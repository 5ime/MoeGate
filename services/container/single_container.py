"""单容器启动：镜像直启与 Dockerfile 启动。"""
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import docker

from config.settings import AppConfig, config as default_config
from core.exceptions import DockerConnectionError, ImageBuildError, PortUnavailableError
from infra.docker import ensure_client
from services.container.container_create import (
    _build_explicit_port_bindings,
    _extract_host_ports_from_bindings,
    build_container_create_kwargs,
    build_port_info,
    cleanup_existing_container,
)
from services.container.image_workflow import (
    build_or_get_image,
    build_or_get_image_streaming,
    ensure_image_available,
    ensure_image_available_streaming,
)
from services.container.port_manager import get_container_ports
from utils.container_manager import get_container_manager
from utils.docker_image import resolve_image_reference
from utils.port_utils import release_port

logger = logging.getLogger(__name__)

__all__ = [
    "ensure_image_available",
    "ensure_image_available_streaming",
    "build_or_get_image",
    "build_or_get_image_streaming",
    "start_from_image",
    "start_from_image_streaming",
    "start_from_dockerfile",
    "_start_from_dockerfile_streaming",
]


def start_from_image(
    image: str,
    uid: int,
    cmd: Optional[str],
    min_port: int,
    max_port: int,
    max_time: int,
    env: Dict,
    port_mappings: Optional[List[Tuple[str, int]]] = None,
    resource_limits: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    network: Optional[str] = None,
    app_config: AppConfig = None,
    **_extra,
) -> Dict[str, Any]:
    """直接使用现有镜像启动容器。"""
    if app_config is None:
        app_config = default_config

    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    image_source = getattr(app_config, "IMAGE_SOURCE", None)
    resolved_image, image_obj = ensure_image_available(image, app_config=app_config, client=client)

    if port_mappings:
        ports = _build_explicit_port_bindings(port_mappings)
    else:
        try:
            ports = get_container_ports(image_obj, min_port, max_port, app_config)
        except PortUnavailableError:
            raise PortUnavailableError(f"端口范围 {min_port}-{max_port} 内没有可用端口")
        except Exception as e:
            raise ImageBuildError(f"获取容器端口失败: {str(e)}")

    container_name = uid
    cleanup_existing_container(client, container_name)

    create_kwargs = build_container_create_kwargs(
        image=image_obj.id,
        name=container_name,
        ports=ports,
        command=cmd,
        environment=env,
        network=network,
        network_mode=None if network else "bridge",
        resource_limits=resource_limits,
        app_config=app_config,
        ttl_seconds=max_time,
        creation_meta=meta,
    )

    reserved_ports = _extract_host_ports_from_bindings(ports)

    try:
        container = client.containers.create(**create_kwargs)
    except docker.errors.APIError as e:
        for reserved_port in reserved_ports:
            release_port(reserved_port)
        raise ImageBuildError(f"创建容器失败: {e}")
    except Exception as e:
        for reserved_port in reserved_ports:
            release_port(reserved_port)
        raise ImageBuildError(f"创建容器失败: {e}")

    try:
        container.start()
        for reserved_port in reserved_ports:
            release_port(reserved_port)
    except Exception as e:
        for reserved_port in reserved_ports:
            release_port(reserved_port)
        try:
            container.remove(force=True)
        except Exception:
            pass
        raise ImageBuildError(f"启动容器失败: {e}")

    manager = get_container_manager()
    creation_meta = dict(meta or {})
    creation_meta.setdefault("source_image", resolved_image)
    if image_source:
        creation_meta.setdefault("source_image_source", image_source)
    creation_meta.setdefault("container_uuid", container_name)
    manager.register_container(container, max_time, metadata=creation_meta)

    port_info = build_port_info(ports, container)
    return {
        "container_id": container.id,
        "container_name": container_name,
        "container_uuid": container_name,
        "start_time": datetime.now().isoformat(),
        "ports": port_info,
    }


def start_from_image_streaming(
    image: str,
    uid,
    cmd: Optional[str],
    min_port: int,
    max_port: int,
    max_time: int,
    env: Dict,
    port_mappings: Optional[List[Tuple[str, int]]] = None,
    resource_limits: Optional[Dict[str, Any]] = None,
    meta=None,
    network: Optional[str] = None,
    app_config: AppConfig = None,
    **_extra,
):
    """直接使用镜像启动容器（流式版本）。"""
    if app_config is None:
        app_config = default_config

    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    image_source = getattr(app_config, "IMAGE_SOURCE", None)
    resolved_image = resolve_image_reference(image, image_source)
    yield f"正在检查镜像: {resolved_image}"
    image_stream = ensure_image_available_streaming(
        image,
        app_config=app_config,
        client=client,
    )
    while True:
        try:
            line = next(image_stream)
            yield line
        except StopIteration as stop:
            resolved_image, image_obj = stop.value
            break

    if port_mappings:
        yield "镜像就绪，正在应用固定端口映射..."
        ports = _build_explicit_port_bindings(port_mappings)
    else:
        yield "镜像就绪，正在分配端口..."
        try:
            ports = get_container_ports(image_obj, min_port, max_port, app_config)
        except PortUnavailableError:
            raise PortUnavailableError(f"端口范围 {min_port}-{max_port} 内没有可用端口")
        except Exception as e:
            raise ImageBuildError(f"获取容器端口失败: {str(e)}")

    container_name = uid
    cleanup_existing_container(client, container_name)
    create_kwargs = build_container_create_kwargs(
        image=image_obj.id,
        name=container_name,
        ports=ports,
        command=cmd,
        environment=env,
        network=network,
        network_mode=None if network else "bridge",
        resource_limits=resource_limits,
        app_config=app_config,
        ttl_seconds=max_time,
        creation_meta=meta,
    )
    reserved_ports = _extract_host_ports_from_bindings(ports)

    yield "正在创建容器..."
    try:
        container = client.containers.create(**create_kwargs)
    except Exception as e:
        for p in reserved_ports:
            release_port(p)
        raise ImageBuildError(f"创建容器失败: {e}")

    yield "正在启动容器..."
    try:
        container.start()
        for p in reserved_ports:
            release_port(p)
    except Exception as e:
        for p in reserved_ports:
            release_port(p)
        try:
            container.remove(force=True)
        except Exception:
            pass
        raise ImageBuildError(f"启动容器失败: {e}")

    manager = get_container_manager()
    creation_meta = dict(meta or {})
    creation_meta.setdefault("source_image", resolved_image)
    if image_source:
        creation_meta.setdefault("source_image_source", image_source)
    creation_meta.setdefault("container_uuid", container_name)
    manager.register_container(container, max_time, metadata=creation_meta)

    port_info = build_port_info(ports, container)
    yield "容器启动成功"
    yield {
        "container_id": container.id,
        "container_name": container_name,
        "container_uuid": container_name,
        "start_time": datetime.now().isoformat(),
        "ports": port_info,
    }


def start_from_dockerfile(
    path: str,
    uid: int,
    cmd: Optional[str],
    min_port: int,
    max_port: int,
    max_time: int,
    env: Dict,
    tag: Optional[str],
    port_mappings: Optional[List[Tuple[str, int]]] = None,
    resource_limits: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    network: Optional[str] = None,
    app_config: AppConfig = None,
) -> Dict[str, Any]:
    """从 Dockerfile 启动容器。"""
    if app_config is None:
        app_config = default_config

    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    image = build_or_get_image(path, tag)

    if port_mappings:
        ports = _build_explicit_port_bindings(port_mappings)
    else:
        try:
            ports = get_container_ports(image, min_port, max_port, app_config)
        except PortUnavailableError:
            raise PortUnavailableError(f"端口范围 {min_port}-{max_port} 内没有可用端口")
        except Exception as e:
            logger.error("获取容器端口失败: %s", e)
            raise ImageBuildError(f"获取容器端口失败: {str(e)}")

    container_name = uid
    cleanup_existing_container(client, container_name)

    create_kwargs = build_container_create_kwargs(
        image=image.id,
        name=container_name,
        ports=ports,
        command=cmd,
        environment=env,
        network=network,
        network_mode=None if network else "bridge",
        resource_limits=resource_limits,
        app_config=app_config,
        ttl_seconds=max_time,
        creation_meta=meta,
    )

    reserved_ports = _extract_host_ports_from_bindings(ports)

    try:
        container = client.containers.create(**create_kwargs)
    except docker.errors.APIError as e:
        for reserved_port in reserved_ports:
            release_port(reserved_port)
        logger.error("创建容器失败: %s", e)
        raise ImageBuildError(f"创建容器失败: {e}")
    except Exception as e:
        for reserved_port in reserved_ports:
            release_port(reserved_port)
        logger.error("创建容器时发生未知错误: %s", e)
        raise ImageBuildError(f"创建容器失败: {e}")

    try:
        container.start()
        for reserved_port in reserved_ports:
            release_port(reserved_port)
    except (docker.errors.APIError, Exception) as e:
        for reserved_port in reserved_ports:
            release_port(reserved_port)
        logger.error("启动容器失败: %s", e)
        try:
            container.remove(force=True)
        except Exception:
            pass
        raise ImageBuildError(f"启动容器失败: {e}")

    manager = get_container_manager()
    creation_meta = dict(meta or {})
    creation_meta.setdefault("source_path", path)
    creation_meta.setdefault("container_uuid", container_name)
    manager.register_container(container, max_time, metadata=creation_meta)

    port_info = build_port_info(ports, container)
    logger.debug("最终端口信息: %s", port_info)

    return {
        "container_id": container.id,
        "container_name": container_name,
        "container_uuid": container_name,
        "start_time": datetime.now().isoformat(),
        "ports": port_info,
    }


def _start_from_dockerfile_streaming(
    path: str,
    uid,
    cmd,
    min_port: int,
    max_port: int,
    max_time: int,
    env: Dict,
    tag,
    port_mappings: Optional[List[Tuple[str, int]]] = None,
    resource_limits: Optional[Dict[str, Any]] = None,
    meta=None,
    network: Optional[str] = None,
    app_config: AppConfig = None,
):
    """从 Dockerfile 启动容器（流式版本）。"""
    if app_config is None:
        app_config = default_config

    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    resolved_tag = tag or f"dynamic-container-{random.randint(100000, 999999)}"

    yield "正在构建镜像..."
    image = None
    for line in build_or_get_image_streaming(path, resolved_tag):
        if line == "__IMAGE_READY__":
            image = client.images.get(resolved_tag)
            continue
        yield line

    if image is None:
        image = build_or_get_image(path, resolved_tag)

    if port_mappings:
        yield "镜像就绪，正在应用固定端口映射..."
        ports = _build_explicit_port_bindings(port_mappings)
    else:
        yield "镜像就绪，正在分配端口..."
        try:
            ports = get_container_ports(image, min_port, max_port, app_config)
        except PortUnavailableError:
            raise PortUnavailableError(f"端口范围 {min_port}-{max_port} 内没有可用端口")
        except Exception as e:
            raise ImageBuildError(f"获取容器端口失败: {str(e)}")

    container_name = uid
    cleanup_existing_container(client, container_name)

    create_kwargs = build_container_create_kwargs(
        image=image.id,
        name=container_name,
        ports=ports,
        command=cmd,
        environment=env,
        network=network,
        network_mode=None if network else "bridge",
        resource_limits=resource_limits,
        app_config=app_config,
        ttl_seconds=max_time,
        creation_meta=meta,
    )
    reserved_ports = _extract_host_ports_from_bindings(ports)

    yield "正在创建容器..."
    try:
        container = client.containers.create(**create_kwargs)
    except Exception as e:
        for p in reserved_ports:
            release_port(p)
        raise ImageBuildError(f"创建容器失败: {e}")

    yield "正在启动容器..."
    try:
        container.start()
        for p in reserved_ports:
            release_port(p)
    except Exception as e:
        for p in reserved_ports:
            release_port(p)
        try:
            container.remove(force=True)
        except Exception:
            pass
        raise ImageBuildError(f"启动容器失败: {e}")

    manager = get_container_manager()
    creation_meta = dict(meta or {})
    creation_meta.setdefault("source_path", path)
    creation_meta.setdefault("container_uuid", container_name)
    manager.register_container(container, max_time, metadata=creation_meta)

    port_info = build_port_info(ports, container)
    yield "容器启动成功"

    yield {
        "container_id": container.id,
        "container_name": container_name,
        "container_uuid": container_name,
        "start_time": datetime.now().isoformat(),
        "ports": port_info,
    }

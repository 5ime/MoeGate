"""Compose 项目启动编排。"""
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import yaml

from config.settings import AppConfig, config as default_config
from core.exceptions import DockerConnectionError, ImageBuildError, ValidationError
from infra.docker import ensure_client
from services.container.compose_env import apply_compose_service_env
from services.container.compose_policy import (
    order_compose_services,
    prepare_compose_services_policy,
)
from services.container.compose_volumes import resolve_compose_service_volumes
from services.container.compose_project import process_service_ports
from services.container.container_create import build_container_create_kwargs, cleanup_existing_container
from services.container.info import get_container_info
from services.container.network_pool import ensure_compose_networks as _ensure_compose_networks
from services.container.single_container import (
    build_or_get_image,
    build_or_get_image_streaming,
    ensure_image_available,
    ensure_image_available_streaming,
)
from core.exceptions import InvalidPathError
from utils.container_manager import get_container_manager
from utils.docker_image import resolve_image_reference
from utils.path_validator import validate_path
from utils.port_utils import release_port

logger = logging.getLogger(__name__)


def _resolve_and_validate_compose_build(compose_path: str, build_spec) -> Tuple[str, Optional[str]]:
    """解析 Compose build 配置，返回 (context 绝对路径, dockerfile 相对 context 或 None)。"""
    dockerfile: Optional[str] = None
    if isinstance(build_spec, dict):
        context = build_spec.get("context", ".")
        raw_dockerfile = build_spec.get("dockerfile")
        if raw_dockerfile is not None:
            dockerfile = str(raw_dockerfile)
    elif isinstance(build_spec, str):
        context = build_spec
    else:
        raise ImageBuildError("build 配置格式无效")

    if not isinstance(context, str):
        raise ImageBuildError("build.context 必须是字符串")

    compose_dir = os.path.dirname(os.path.abspath(compose_path))
    if os.path.isabs(context):
        candidate = os.path.normpath(context)
    else:
        candidate = os.path.normpath(os.path.join(compose_dir, context))

    try:
        validated_context = validate_path(candidate)
    except InvalidPathError as exc:
        raise ImageBuildError(str(exc)) from exc

    if dockerfile:
        dockerfile_abs = os.path.normpath(os.path.join(validated_context, dockerfile))
        try:
            validate_path(dockerfile_abs)
        except InvalidPathError as exc:
            raise ImageBuildError(str(exc)) from exc

    return validated_context, dockerfile


def _load_compose_services(compose_path: str) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], List[Tuple[str, Dict[str, Any]]]]:
    """加载 compose 文件并完成策略校验与服务排序。"""
    with open(compose_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f) or {}

    services = content.get("services", {}) or {}
    compose_warnings, policy_error = prepare_compose_services_policy(services)
    if policy_error:
        raise ValidationError(policy_error)
    for warning in compose_warnings:
        logger.warning("Compose 配置提示: %s", warning)

    try:
        ordered_services = order_compose_services(services)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    return content, services, compose_warnings, ordered_services


def _normalize_cap_list(raw: Any) -> Optional[List[str]]:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple, set)):
        values = [str(item).strip() for item in raw if str(item).strip()]
        return values or None
    text = str(raw).strip()
    return [text] if text else None


def start_from_compose(
    compose_path: str,
    uid: int,
    max_time: int,
    env: Dict,
    resource_limits: Optional[Dict[str, Any]] = None,
    app_config: AppConfig = None,
    meta: Optional[Dict[str, Any]] = None,
    min_port: Optional[int] = None,
    max_port: Optional[int] = None,
    port_mappings: Optional[List[Tuple[str, int]]] = None,
) -> Dict[str, Any]:
    """从 Docker Compose 启动容器。"""
    if app_config is None:
        app_config = default_config

    containers_to_start: List[Tuple[Any, str]] = []
    created_networks: List[str] = []

    try:
        content, services, compose_warnings, ordered_services = _load_compose_services(compose_path)

        compose_project_id = str(uid)
        client = ensure_client()
        manager = get_container_manager()
        compose_network_map, created_networks = _ensure_compose_networks(
            client=client,
            compose_content=content,
            compose_project_id=compose_project_id,
            app_config=app_config,
        )

        multi_service = len(services) > 1

        for name, service in ordered_services:
            if multi_service:
                service_uuid = str(uuid.uuid4())
                service["container_name"] = service_uuid
            else:
                service["container_name"] = uid
            service["image"] = service.get("image", name)
            apply_compose_service_env(service, env, multi_service=multi_service, service_name=name)
            service["ports"] = process_service_ports(
                service,
                app_config,
                port_mappings=port_mappings if not multi_service else None,
                min_port=min_port,
                max_port=max_port,
                containers=manager.get_all_containers(),
            )
            service["_compose_project_id"] = compose_project_id
            service["_compose_service_name"] = name

            network_keys = _extract_service_network_keys(service)
            primary_network = compose_network_map.get(network_keys[0]) if network_keys else None
            extra_networks = [compose_network_map[key] for key in network_keys[1:] if key in compose_network_map]
            service["_primary_network"] = primary_network
            service["_extra_networks"] = extra_networks
            service["_resolved_volumes"] = resolve_compose_service_volumes(compose_path, name, service)

            if service.get("build"):
                build_path, dockerfile = _resolve_and_validate_compose_build(
                    compose_path,
                    service.get("build", "."),
                )
                logger.info("从 docker-compose 构建镜像，路径: %s", build_path)
                build_or_get_image(build_path, service["image"], dockerfile=dockerfile)

            container = create_container_from_service(
                service,
                app_config,
                resource_limits=resource_limits,
                max_time=max_time,
                creation_meta=meta,
            )
            containers_to_start.append((container, name))

        for container, service_name in containers_to_start:
            creation_meta = dict(meta or {})
            creation_meta.setdefault("source_path", compose_path)
            creation_meta.setdefault("container_uuid", container.name)
            creation_meta.setdefault("compose_project_id", compose_project_id)
            creation_meta.setdefault("compose_service_name", service_name)
            manager.set_timer(container.id, max_time, container_name=container.name, metadata=creation_meta)

        data = []
        for container, service_name in containers_to_start:
            info = get_container_info(container)
            info.setdefault("compose_project_id", compose_project_id)
            info.setdefault("compose_service", service_name)
            if compose_warnings:
                info["compose_warnings"] = compose_warnings
            data.append(info)

        get_container_manager().consume_reservation(slots=len(containers_to_start))
        return data[0] if len(data) == 1 else data

    except Exception:
        rollback_client = ensure_client()
        for container, _service_name in containers_to_start:
            try:
                get_container_manager().remove_container(container.id)
                container.remove(force=True)
            except Exception as container_cleanup_err:
                logger.warning(
                    "Compose 回滚容器失败: %s, err=%s",
                    getattr(container, "id", "unknown"),
                    container_cleanup_err,
                )

        if rollback_client:
            for network_name in created_networks:
                try:
                    rollback_client.networks.get(network_name).remove()
                except Exception as network_cleanup_err:
                    logger.warning("Compose 回滚网络失败: %s, err=%s", network_name, network_cleanup_err)

        logger.exception("Docker Compose启动失败")
        raise


def create_container_from_service(
    service: Dict,
    app_config: AppConfig = None,
    resource_limits: Optional[Dict[str, Any]] = None,
    max_time: Optional[int] = None,
    creation_meta: Optional[Dict[str, Any]] = None,
):
    """从服务配置创建并启动容器。"""
    if app_config is None:
        app_config = default_config

    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    image_id = service.get("_resolved_image_id")
    if not image_id:
        _resolved_image, image_obj = ensure_image_available(service["image"], app_config=app_config, client=client)
        image_id = image_obj.id

    container_name = service["container_name"]
    cleanup_existing_container(client, container_name)

    port_bindings = {}
    reserved_ports: List[int] = []
    for port_str in service["ports"]:
        parts = port_str.split(":")
        if len(parts) == 2:
            host_port, container_port = parts
            port_bindings[container_port] = (None, host_port)
            try:
                reserved_ports.append(int(host_port))
            except (TypeError, ValueError):
                pass

    extra_labels = {
        "moegate.compose_project_id": str(service.get("_compose_project_id") or ""),
        "moegate.compose_service": str(service.get("_compose_service_name") or ""),
    }
    primary_network = service.get("_primary_network")

    create_kwargs = build_container_create_kwargs(
        image=image_id,
        name=container_name,
        ports=port_bindings,
        command=service.get("command"),
        environment=service.get("environment"),
        extra_labels=extra_labels,
        network=primary_network,
        network_mode=None if primary_network else "bridge",
        resource_limits=resource_limits,
        app_config=app_config,
        ttl_seconds=max_time,
        creation_meta=creation_meta,
        volumes=service.get("_resolved_volumes") or None,
        privileged=service.get("privileged") is True,
        cap_add=_normalize_cap_list(service.get("cap_add")),
        cap_drop=_normalize_cap_list(service.get("cap_drop")),
    )

    container = None
    try:
        container = client.containers.create(**create_kwargs)
        container.start()

        for network_name in service.get("_extra_networks", []):
            try:
                client.networks.get(network_name).connect(container)
            except Exception as network_err:
                logger.warning("连接额外网络失败: %s, err=%s", network_name, network_err)

        manager = get_container_manager()
        manager.add_container(container.id, container, consume_reservation=False)
        return container
    except Exception:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
        raise
    finally:
        for reserved_port in reserved_ports:
            release_port(reserved_port)


def _extract_service_network_keys(service: Dict[str, Any]) -> List[str]:
    """提取服务声明的网络名称列表。"""
    raw_networks = service.get("networks")
    if not raw_networks:
        return []

    if isinstance(raw_networks, list):
        return [str(item) for item in raw_networks if item]

    if isinstance(raw_networks, dict):
        return [str(key) for key in raw_networks.keys()]

    return []


def _start_from_compose_streaming(
    compose_path: str,
    uid,
    max_time: int,
    env: Dict,
    resource_limits: Optional[Dict[str, Any]] = None,
    app_config: AppConfig = None,
    meta=None,
    min_port: Optional[int] = None,
    max_port: Optional[int] = None,
    port_mappings: Optional[List[Tuple[str, int]]] = None,
):
    """从 Docker Compose 启动容器（流式版本）。"""
    if app_config is None:
        app_config = default_config

    containers_to_start: List[Tuple[Any, str]] = []
    created_networks: List[str] = []

    try:
        content, services, compose_warnings, ordered_services = _load_compose_services(compose_path)

        compose_project_id = str(uid)
        client = ensure_client()
        manager = get_container_manager()
        compose_network_map, created_networks = _ensure_compose_networks(
            client=client,
            compose_content=content,
            compose_project_id=compose_project_id,
            app_config=app_config,
        )

        multi_service = len(services) > 1

        for name, service in ordered_services:
            if multi_service:
                service_uuid = str(uuid.uuid4())
                service["container_name"] = service_uuid
            else:
                service["container_name"] = uid
            service["image"] = service.get("image", name)
            apply_compose_service_env(service, env, multi_service=multi_service, service_name=name)
            service["ports"] = process_service_ports(
                service,
                app_config,
                port_mappings=port_mappings if not multi_service else None,
                min_port=min_port,
                max_port=max_port,
                containers=manager.get_all_containers(),
            )
            service["_compose_project_id"] = compose_project_id
            service["_compose_service_name"] = name

            network_keys = _extract_service_network_keys(service)
            primary_network = compose_network_map.get(network_keys[0]) if network_keys else None
            extra_networks = [compose_network_map[key] for key in network_keys[1:] if key in compose_network_map]
            service["_primary_network"] = primary_network
            service["_extra_networks"] = extra_networks
            service["_resolved_volumes"] = resolve_compose_service_volumes(compose_path, name, service)

            if service.get("build"):
                build_path, dockerfile = _resolve_and_validate_compose_build(
                    compose_path,
                    service.get("build", "."),
                )
                yield f"[{name}] 开始构建镜像..."
                for line in build_or_get_image_streaming(build_path, service["image"], dockerfile=dockerfile):
                    if line == "__IMAGE_READY__":
                        continue
                    yield f"[{name}] {line}"

            image_preview = resolve_image_reference(service["image"], getattr(app_config, "IMAGE_SOURCE", None))
            yield f"[{name}] 正在检查镜像: {image_preview}"
            image_stream = ensure_image_available_streaming(
                service["image"],
                app_config=app_config,
                client=client,
            )
            while True:
                try:
                    line = next(image_stream)
                    yield f"[{name}] {line}"
                except StopIteration as stop:
                    _resolved_image, image_obj = stop.value
                    break
            service["_resolved_image_id"] = image_obj.id

            yield f"[{name}] 正在创建容器..."
            container = create_container_from_service(
                service,
                app_config,
                resource_limits=resource_limits,
                max_time=max_time,
                creation_meta=meta,
            )
            containers_to_start.append((container, name))
            yield f"[{name}] 容器已启动"

        for container, service_name in containers_to_start:
            creation_meta = dict(meta or {})
            creation_meta.setdefault("source_path", compose_path)
            creation_meta.setdefault("container_uuid", container.name)
            creation_meta.setdefault("compose_project_id", compose_project_id)
            creation_meta.setdefault("compose_service_name", service_name)
            manager.set_timer(container.id, max_time, container_name=container.name, metadata=creation_meta)

        data = []
        for container, service_name in containers_to_start:
            info = get_container_info(container)
            info.setdefault("compose_project_id", compose_project_id)
            info.setdefault("compose_service", service_name)
            if compose_warnings:
                info["compose_warnings"] = compose_warnings
            data.append(info)

        yield "所有服务启动完成"
        get_container_manager().consume_reservation(slots=len(containers_to_start))
        yield data[0] if len(data) == 1 else data

    except Exception:
        rollback_client = ensure_client()
        for container, _service_name in containers_to_start:
            try:
                get_container_manager().remove_container(container.id)
                container.remove(force=True)
            except Exception:
                pass
        if rollback_client:
            for network_name in created_networks:
                try:
                    rollback_client.networks.get(network_name).remove()
                except Exception:
                    pass
        raise

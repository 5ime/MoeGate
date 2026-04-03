"""容器构建和创建"""
import os
import yaml
import docker
import random
import logging
import types
from contextlib import contextmanager
import uuid
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from config.settings import config as default_config, AppConfig
from core.exceptions import (
    DockerConnectionError,
    ImageBuildError,
    PortUnavailableError,
)
from infra.docker import (
    ensure_client,
)
from utils.container_manager import get_container_manager
from services.container.port_manager import get_container_ports, process_service_ports, get_port_info
from services.container.info import get_container_info
from utils.port_utils import release_port

logger = logging.getLogger(__name__)


def _resolve_image_reference(image: str, image_source: Optional[str] = None) -> str:
    """根据可选镜像源拼接或改写镜像引用。"""
    image_ref = str(image or "").strip()
    if not image_ref:
        raise ImageBuildError("镜像名不能为空")

    source = str(image_source or "").strip()
    if not source:
        return image_ref

    source = source.rstrip("/")
    if source.startswith("http://"):
        source = source[len("http://"):]
    elif source.startswith("https://"):
        source = source[len("https://"):]

    if not source:
        raise ImageBuildError("镜像源不能为空")

    # 判断镜像是否已包含 registry 前缀
    # 只看 "/" 前的部分；需排除 tag 中的 ":" 干扰（如 nginx:latest）
    parts = image_ref.split("/", 1)
    first_segment = parts[0].split(":")[0]  # 去掉端口或 tag
    has_registry = ("." in first_segment or first_segment == "localhost") and len(parts) > 1

    if not has_registry:
        return f"{source}/{image_ref}"

    if image_ref.startswith(f"{source}/"):
        return image_ref

    _, remainder = image_ref.split("/", 1)
    return f"{source}/{remainder}"


def _extract_host_ports_from_bindings(ports: Dict[str, tuple]) -> List[int]:
    """提取端口绑定中的宿主机端口列表。"""
    host_ports: List[int] = []
    for host_binding in (ports or {}).values():
        if isinstance(host_binding, tuple) and len(host_binding) >= 2:
            host_port = host_binding[1]
            try:
                host_ports.append(int(host_port))
            except (TypeError, ValueError):
                continue
    return host_ports


def build_port_info(ports: Dict[str, tuple], container) -> Dict[str, str]:
    """从预期的端口映射或容器属性构建端口信息
    
    优先使用创建参数中的 ports（可靠、无需等待容器网络就绪）；
    若无法获取，则回退到容器属性并在必要时 reload。
    """
    port_info: Dict[str, str] = {}
    try:
        for container_port, host_port_tuple in (ports or {}).items():
            if isinstance(host_port_tuple, tuple) and len(host_port_tuple) >= 2:
                host_port = host_port_tuple[1]
                if host_port:
                    port_info[container_port] = str(host_port)
        if port_info:
            return port_info
    except Exception as e:
        logger.debug("从 ports 构建端口信息失败，将回退到容器属性: %s", e)
    
    # 回退：从容器属性读取
    try:
        port_info = get_port_info(container) or {}
        if port_info:
            return port_info
        # 二次回退：reload 后再取
        try:
            container.reload()
            port_info = get_port_info(container) or {}
        except Exception as reload_err:
            logger.debug("容器属性重载失败: %s", reload_err)
        return port_info
    except Exception as e:
        logger.warning("从容器属性读取端口信息失败: %s", e)
        return {}


def _build_explicit_port_bindings(port_mappings: Optional[List[Tuple[str, int]]]) -> Dict[str, tuple]:
    """将显式端口映射转换为 Docker SDK 所需格式。"""
    bindings: Dict[str, tuple] = {}
    for container_port, host_port in (port_mappings or []):
        bindings[str(container_port)] = (None, int(host_port))
    return bindings


@contextmanager
def disable_docker_credentials(client):
    """临时禁用 docker 凭证存储，避免构建阶段触发外部凭证助手"""
    original_auth_configs = None
    original_get_all_credentials = None
    try:
        if hasattr(client.api, '_auth_configs'):
            auth_configs = client.api._auth_configs
            original_auth_configs = auth_configs
            if hasattr(auth_configs, 'get_all_credentials'):
                original_get_all_credentials = auth_configs.get_all_credentials

            def disabled_get_all_credentials(self):
                return {}

            auth_configs.get_all_credentials = types.MethodType(disabled_get_all_credentials, auth_configs)
            if hasattr(auth_configs, '_store'):
                auth_configs._store = None
            if hasattr(auth_configs, '_creds_store'):
                auth_configs._creds_store = None
            logger.debug("已禁用 Docker 凭证存储（context manager）")
    except Exception as e:
        logger.warning("禁用凭证存储失败（将继续构建）: %s", e)
    try:
        yield
    finally:
        if original_auth_configs is not None and original_get_all_credentials is not None:
            try:
                if hasattr(client.api, '_auth_configs'):
                    auth_configs = client.api._auth_configs
                    auth_configs.get_all_credentials = original_get_all_credentials
            except Exception as restore_err:
                logger.warning("恢复凭证配置时出现警告: %s", restore_err)


def build_or_get_image(path: str, tag: Optional[str]):
    """构建或获取Docker镜像
    
    Args:
        path: Dockerfile所在目录路径
        tag: 镜像标签，如果指定且镜像已存在则直接使用
        
    Returns:
        docker.models.images.Image: Docker镜像对象
        
    Raises:
        DockerConnectionError: Docker客户端不可用时抛出
        ImageBuildError: 镜像构建失败时抛出
    """
    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")
    
    path = os.path.normpath(path)
    
    if os.path.isfile(path):
        path = os.path.dirname(path)
    
    if not os.path.exists(path):
        raise ImageBuildError(f"构建路径不存在: {path}")
    
    if not os.path.isdir(path):
        raise ImageBuildError(f"构建路径不是目录: {path}")
    
    if tag:
        try:
            image = client.images.get(tag)
            logger.info("使用已存在的镜像: %s", tag)
            return image
        except docker.errors.ImageNotFound:
            logger.info("镜像 %s 不存在，开始构建", tag)
    
    final_tag = tag or f"dynamic-container-{random.randint(100000, 999999)}"
    logger.info("开始构建镜像: %s, 路径: %s", final_tag, path)
    
    # 在构建过程中临时禁用凭证存储
    # 可配置地禁用凭证存储
    use_disable_creds = getattr(default_config, "DISABLE_DOCKER_CREDENTIALS", False)
    context_mgr = disable_docker_credentials(client) if use_disable_creds else contextmanager(lambda: (yield))()
    with context_mgr:
        try:
            image, _ = client.images.build(path=path, tag=final_tag, rm=True, forcerm=True)
        except docker.errors.BuildError as e:
            error_msg = str(e)
            build_log = ""
            if hasattr(e, 'build_log') and e.build_log:
                build_log = "\n".join([log.get('stream', '') for log in e.build_log if log.get('stream')])
                if build_log:
                    error_msg = f"{error_msg}\n构建日志:\n{build_log[-500:]}"
            logger.error("镜像构建失败: %s", error_msg)
            raise ImageBuildError(f"构建镜像失败: {error_msg}")
        except docker.errors.APIError as e:
            error_msg = f"Docker API错误: {str(e)}"
            logger.error(error_msg)
            raise ImageBuildError(error_msg)
        except Exception as e:
            error_msg = f"构建镜像时发生未知错误: {str(e)}"
            logger.exception(error_msg)
            raise ImageBuildError(error_msg)

        logger.info("镜像构建成功: %s", final_tag)
        return image


def build_or_get_image_streaming(path: str, tag: Optional[str]):
    """构建或获取Docker镜像，以生成器方式逐行返回构建日志。

    每次 yield 一个字符串（日志行），构建完成后最终 yield
    特殊标记 ``__IMAGE_READY__`` 表示成功。若构建失败，
    会直接抛出 ImageBuildError。

    Args:
        path: Dockerfile 所在目录路径
        tag: 镜像标签

    Yields:
        str: 构建日志行

    Raises:
        DockerConnectionError: Docker 客户端不可用
        ImageBuildError: 构建失败
    """
    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    path = os.path.normpath(path)
    if os.path.isfile(path):
        path = os.path.dirname(path)
    if not os.path.exists(path):
        raise ImageBuildError(f"构建路径不存在: {path}")
    if not os.path.isdir(path):
        raise ImageBuildError(f"构建路径不是目录: {path}")

    if tag:
        try:
            client.images.get(tag)
            yield f"镜像 {tag} 已存在，跳过构建"
            yield "__IMAGE_READY__"
            return
        except docker.errors.ImageNotFound:
            yield f"镜像 {tag} 不存在，开始构建..."

    final_tag = tag or f"dynamic-container-{random.randint(100000, 999999)}"
    yield f"开始构建镜像: {final_tag}"

    use_disable_creds = getattr(default_config, "DISABLE_DOCKER_CREDENTIALS", False)
    context_mgr = disable_docker_credentials(client) if use_disable_creds else contextmanager(lambda: (yield))()
    with context_mgr:
        try:
            # 使用低级 API 逐行获取构建日志
            resp = client.api.build(path=path, tag=final_tag, rm=True, forcerm=True, decode=True)
            for chunk in resp:
                if "stream" in chunk:
                    line = chunk["stream"].rstrip("\n")
                    if line:
                        yield line
                if "error" in chunk:
                    raise ImageBuildError(f"构建镜像失败: {chunk['error']}")
        except ImageBuildError:
            raise
        except docker.errors.BuildError as e:
            error_msg = str(e)
            if hasattr(e, 'build_log') and e.build_log:
                build_log = "\n".join([log.get('stream', '') for log in e.build_log if log.get('stream')])
                if build_log:
                    error_msg = f"{error_msg}\n构建日志:\n{build_log[-500:]}"
            raise ImageBuildError(f"构建镜像失败: {error_msg}")
        except docker.errors.APIError as e:
            raise ImageBuildError(f"Docker API错误: {str(e)}")
        except Exception as e:
            raise ImageBuildError(f"构建镜像时发生未知错误: {str(e)}")

    yield f"镜像构建成功: {final_tag}"
    yield "__IMAGE_READY__"


def cleanup_existing_container(client, container_name: str):
    """清理已存在的同名容器
    
    Args:
        client: Docker客户端对象
        container_name: 容器名称
    """
    try:
        existing = client.containers.get(container_name)
        labels = (existing.attrs or {}).get("Config", {}).get("Labels") or {}
        if str(labels.get("moegate.managed") or "").lower() != "true":
            # 防止误删宿主机上非本系统管理的容器
            logger.warning(
                "检测到同名容器但非本系统管理，拒绝清理: name=%s, id=%s",
                container_name,
                getattr(existing, "id", "unknown"),
            )
            return
        logger.warning("删除已存在的受管同名容器: %s", container_name)
        existing.stop()
        existing.remove()
    except docker.errors.NotFound:
        pass


def build_container_create_kwargs(
    image: str,
    name: str,
    ports: Dict[str, tuple],
    command: Optional[str] = None,
    environment: Optional[Dict] = None,
    extra_labels: Optional[Dict[str, str]] = None,
    network: Optional[str] = None,
    network_mode: Optional[str] = "bridge",
    resource_limits: Optional[Dict[str, Any]] = None,
    app_config: AppConfig = None
) -> Dict[str, Any]:
    """构建容器创建参数字典（公共函数）
    
    Args:
        image: 镜像ID或标签
        name: 容器名称
        ports: 端口绑定字典
        command: 容器启动命令
        environment: 环境变量字典
        app_config: 应用配置对象
        
    Returns:
        Dict[str, Any]: 容器创建参数字典
    """
    if app_config is None:
        app_config = default_config
    
    labels = {
        "moegate.managed": "true",
        "moegate.container_name": name,
    }
    if extra_labels:
        labels.update(extra_labels)

    create_kwargs = {
        "image": image,
        "name": name,
        "command": command,
        "detach": True,
        "ports": ports,
        "environment": environment or {},
        "labels": labels,
        "restart_policy": {"Name": "no"}
    }

    if network:
        create_kwargs["network"] = network
    elif network_mode:
        create_kwargs["network_mode"] = network_mode
    
    effective_limits = resource_limits or {}
    memory_limit = effective_limits.get("memory_limit")
    if memory_limit is None:
        memory_limit = app_config.CONTAINER_MEMORY_LIMIT
    if memory_limit:
        create_kwargs["mem_limit"] = memory_limit

    cpu_limit = effective_limits.get("cpu_limit")
    if cpu_limit is None:
        cpu_limit = app_config.CONTAINER_CPU_LIMIT
    if cpu_limit is not None:
        create_kwargs["cpu_quota"] = int(float(cpu_limit) * 100000)
        create_kwargs["cpu_period"] = 100000

    cpu_shares = effective_limits.get("cpu_shares")
    if cpu_shares is None:
        cpu_shares = app_config.CONTAINER_CPU_SHARES
    if cpu_shares is not None:
        create_kwargs["cpu_shares"] = int(cpu_shares)
    
    return create_kwargs


def start_container_from_source(file_path: str, app_config: AppConfig = None, **params) -> Dict[str, Any]:
    """根据文件类型选择相应的启动方式
    
    Args:
        file_path: Docker配置文件路径
        app_config: 应用配置对象，默认使用全局配置
        **params: 容器启动参数
        
    Returns:
        Dict[str, Any]: 容器信息字典
    """
    if app_config is None:
        app_config = default_config
    
    if file_path.endswith(('.yaml', '.yml')):
        return start_from_compose(
            file_path,
            params['uid'],
            params['max_time'],
            params['env'],
            resource_limits=params.get('resource_limits'),
            app_config=app_config,
            meta=params.get('meta'),
        )
    
    if 'path' in params:
        dockerfile_dir = params['path']
    else:
        dockerfile_dir = os.path.dirname(file_path) if os.path.dirname(file_path) else '.'
    
    dockerfile_params = {
        'path': dockerfile_dir,
        'uid': params['uid'],
        'cmd': params.get('cmd'),
        'min_port': params['min_port'],
        'max_port': params['max_port'],
        'max_time': params['max_time'],
        'env': params.get('env', {}),
        'tag': params.get('tag'),
        'port_mappings': params.get('port_mappings'),
        'resource_limits': params.get('resource_limits'),
        'meta': params.get('meta'),
    }
    return start_from_dockerfile(app_config=app_config, **dockerfile_params)


def start_container_from_source_streaming(file_path: str, app_config: AppConfig = None, **params):
    """与 start_container_from_source 相同，但以生成器形式逐行返回构建日志。

    Yields:
        str: 日志行（普通文本）。最后一条 yield 的值为最终的容器信息字典。
    """
    if app_config is None:
        app_config = default_config

    if file_path.endswith(('.yaml', '.yml')):
        yield from _start_from_compose_streaming(
            file_path,
            params['uid'],
            params['max_time'],
            params['env'],
            resource_limits=params.get('resource_limits'),
            app_config=app_config,
            meta=params.get('meta'),
        )
        return

    if 'path' in params:
        dockerfile_dir = params['path']
    else:
        dockerfile_dir = os.path.dirname(file_path) if os.path.dirname(file_path) else '.'

    dockerfile_params = {
        'path': dockerfile_dir,
        'uid': params['uid'],
        'cmd': params.get('cmd'),
        'min_port': params['min_port'],
        'max_port': params['max_port'],
        'max_time': params['max_time'],
        'env': params.get('env', {}),
        'tag': params.get('tag'),
        'port_mappings': params.get('port_mappings'),
        'resource_limits': params.get('resource_limits'),
        'meta': params.get('meta'),
    }
    yield from _start_from_dockerfile_streaming(app_config=app_config, **dockerfile_params)


def start_from_dockerfile(path: str, uid: int, cmd: Optional[str], min_port: int, 
                          max_port: int, max_time: int, env: Dict, tag: Optional[str],
                          port_mappings: Optional[List[Tuple[str, int]]] = None,
                          resource_limits: Optional[Dict[str, Any]] = None,
                          meta: Optional[Dict[str, Any]] = None,
                          app_config: AppConfig = None) -> Dict[str, Any]:
    """从Dockerfile启动容器
    
    Args:
        path: Dockerfile所在目录路径
        uid: 容器唯一标识符
        cmd: 容器启动命令
        min_port: 最小端口号
        max_port: 最大端口号
        max_time: 容器最大存活时间（秒）
        env: 环境变量字典
        tag: 镜像标签
        
    Returns:
        Dict[str, Any]: 容器信息字典
        
    Raises:
        DockerConnectionError: Docker客户端不可用时抛出
        ImageBuildError: 镜像构建或容器创建失败时抛出
        PortUnavailableError: 端口不可用时抛出
    """
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

    # 使用 UUID 作为容器名称（直接使用 UUID，不带前缀）
    container_name = uid
    cleanup_existing_container(client, container_name)

    # 构建容器创建参数（使用公共函数）
    create_kwargs = build_container_create_kwargs(
        image=image.id,
        name=container_name,
        ports=ports,
        command=cmd,
        environment=env,
        resource_limits=resource_limits,
        app_config=app_config
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
    
    # 从端口配置构建端口信息，失败则自动回退到容器属性
    port_info = build_port_info(ports, container)
    logger.debug("最终端口信息: %s", port_info)

    return {
        "container_id": container.id,
        "container_name": container_name,
        "container_uuid": container_name,  # UUID格式的容器名称
        "start_time": datetime.now().isoformat(),
        "ports": port_info,
    }


def start_from_compose(
    compose_path: str,
    uid: int,
    max_time: int,
    env: Dict,
    resource_limits: Optional[Dict[str, Any]] = None,
    app_config: AppConfig = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从Docker Compose启动容器
    
    Args:
        compose_path: docker-compose文件路径
        uid: 容器唯一标识符
        max_time: 容器最大存活时间（秒）
        env: 环境变量字典
        
    Returns:
        Dict[str, Any]: 容器信息字典或字典列表
        
    Raises:
        ImageBuildError: 镜像构建失败时抛出
    """
    if app_config is None:
        app_config = default_config
    
    containers_to_start: List[Tuple[Any, str]] = []
    created_networks: List[str] = []

    try:
        with open(compose_path, "r", encoding='utf-8') as f:
            content = yaml.safe_load(f)
        
        compose_project_id = str(uid)
        client = ensure_client()
        compose_network_map, created_networks = _ensure_compose_networks(
            client=client,
            compose_content=content,
            compose_project_id=compose_project_id,
        )

        for name, service in content.get("services", {}).items():
            # 使用 UUID 作为容器名称，如果是多个服务则使用独立的 UUID
            if len(content.get("services", {})) > 1:
                service_uuid = str(uuid.uuid4())
                service["container_name"] = service_uuid
            else:
                service["container_name"] = uid
            service["image"] = service.get("image", name)
            service_env = service.get("environment") or {}
            if isinstance(service_env, list):
                merged_env = {}
                for item in service_env:
                    if isinstance(item, str) and "=" in item:
                        key, value = item.split("=", 1)
                        merged_env[key] = value
                service_env = merged_env
            elif not isinstance(service_env, dict):
                service_env = {}

            merged_env = dict(service_env)
            merged_env.update(env or {})
            service["environment"] = merged_env
            service["ports"] = process_service_ports(service, app_config)
            service["_compose_project_id"] = compose_project_id
            service["_compose_service_name"] = name

            network_keys = _extract_service_network_keys(service)
            primary_network = compose_network_map.get(network_keys[0]) if network_keys else None
            extra_networks = [compose_network_map[key] for key in network_keys[1:] if key in compose_network_map]
            service["_primary_network"] = primary_network
            service["_extra_networks"] = extra_networks
            
            if service.get("build"):
                build_path = service.get("build", ".")
                if not os.path.isabs(build_path):
                    build_path = os.path.join(os.path.dirname(compose_path), build_path)
                build_path = os.path.normpath(build_path)
                if not os.path.exists(build_path):
                    raise ImageBuildError(f"构建路径不存在: {build_path}")
                logger.info("从 docker-compose 构建镜像，路径: %s", build_path)
                build_or_get_image(build_path, service["image"])
            
            container = create_container_from_service(service, app_config, resource_limits=resource_limits)
            containers_to_start.append((container, name))

        for container, service_name in containers_to_start:
            # 创建容器时设置定时器，不增加续期计数
            manager = get_container_manager()
            creation_meta = dict(meta or {})
            creation_meta.setdefault("source_path", compose_path)
            creation_meta.setdefault("container_uuid", container.name)
            creation_meta.setdefault("compose_project_id", compose_project_id)
            creation_meta.setdefault("compose_service_name", service_name)
            manager.set_timer(container.id, max_time, container_name=container.name, metadata=creation_meta)

        data = []
        for container, _service_name in containers_to_start:
            info = get_container_info(container)
            info.setdefault("compose_project_id", compose_project_id)
            data.append(info)
        return data[0] if len(data) == 1 else data
        
    except Exception as e:
        rollback_client = ensure_client()
        for container, _service_name in containers_to_start:
            try:
                get_container_manager().remove_container(container.id)
                container.remove(force=True)
            except Exception as container_cleanup_err:
                logger.warning("Compose 回滚容器失败: %s, err=%s", getattr(container, 'id', 'unknown'), container_cleanup_err)

        if rollback_client:
            for network_name in locals().get("created_networks", []):
                try:
                    rollback_client.networks.get(network_name).remove()
                except Exception as network_cleanup_err:
                    logger.warning("Compose 回滚网络失败: %s, err=%s", network_name, network_cleanup_err)

        logger.exception("Docker Compose启动失败")
        raise


def create_container_from_service(service: Dict, app_config: AppConfig = None, resource_limits: Optional[Dict[str, Any]] = None):
    """从服务配置创建并启动容器
    
    Args:
        service: Docker Compose服务配置字典
        app_config: 应用配置对象，默认使用全局配置
        
    Returns:
        docker.models.containers.Container: Docker容器对象
        
    Raises:
        DockerConnectionError: Docker客户端不可用时抛出
    """
    if app_config is None:
        app_config = default_config
    
    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")
    
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

    # 构建容器创建参数（使用公共函数）
    create_kwargs = build_container_create_kwargs(
        image=service["image"],
        name=container_name,
        ports=port_bindings,
        command=service.get("command"),
        environment=service.get("environment"),
        extra_labels=extra_labels,
        network=primary_network,
        network_mode=None if primary_network else "bridge",
        resource_limits=resource_limits,
        app_config=app_config
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
        manager.add_container(container.id, container)
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


def _ensure_compose_networks(client, compose_content: Dict[str, Any], compose_project_id: str) -> Tuple[Dict[str, str], List[str]]:
    """确保 compose 中定义的网络存在，并返回逻辑名到实际 Docker 网络名的映射。"""
    if client is None:
        raise DockerConnectionError("Docker客户端不可用")

    networks = compose_content.get("networks") or {}
    if not isinstance(networks, dict):
        return {}, []

    mapping: Dict[str, str] = {}
    created_networks: List[str] = []
    for network_key, network_cfg in networks.items():
        cfg = network_cfg if isinstance(network_cfg, dict) else {}
        external_cfg = cfg.get("external")

        if external_cfg:
            if isinstance(external_cfg, dict):
                resolved_name = external_cfg.get("name") or cfg.get("name") or str(network_key)
            else:
                resolved_name = cfg.get("name") or str(network_key)
            mapping[str(network_key)] = str(resolved_name)
            continue

        resolved_name = str(cfg.get("name") or f"{compose_project_id}_{network_key}")
        mapping[str(network_key)] = resolved_name

        existing = client.networks.list(names=[resolved_name])
        if existing:
            continue

        client.networks.create(
            resolved_name,
            driver=str(cfg.get("driver") or "bridge"),
            attachable=bool(cfg.get("attachable", False)),
            labels={
                "moegate.managed": "true",
                "moegate.compose_project_id": compose_project_id,
            },
        )
        created_networks.append(resolved_name)

    return mapping, created_networks


def _start_from_dockerfile_streaming(path: str, uid, cmd, min_port: int,
                                     max_port: int, max_time: int, env: Dict, tag,
                                     port_mappings: Optional[List[Tuple[str, int]]] = None,
                                     resource_limits: Optional[Dict[str, Any]] = None,
                                     meta=None, app_config: AppConfig = None):
    """从 Dockerfile 启动容器（流式版本）。

    Yields:
        str | dict: 日志行字符串；最后一个 yield 为容器信息字典。
    """
    if app_config is None:
        app_config = default_config

    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    # 确保有一个合法的镜像标签，避免 tag 为 None 时误用路径作为镜像名
    resolved_tag = tag or f"dynamic-container-{random.randint(100000, 999999)}"

    yield "正在构建镜像..."
    # 使用流式构建
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
        image=image.id, name=container_name, ports=ports,
        command=cmd, environment=env, resource_limits=resource_limits, app_config=app_config
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


def _start_from_compose_streaming(compose_path: str, uid, max_time: int, env: Dict,
                                  resource_limits: Optional[Dict[str, Any]] = None,
                                  app_config: AppConfig = None, meta=None):
    """从 Docker Compose 启动容器（流式版本）。

    Yields:
        str | dict | list: 日志行字符串；最后一个 yield 为容器信息字典或列表。
    """
    if app_config is None:
        app_config = default_config

    containers_to_start: List[Tuple[Any, str]] = []
    created_networks: List[str] = []

    try:
        with open(compose_path, "r", encoding='utf-8') as f:
            content = yaml.safe_load(f)

        compose_project_id = str(uid)
        client = ensure_client()
        compose_network_map, created_networks = _ensure_compose_networks(
            client=client, compose_content=content, compose_project_id=compose_project_id,
        )

        for name, service in content.get("services", {}).items():
            if len(content.get("services", {})) > 1:
                service_uuid = str(uuid.uuid4())
                service["container_name"] = service_uuid
            else:
                service["container_name"] = uid
            service["image"] = service.get("image", name)

            service_env = service.get("environment") or {}
            if isinstance(service_env, list):
                merged_env = {}
                for item in service_env:
                    if isinstance(item, str) and "=" in item:
                        key, value = item.split("=", 1)
                        merged_env[key] = value
                service_env = merged_env
            elif not isinstance(service_env, dict):
                service_env = {}
            merged_env = dict(service_env)
            merged_env.update(env or {})
            service["environment"] = merged_env
            service["ports"] = process_service_ports(service, app_config)
            service["_compose_project_id"] = compose_project_id
            service["_compose_service_name"] = name

            network_keys = _extract_service_network_keys(service)
            primary_network = compose_network_map.get(network_keys[0]) if network_keys else None
            extra_networks = [compose_network_map[key] for key in network_keys[1:] if key in compose_network_map]
            service["_primary_network"] = primary_network
            service["_extra_networks"] = extra_networks

            if service.get("build"):
                build_path = service.get("build", ".")
                if not os.path.isabs(build_path):
                    build_path = os.path.join(os.path.dirname(compose_path), build_path)
                build_path = os.path.normpath(build_path)
                if not os.path.exists(build_path):
                    raise ImageBuildError(f"构建路径不存在: {build_path}")
                yield f"[{name}] 开始构建镜像..."
                for line in build_or_get_image_streaming(build_path, service["image"]):
                    if line == "__IMAGE_READY__":
                        continue
                    yield f"[{name}] {line}"

            yield f"[{name}] 正在创建容器..."
            container = create_container_from_service(service, app_config, resource_limits=resource_limits)
            containers_to_start.append((container, name))
            yield f"[{name}] 容器已启动"

        for container, service_name in containers_to_start:
            manager = get_container_manager()
            creation_meta = dict(meta or {})
            creation_meta.setdefault("source_path", compose_path)
            creation_meta.setdefault("container_uuid", container.name)
            creation_meta.setdefault("compose_project_id", compose_project_id)
            creation_meta.setdefault("compose_service_name", service_name)
            manager.set_timer(container.id, max_time, container_name=container.name, metadata=creation_meta)

        data = []
        for container, _service_name in containers_to_start:
            info = get_container_info(container)
            info.setdefault("compose_project_id", compose_project_id)
            data.append(info)

        yield "所有服务启动完成"
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
    resolved_image = _resolve_image_reference(image, image_source)

    try:
        image_obj = client.images.get(resolved_image)
    except docker.errors.ImageNotFound:
        raise ImageBuildError(f"镜像不存在: {resolved_image}")
    except docker.errors.APIError as e:
        raise ImageBuildError(f"获取镜像失败: {e}")

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
        resource_limits=resource_limits,
        app_config=app_config,
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
    resolved_image = _resolve_image_reference(image, image_source)

    yield f"正在检查镜像: {resolved_image}"
    try:
        image_obj = client.images.get(resolved_image)
    except docker.errors.ImageNotFound:
        raise ImageBuildError(f"镜像不存在: {resolved_image}")
    except docker.errors.APIError as e:
        raise ImageBuildError(f"获取镜像失败: {e}")

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
        resource_limits=resource_limits,
        app_config=app_config,
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


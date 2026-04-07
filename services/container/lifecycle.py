"""容器生命周期管理"""
import os
import time
import uuid
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from config.settings import config as default_config, AppConfig
from core.exceptions import (
    DockerConnectionError,
    ContainerLimitExceededError,
    ValidationError,
    InvalidPathError,
)
from infra.docker import (
    ensure_client,
)
from utils.path_validator import (
    validate_path,
)
from utils.container_manager import get_container_manager
from core.events import get_event_bus
from services.container.builder import (
    start_container_from_source,
    start_container_from_source_streaming,
    start_from_image,
    start_from_image_streaming,
)
from services.container.info import _add_frp_mapping_info

logger = logging.getLogger(__name__)

_UUID_V4_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"4[0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-"
    r"[0-9a-fA-F]{12}$"
)


def _validate_uid(uid_raw: object) -> str:
    """仅允许 UUID v4，避免被用作任意容器名（安全边界）。"""
    if uid_raw is None:
        return ""
    uid = str(uid_raw).strip()
    if not uid:
        return ""
    if len(uid) > 64:
        raise ValidationError("uid 过长")
    if not _UUID_V4_RE.match(uid):
        raise ValidationError("uid 必须为 UUID v4（标准格式）")
    return uid


def _normalize_source_mode(data: Dict[str, Any]) -> str:
    source = str(data.get("source") or data.get("source_type") or "").strip().lower()
    path = str(data.get("path") or "").strip()
    image = str(data.get("image") or "").strip()

    if source and source not in ("path", "image"):
        raise ValidationError("source/source_type 仅支持 path 或 image")

    if path and image:
        raise ValidationError("path 与 image 不能同时提供")

    if source == "path" and not path:
        raise ValidationError("source=path 时必须提供 path")
    if source == "image" and not image:
        raise ValidationError("source=image 时必须提供 image")

    if source:
        return source
    if image:
        return "image"
    if path:
        return "path"
    raise ValidationError("缺少必要字段: path 或 image")


def _extract_resource_limits(data: Dict[str, Any]) -> Dict[str, Any]:
    resource_limits: Dict[str, Any] = {}

    memory_limit = data.get("memory_limit", data.get("mem_limit"))
    if memory_limit is not None:
        memory_limit = str(memory_limit).strip()
        if not memory_limit:
            raise ValidationError("memory_limit 不能为空")
        resource_limits["memory_limit"] = memory_limit

    cpu_limit_raw = data.get("cpu_limit")
    if cpu_limit_raw is not None:
        try:
            cpu_limit = float(cpu_limit_raw)
        except (ValueError, TypeError):
            raise ValidationError("cpu_limit 必须是数字")
        if cpu_limit <= 0:
            raise ValidationError("cpu_limit 必须大于 0")
        resource_limits["cpu_limit"] = cpu_limit

    cpu_shares_raw = data.get("cpu_shares")
    if cpu_shares_raw is not None:
        try:
            cpu_shares = int(cpu_shares_raw)
        except (ValueError, TypeError):
            raise ValidationError("cpu_shares 必须是整数")
        if cpu_shares < 0:
            raise ValidationError("cpu_shares 不能为负数")
        resource_limits["cpu_shares"] = cpu_shares

    return resource_limits


def _extract_port_mappings(data: Dict[str, Any]) -> List[Tuple[str, int]]:
    """解析显式端口映射。

    支持的输入格式：
    - 字符串："8080:80,8443:443" 或按行分隔
    - 数组： ["8080:80", "8443:443"]

    Returns:
        List[Tuple[str, int]]: [("80/tcp", 8080), ("443/tcp", 8443)]
    """
    raw = data.get("port_mappings")
    if raw is None:
        return []

    items: List[str] = []
    if isinstance(raw, str):
        normalized = raw.replace("\n", ",")
        items = [part.strip() for part in normalized.split(",") if part.strip()]
    elif isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text:
                items.append(text)
    else:
        raise ValidationError("port_mappings 必须是字符串或字符串数组")

    mappings: List[Tuple[str, int]] = []
    seen_host_ports = set()
    seen_container_ports = set()

    for item in items:
        if ":" not in item:
            raise ValidationError(f"port_mappings 条目格式错误: {item}，应为 host:container")

        host_raw, container_raw = item.split(":", 1)
        host_raw = host_raw.strip()
        container_raw = container_raw.strip().lower()

        try:
            host_port = int(host_raw)
        except (TypeError, ValueError):
            raise ValidationError(f"host 端口无效: {host_raw}")
        if host_port < 1 or host_port > 65535:
            raise ValidationError(f"host 端口超出范围: {host_port}")

        protocol = "tcp"
        container_port_raw = container_raw
        if "/" in container_raw:
            container_port_raw, protocol = container_raw.split("/", 1)
            protocol = protocol.strip().lower()
            if protocol not in ("tcp", "udp"):
                raise ValidationError(f"container 协议仅支持 tcp/udp: {container_raw}")

        try:
            container_port_num = int(container_port_raw)
        except (TypeError, ValueError):
            raise ValidationError(f"container 端口无效: {container_raw}")
        if container_port_num < 1 or container_port_num > 65535:
            raise ValidationError(f"container 端口超出范围: {container_port_num}")

        container_port = f"{container_port_num}/{protocol}"
        if host_port in seen_host_ports:
            raise ValidationError(f"host 端口重复: {host_port}")
        if container_port in seen_container_ports:
            raise ValidationError(f"container 端口重复: {container_port}")

        seen_host_ports.add(host_port)
        seen_container_ports.add(container_port)
        mappings.append((container_port, host_port))

    return mappings


def extract_and_validate_data(data: Dict[str, Any], app_config: AppConfig = None) -> Dict[str, Any]:
    """提取并验证容器启动参数
    
    Args:
        data: 原始请求数据字典
        app_config: 应用配置对象，默认使用全局配置
        
    Returns:
        Dict[str, Any]: 验证后的参数字典
        
    Raises:
        ValidationError: 参数验证失败时抛出
    """
    if app_config is None:
        app_config = default_config
    
    source_mode = _normalize_source_mode(data)
    
    # 如果没有指定 uid，使用 UUID（标准格式，带连字符）
    uid = _validate_uid(data.get("uid")) or str(uuid.uuid4())
    
    resource_limits = _extract_resource_limits(data)
    port_mappings = _extract_port_mappings(data)

    # 可选：指定容器加入某个 Docker network（用于容器间互通/隔离/DNS）
    network = data.get("network")
    if network is not None:
        network = str(network).strip()
        if not network:
            raise ValidationError("network 不能为空")
        if len(network) > 255:
            raise ValidationError("network 过长")

    has_min_port = data.get("min_port") is not None
    has_max_port = data.get("max_port") is not None
    if port_mappings and (has_min_port or has_max_port):
        raise ValidationError("port_mappings 与 min_port/max_port 只能二选一")

    min_port = data.get("min_port", app_config.MIN_PORT)
    max_port = data.get("max_port", app_config.MAX_PORT)

    if min_port >= max_port:
        raise ValidationError("min_port 必须小于 max_port")

    normalized_path: Optional[str] = None
    normalized_image: Optional[str] = None
    if source_mode == "path":
        normalized_path = str(data.get("path") or "").strip()
    else:
        normalized_image = str(data.get("image") or "").strip()
    
    return {
        "source_mode": source_mode,
        "path": normalized_path,
        "image": normalized_image,
        "cmd": data.get("command"),
        "min_port": min_port,
        "max_port": max_port,
        "max_time": data.get("max_time", app_config.MAX_TIME),
        "tag": data.get("tag"),
        "uid": uid,
        "env": data.get("env", {}),
        "meta": data.get("_meta", {}),
        "resource_limits": resource_limits,
        "port_mappings": port_mappings,
        "network": network,
    }


def get_docker_file_path(path: str) -> str:
    """获取Dockerfile或docker-compose文件路径
    
    按优先级顺序查找：docker-compose.yaml > docker-compose.yml > Dockerfile
    
    Args:
        path: 目录路径
        
    Returns:
        str: Docker配置文件的完整路径
        
    Raises:
        ValueError: 目录中不存在任何Docker配置文件时抛出
    """
    filenames = ["docker-compose.yaml", "docker-compose.yml", "Dockerfile"]
    
    for filename in filenames:
        file_path = os.path.join(path, filename)
        if os.path.isfile(file_path):
            return file_path
    
    raise InvalidPathError("未找到 Dockerfile 或 Docker Compose 文件")


def start_container(data: Dict[str, Any], app_config: AppConfig = None) -> Dict[str, Any]:
    """启动容器
    
    Args:
        data: 包含容器配置的字典，必须包含'path'字段
        app_config: 应用配置对象，默认使用全局配置
        
    Returns:
        Dict[str, Any]: 容器信息字典或字典列表
        
    Raises:
        ContainerServiceError: 容器服务相关错误
    """
    if app_config is None:
        app_config = default_config
    
    client = ensure_client()
    if not client:
        raise DockerConnectionError()
    
    manager = get_container_manager()
    if not manager.check_and_reserve(app_config.MAX_CONTAINERS):
        raise ContainerLimitExceededError(len(manager.get_container_ids()), app_config.MAX_CONTAINERS)

    try:
        params = extract_and_validate_data(data, app_config)

        if params["source_mode"] == "image":
            response_data = start_from_image(app_config=app_config, **params)
        else:
            params['path'] = validate_path(params['path'])
            docker_file_path = get_docker_file_path(params['path'])
            response_data = start_container_from_source(docker_file_path, app_config=app_config, **params)
    except Exception:
        manager.release_reservation()
        raise
    
    # 通过事件机制通知FRP服务创建配置
    if app_config.ENABLE_FRP and response_data:
        try:
            proxy_type = data.get("type")
            if isinstance(response_data, list):
                for container_info in response_data:
                    if isinstance(container_info, dict):
                        if proxy_type:
                            container_info['type'] = proxy_type
                        logger.debug("发布 container.created 事件 (列表): %s", container_info.get('container_name'))
                        get_event_bus().publish('container.created', container_info)
                        
                        # 解析代理配置获取映射地址
                        _add_frp_mapping_info(container_info, app_config)
            elif isinstance(response_data, dict):
                if proxy_type:
                    response_data['type'] = proxy_type
                logger.debug("发布 container.created 事件 (字典): %s, ports: %s", response_data.get('container_name'), response_data.get('ports'))
                get_event_bus().publish('container.created', response_data)
                
                # 解析代理配置获取映射地址
                _add_frp_mapping_info(response_data, app_config)
        except Exception as frp_err:
            logger.warning("FRP配置失败: %s", frp_err)
            logger.exception("FRP配置异常详情")
    elif not app_config.ENABLE_FRP:
        logger.debug("FRP未启用，跳过FRP配置")
    elif not response_data:
        logger.warning("响应数据为空，无法创建FRP配置")
    
    return response_data


def start_container_streaming(data, app_config=None):
    """启动容器（流式版本），以生成器方式返回构建日志。

    Yields:
        str | dict: 日志行或最终容器信息字典。
    """
    if app_config is None:
        app_config = default_config

    client = ensure_client()
    if not client:
        raise DockerConnectionError()

    manager = get_container_manager()
    if not manager.check_and_reserve(app_config.MAX_CONTAINERS):
        raise ContainerLimitExceededError(len(manager.get_container_ids()), app_config.MAX_CONTAINERS)

    response_data = None
    try:
        params = extract_and_validate_data(data, app_config)

        if params["source_mode"] == "image":
            stream_iter = start_from_image_streaming(app_config=app_config, **params)
        else:
            params['path'] = validate_path(params['path'])
            docker_file_path = get_docker_file_path(params['path'])
            stream_iter = start_container_from_source_streaming(docker_file_path, app_config=app_config, **params)
    except Exception:
        manager.release_reservation()
        raise

    for item in stream_iter:
        if isinstance(item, (dict, list)):
            response_data = item
        else:
            yield item

    if app_config.ENABLE_FRP and response_data:
        try:
            proxy_type = data.get("type")
            if isinstance(response_data, list):
                for ci in response_data:
                    if isinstance(ci, dict):
                        if proxy_type:
                            ci['type'] = proxy_type
                        get_event_bus().publish('container.created', ci)
                        _add_frp_mapping_info(ci, app_config)
            elif isinstance(response_data, dict):
                if proxy_type:
                    response_data['type'] = proxy_type
                get_event_bus().publish('container.created', response_data)
                _add_frp_mapping_info(response_data, app_config)
        except Exception as frp_err:
            logger.warning("FRP配置失败: %s", frp_err)

    yield response_data


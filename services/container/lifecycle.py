"""容器生命周期管理"""
import os
import uuid
import logging
import re
import yaml
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
from services.container.builder import (
    start_container_from_source,
    start_container_from_source_streaming,
)
from services.network import assert_managed_network
from services.container.single_container import (
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


def _validate_host_port_range(host_port: int, min_port: int, max_port: int) -> None:
    if host_port < min_port or host_port > max_port:
        raise ValidationError(
            f"host 端口 {host_port} 必须在 {min_port}-{max_port} 范围内"
        )


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


def _extract_env(data: Dict[str, Any], app_config: AppConfig = None) -> Dict[str, str]:
    """提取并规范化全局环境变量。"""
    if app_config is None:
        app_config = default_config

    raw = data.get("env", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValidationError("env 必须是对象")

    max_keys = int(getattr(app_config, "MAX_CONTAINER_ENV_KEYS", 64) or 64)
    max_value_len = int(getattr(app_config, "MAX_CONTAINER_ENV_VALUE_LEN", 4096) or 4096)
    if len(raw) > max_keys:
        raise ValidationError(f"env 键数量不能超过 {max_keys}")

    normalized: Dict[str, str] = {}
    for key, value in raw.items():
        key_text = str(key)
        if len(key_text) > 256:
            raise ValidationError("env 键过长")
        value_text = "" if value is None else str(value)
        if len(value_text) > max_value_len:
            raise ValidationError(f"env 值长度不能超过 {max_value_len}")
        normalized[key_text] = value_text
    return normalized


def _validate_max_time(raw: object, app_config: AppConfig) -> int:
    """校验容器存活时间，限制在配置允许范围内。"""
    if raw is None:
        return int(app_config.MAX_TIME)
    try:
        max_time = int(raw)
    except (TypeError, ValueError):
        raise ValidationError("max_time 必须是整数")
    if max_time <= 0:
        raise ValidationError("max_time 必须大于 0")
    if max_time > int(app_config.MAX_TIME):
        raise ValidationError(f"max_time 不能超过 {app_config.MAX_TIME}")
    return max_time


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
        network = assert_managed_network(network)

    max_time = _validate_max_time(data.get("max_time"), app_config)
    has_min_port = data.get("min_port") is not None
    has_max_port = data.get("max_port") is not None
    if port_mappings and (has_min_port or has_max_port):
        raise ValidationError("port_mappings 与 min_port/max_port 只能二选一")

    allowed_min = int(app_config.MIN_PORT)
    allowed_max = int(app_config.MAX_PORT)
    min_port = int(data.get("min_port", allowed_min))
    max_port = int(data.get("max_port", allowed_max))

    if min_port < allowed_min:
        min_port = allowed_min
    if max_port > allowed_max:
        max_port = allowed_max

    if min_port >= max_port:
        raise ValidationError("min_port 必须小于 max_port")

    if port_mappings:
        for _, host_port in port_mappings:
            _validate_host_port_range(host_port, allowed_min, allowed_max)

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
        "max_time": max_time,
        "tag": data.get("tag"),
        "uid": uid,
        "env": _extract_env(data, app_config),
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


def _creation_slot_count(params: Dict[str, Any]) -> int:
    if params.get("source_mode") == "image":
        return 1

    path = params.get("path")
    if not path:
        return 1

    validated_path = validate_path(path)
    docker_file_path = get_docker_file_path(validated_path)

    if not docker_file_path.endswith((".yaml", ".yml")):
        return 1

    with open(docker_file_path, "r", encoding="utf-8") as handle:
        content = yaml.safe_load(handle) or {}
    services = content.get("services") or {}
    if not isinstance(services, dict) or not services:
        return 1
    return len(services)


def _normalize_container_results(response_data):
    if isinstance(response_data, list):
        return [item for item in response_data if isinstance(item, dict)]
    if isinstance(response_data, dict):
        return [response_data]
    return []


def _apply_frp_configs(response_data, request_data: Dict[str, Any], app_config: AppConfig) -> None:
    """创建后为容器（或 Compose 多 service 列表）注册 FRP 并回填映射信息。"""
    if not app_config.ENABLE_FRP:
        logger.debug("FRP未启用，跳过FRP配置")
        return

    containers = _normalize_container_results(response_data)
    if not containers:
        logger.warning("响应数据为空，无法创建FRP配置")
        return

    proxy_type = request_data.get("type")
    if proxy_type:
        for container_info in containers:
            container_info["type"] = proxy_type

    try:
        from services.frp.event_handler import create_configs_batch

        create_configs_batch(containers)
        for container_info in containers:
            _add_frp_mapping_info(container_info, app_config)
    except Exception as frp_err:
        logger.warning("FRP配置失败: %s", frp_err)
        logger.exception("FRP配置异常详情")


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
    params = extract_and_validate_data(data, app_config)
    slots = _creation_slot_count(params)

    if not manager.check_and_reserve(app_config.MAX_CONTAINERS, slots=slots):
        raise ContainerLimitExceededError(manager.get_usage_count(), app_config.MAX_CONTAINERS)

    try:
        if params["source_mode"] == "image":
            response_data = start_from_image(app_config=app_config, **params)
        else:
            params['path'] = validate_path(params['path'])
            docker_file_path = get_docker_file_path(params['path'])
            response_data = start_container_from_source(docker_file_path, app_config=app_config, **params)
    except Exception:
        manager.release_reservation(slots=slots)
        raise

    _apply_frp_configs(response_data, data, app_config)
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
    params = extract_and_validate_data(data, app_config)
    slots = _creation_slot_count(params)

    if not manager.check_and_reserve(app_config.MAX_CONTAINERS, slots=slots):
        raise ContainerLimitExceededError(manager.get_usage_count(), app_config.MAX_CONTAINERS)

    response_data = None
    try:
        if params["source_mode"] == "image":
            stream_iter = start_from_image_streaming(app_config=app_config, **params)
        else:
            params['path'] = validate_path(params['path'])
            docker_file_path = get_docker_file_path(params['path'])
            stream_iter = start_container_from_source_streaming(docker_file_path, app_config=app_config, **params)

        for item in stream_iter:
            if isinstance(item, (dict, list)):
                response_data = item
            else:
                yield item
    except Exception:
        manager.release_reservation(slots=slots)
        raise

    _apply_frp_configs(response_data, data, app_config)
    yield response_data


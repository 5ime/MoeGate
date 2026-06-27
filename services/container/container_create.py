"""容器创建公共辅助函数。"""
import logging
from typing import Dict, Any, Optional, List, Tuple

import docker

from config.settings import config as default_config, AppConfig
from services.container.port_manager import get_port_info
from utils.creation_meta import build_creation_meta_labels

logger = logging.getLogger(__name__)

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
    app_config: AppConfig = None,
    ttl_seconds: Optional[int] = None,
    creation_meta: Optional[Dict[str, Any]] = None,
    volumes: Optional[Dict[str, Dict[str, str]]] = None,
    privileged: bool = False,
    cap_add: Optional[List[str]] = None,
    cap_drop: Optional[List[str]] = None,
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
    if ttl_seconds is not None and ttl_seconds > 0:
        from utils.container_manager import ContainerManager, EXPIRES_AT_LABEL
        labels[EXPIRES_AT_LABEL] = str(ContainerManager.compute_expires_at(ttl_seconds))
    if extra_labels:
        labels.update(extra_labels)
    labels.update(build_creation_meta_labels(creation_meta))

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

    if volumes:
        create_kwargs["volumes"] = volumes
    if privileged:
        create_kwargs["privileged"] = True
    if cap_add:
        create_kwargs["cap_add"] = [str(item) for item in cap_add if str(item).strip()]
    if cap_drop:
        create_kwargs["cap_drop"] = [str(item) for item in cap_drop if str(item).strip()]
    
    return create_kwargs


"""容器端口管理"""
import logging
from typing import Dict
from config.settings import config as default_config, AppConfig
from core.exceptions import PortUnavailableError
from utils.port_utils import find_available_port
from utils.container_manager import get_container_manager

logger = logging.getLogger(__name__)


def get_container_ports(image, min_port: int, max_port: int, app_config: AppConfig = None) -> Dict[str, tuple]:
    """获取容器端口映射
    
    Args:
        image: Docker镜像对象
        min_port: 最小端口号
        max_port: 最大端口号
        app_config: 应用配置对象，默认使用全局配置
        
    Returns:
        Dict[str, tuple]: 端口绑定字典，格式为 {容器端口: (None, 主机端口)}
        
    Raises:
        PortUnavailableError: 端口不可用时抛出
    """
    if app_config is None:
        app_config = default_config
    
    manager = get_container_manager()
    exposed = image.attrs.get("Config", {}).get("ExposedPorts", {})
    bindings = {}
    
    if not exposed:
        logger.warning("镜像没有暴露任何端口，将使用默认端口映射")
        exposed = {"80/tcp": {}}
    
    for port in exposed:
        avail_port = find_available_port(min_port, max_port, manager.get_all_containers())
        if avail_port:
            bindings[port] = (None, avail_port)
        else:
            raise PortUnavailableError(f"端口范围 {min_port}-{max_port} 内没有可用端口用于映射 {port}")
    
    return bindings


def process_service_ports(service: Dict, app_config: AppConfig = None) -> list:
    """处理服务端口映射
    
    Args:
        service: Docker Compose服务配置字典
        app_config: 应用配置对象，默认使用全局配置
        
    Returns:
        list: 端口映射列表，格式为 ["主机端口:容器端口", ...]
        
    Raises:
        PortUnavailableError: 端口不可用时抛出
    """
    if app_config is None:
        app_config = default_config
    
    manager = get_container_manager()
    new_ports = []
    for port in service.get("ports", []):
        if ":" in port:
            _, container_port = port.split(":", 1)
        else:
            container_port = port
        available_port = find_available_port(app_config.MIN_PORT, app_config.MAX_PORT, manager.get_all_containers())
        if available_port:
            new_ports.append(f"{available_port}:{container_port}")
        else:
            raise PortUnavailableError()
    return new_ports


def get_port_info(container) -> Dict[str, str]:
    """获取容器端口信息
    
    Args:
        container: Docker容器对象
        
    Returns:
        Dict[str, str]: 端口映射字典，格式为 {容器端口: 主机端口}
    """
    try:
        attrs = getattr(container, '_attrs', None) or container.attrs
        ports = attrs.get("NetworkSettings", {}).get("Ports", {})
        info = {}

        for port, mappings in ports.items():
            if mappings:
                for mapping in mappings:
                    if isinstance(mapping, dict) and mapping.get("HostIp") == "0.0.0.0":
                        info[port] = mapping.get("HostPort", "")
                        break

        return info
    except Exception as e:
        logger.debug("获取容器端口信息失败: %s", e)
        return {}


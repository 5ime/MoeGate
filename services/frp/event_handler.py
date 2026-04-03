"""FRP事件处理器"""
import logging
import time
from typing import Dict, Any, Optional
from config import config
from utils.container_manager import get_container_manager
from services.frp.parser import list_proxies
from services.frp.proxy_manager import add_proxy_config
from services.frp.utils import build_proxy_config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)

# FRP配置重试参数
FRP_CONFIG_MAX_RETRIES = 3
FRP_CONFIG_RETRY_DELAY = 1.0  # 秒


def _find_available_remote_port(
    preferred_port: int, 
    container_name: str,
    min_port: int = None,
    max_port: int = None
) -> int:
    """查找可用的远程端口
    
    如果首选端口被占用，尝试查找其他可用端口。
    
    Args:
        preferred_port: 首选端口
        container_name: 容器名称
        min_port: 最小端口号（可选）
        max_port: 最大端口号（可选）
        
    Returns:
        int: 可用的远程端口号
    """
    existing_proxies = list_proxies()
    used_ports = {
        proxy.get('remotePort') 
        for proxy in existing_proxies 
        if proxy.get('remotePort') and proxy.get('name') != container_name
    }
    
    # 如果首选端口可用，直接返回
    if preferred_port not in used_ports:
        return preferred_port
    
    # 如果首选端口被占用，尝试查找其他端口
    logger.warning(
        "端口 %s 已被其他代理使用，"
        "尝试为容器 %s 查找其他可用端口",
        preferred_port, container_name
    )
    
    # 如果提供了端口范围，在范围内查找
    if min_port is not None and max_port is not None:
        for port in range(min_port, max_port + 1):
            if port not in used_ports and port != preferred_port:
                logger.info("为容器 %s 选择备用端口: %s", container_name, port)
                return port
    
    # 如果没有找到备用端口，仍然使用首选端口（但会记录警告）
    logger.warning(
        "未找到备用端口，容器 %s 将使用可能冲突的端口 %s",
        container_name, preferred_port
    )
    return preferred_port


def create_config(info: Dict[str, Any]) -> None:
    """为容器创建并更新FRP配置（带重试机制）
    
    如果FRP配置创建失败，会进行重试。即使最终失败，也不会影响容器创建。
    
    Args:
        info: 容器信息字典，包含container_name和ports
    """
    container_name = info.get("container_name")
    if not container_name:
        logger.error("无效的容器名称，跳过FRP配置")
        return

    ports = info.get("ports", {})
    logger.debug("收到 container.created 事件，容器: %s, 端口: %s", container_name, ports)
    
    # 获取本地端口
    local_port = None
    if ports:
        first_port_key = list(ports.keys())[0]
        local_port = ports[first_port_key]
        logger.debug("容器 %s 使用端口 %s -> %s", container_name, first_port_key, local_port)
    else:
        logger.error("容器 %s 没有映射任何端口，跳过FRP配置", container_name)
        return

    # 验证端口号
    try:
        local_port_int = int(local_port)
    except (ValueError, TypeError):
        logger.error("无效的端口号: %s，跳过FRP配置", local_port)
        return
    
    # 查找可用的远程端口（避免冲突）
    try:
        remote_port = _find_available_remote_port(
            local_port_int,
            container_name,
            min_port=config.MIN_PORT if hasattr(config, 'MIN_PORT') else None,
            max_port=config.MAX_PORT if hasattr(config, 'MAX_PORT') else None
        )
    except Exception as e:
        logger.warning("查找可用端口时发生错误: %s，使用首选端口 %s", e, local_port_int)
        remote_port = local_port_int
    
    # 构建代理配置
    try:
        user_type = info.get("type")
        container_uuid = info.get("container_uuid") or container_name
        proxy_config, type_source = build_proxy_config(
            container_name, 
            local_port_int, 
            remote_port, 
            user_type, 
            container_uuid
        )
        logger.debug("构建的FRP代理配置: %s, 类型来源: %s", proxy_config, type_source)
    except Exception as e:
        logger.error("构建FRP代理配置失败: %s，跳过FRP配置", e)
        return
    
    # 重试创建FRP配置
    last_error = None
    for attempt in range(1, FRP_CONFIG_MAX_RETRIES + 1):
        try:
            success, msg = add_proxy_config(proxy_config)
            if success:
                proxy_type = proxy_config['type'].upper()
                if proxy_config.get('customDomains'):
                    domain = proxy_config['customDomains'][0]
                    access_url = f"http://{domain}"
                    if config.FRP_VHOST_HTTP_PORT and config.FRP_VHOST_HTTP_PORT != 80:
                        access_url += f":{config.FRP_VHOST_HTTP_PORT}"
                    logger.info(
                        "成功为容器 %s 创建FRP配置 (%s, 域名: %s, 访问地址: %s)",
                        container_name, proxy_type, domain, access_url
                    )
                else:
                    access_url = f"{config.FRP_SERVER_ADDR}:{remote_port}"
                    logger.info(
                        "成功为容器 %s 创建FRP配置 (%s, 端口: %s -> %s, 访问地址: %s)",
                        container_name, proxy_type, local_port_int, remote_port, access_url
                    )
                return  # 成功，退出
            else:
                last_error = msg
                logger.warning(
                    "创建FRP配置失败 (尝试 %s/%s): %s",
                    attempt, FRP_CONFIG_MAX_RETRIES, msg
                )
        except FRPConfigError as e:
            last_error = e.message
            logger.warning(
                "创建FRP配置时发生FRP配置错误 (尝试 %s/%s): %s",
                attempt, FRP_CONFIG_MAX_RETRIES, e.message
            )
        except Exception as e:
            last_error = str(e)
            logger.warning(
                    "创建FRP配置时发生未知错误 (尝试 %s/%s): %s",
                    attempt, FRP_CONFIG_MAX_RETRIES, e
                )
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < FRP_CONFIG_MAX_RETRIES:
            time.sleep(FRP_CONFIG_RETRY_DELAY * attempt)  # 指数退避
    
    # 所有重试都失败，记录错误但不抛出异常（不影响容器创建）
    logger.error(
        "为容器 %s 创建FRP配置失败，已重试 %s 次。最后错误: %s。容器已创建，但FRP配置未生效，可能需要手动配置。",
        container_name, FRP_CONFIG_MAX_RETRIES, last_error
    )


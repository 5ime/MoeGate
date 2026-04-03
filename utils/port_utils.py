"""端口工具函数"""

import logging
import random
import threading
import socket
from typing import Optional, Dict, Set

logger = logging.getLogger(__name__)

# 全局端口分配锁，确保线程安全
_port_allocation_lock = threading.Lock()
# 正在分配的端口集合，用于防止并发分配相同端口
_allocating_ports: Set[int] = set()


def _collect_used_ports(containers: dict) -> Set[int]:
    """收集已使用的端口
    
    Args:
        containers: 当前容器字典
        
    Returns:
        Set[int]: 已使用的端口集合
    """
    used_ports = set()
    try:
        for container in containers.values():
            if hasattr(container, 'attrs'):
                # 从容器属性获取端口映射
                ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
                for port_str, mappings in ports.items():
                    if mappings:
                        for mapping in mappings:
                            if isinstance(mapping, dict):
                                host_port = mapping.get("HostPort")
                                if host_port:
                                    try:
                                        used_ports.add(int(host_port))
                                    except (ValueError, TypeError):
                                        pass
            # 兼容旧版本：从ports属性获取
            elif hasattr(container, 'ports') and container.ports:
                for port in container.ports.keys():
                    try:
                        port_num = int(port.split("/")[0])
                        used_ports.add(port_num)
                    except (ValueError, IndexError, AttributeError):
                        pass
    except Exception as e:
        logger.warning("收集已使用端口时出错: %s", e)
    
    return used_ports


def _check_port_available(port: int) -> bool:
    """检查端口是否可用（通过socket测试）
    
    Args:
        port: 端口号
        
    Returns:
        bool: 端口是否可用
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        # connect_ex返回0表示端口被占用
        return result != 0
    except Exception:
        # 如果检查失败，保守处理为不可用（避免端口冲突导致后续创建失败）
        return False


def find_available_port(
    min_port: int, 
    max_port: int, 
    containers: dict, 
    max_attempts: int = 100
) -> Optional[int]:
    """寻找可用端口（线程安全，带端口冲突检测）
    
    使用全局锁确保端口分配的原子性，防止并发分配相同端口。
    
    Args:
        min_port: 最小端口号
        max_port: 最大端口号
        containers: 当前容器字典
        max_attempts: 最大尝试次数，默认100次
        
    Returns:
        Optional[int]: 可用端口号或None
    """
    if min_port >= max_port:
        logger.error("端口范围无效: %s >= %s", min_port, max_port)
        return None
    
    # 使用锁保护整个分配过程
    with _port_allocation_lock:
        # 收集已使用的端口
        used_ports = _collect_used_ports(containers)
        # 合并正在分配的端口
        used_ports.update(_allocating_ports)
        
        port_range_size = max_port - min_port + 1
        if len(used_ports) >= port_range_size:
            logger.error(
                "没有可用端口 (范围: %s-%s, "
                "已使用: %s, 正在分配: %s)",
                min_port, max_port, len(used_ports), len(_allocating_ports)
            )
            return None
        
        # 随机探测而非生成完整 set，对大范围更高效
        attempts = min(max_attempts, port_range_size - len(used_ports))
        for _ in range(attempts):
            port = random.randint(min_port, max_port)
            if port in used_ports:
                continue
            # 检查端口是否真的可用（socket测试）
            if _check_port_available(port):
                # 标记为正在分配
                _allocating_ports.add(port)
                logger.debug("分配端口: %s", port)
                return port
            used_ports.add(port)  # 标记为不可用，避免重复探测
        
        # 如果所有端口都不可用，返回None
        logger.error("端口范围 %s-%s 内没有可用端口", min_port, max_port)
        return None


def release_port(port: int) -> None:
    """释放端口（从正在分配的集合中移除）
    
    Args:
        port: 要释放的端口号
    """
    with _port_allocation_lock:
        _allocating_ports.discard(port)
        logger.debug("释放端口: %s", port)


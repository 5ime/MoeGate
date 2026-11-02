"""端口工具函数"""

import logging
import random
import threading
import socket
import time
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

_port_allocation_lock = threading.Lock()
# 已分配、但容器尚未真正绑定的端口 -> 分配时刻。既用于并发互斥，
# 也作为异常路径漏掉 release_port 时的兜底（超期自动回收）。
_allocating_ports: Dict[int, float] = {}
# 探测发现被本进程之外占用的端口 -> 记录时刻，短期内不必反复重试
_blocked_ports: Dict[int, float] = {}
_synced_host_ports: Set[int] = set()

_RESERVATION_TTL_SECONDS = 600


def _prune_reservations(now: Optional[float] = None) -> None:
    """清理超期的预留/占用标记（调用方需持有 _port_allocation_lock）。"""
    now = time.time() if now is None else now
    cutoff = now - _RESERVATION_TTL_SECONDS
    for holder in (_allocating_ports, _blocked_ports):
        expired = [port for port, at in holder.items() if at < cutoff]
        for port in expired:
            del holder[port]


def sync_host_ports_from_docker(ports: Set[int]) -> None:
    """更新从 Docker 扫描到的宿主机端口集合（reconcile 时调用）。"""
    global _synced_host_ports
    with _port_allocation_lock:
        _synced_host_ports = set(ports)
    logger.debug("已同步 Docker 宿主机端口: %d 个", len(ports))


def collect_host_ports_from_containers(containers) -> Set[int]:
    """从容器列表收集已映射的宿主机端口。"""
    used: Set[int] = set()
    for container in containers:
        used.update(extract_host_ports_from_container(container))
    return used


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
            used_ports.update(extract_host_ports_from_container(container))
    except Exception as e:
        logger.warning("收集已使用端口时出错: %s", e)

    return used_ports


def _check_port_available(port: int) -> bool:
    """检查端口是否可绑定（与 Docker 默认 0.0.0.0 映射一致）。"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", int(port)))  # nosec B104
        return True
    except OSError:
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def _reserve_candidate(min_port: int, max_port: int, containers: dict, tried: Set[int]) -> Optional[int]:
    """在锁内挑一个候选端口并登记预留（不做 syscall）。"""
    with _port_allocation_lock:
        _prune_reservations()

        used_ports = _collect_used_ports(containers)
        used_ports.update(_synced_host_ports)
        used_ports.update(_allocating_ports)
        used_ports.update(_blocked_ports)
        used_ports.update(tried)

        port_range_size = max_port - min_port + 1
        if len(used_ports) >= port_range_size:
            logger.error(
                "没有可用端口 (范围: %s-%s, 已使用: %s, 正在分配: %s)",
                min_port, max_port, len(used_ports), len(_allocating_ports),
            )
            return None

        # 随机起点 + 线性扫描：最多把范围走一遍就能给出结论，
        # 避免纯随机在端口池较满时反复命中已占用的端口。
        start = random.randint(min_port, max_port)
        for offset in range(port_range_size):
            port = min_port + ((start - min_port + offset) % port_range_size)
            if port in used_ports:
                continue
            _allocating_ports[port] = time.time()
            return port
    return None


def find_available_port(
    min_port: int,
    max_port: int,
    containers: dict,
    max_attempts: int = 100
) -> Optional[int]:
    """寻找可用端口（线程安全，带端口冲突检测）

    并发安全靠"预留"实现：候选端口在进入下一步之前就登记到 `_allocating_ports`，
    其他线程不会选中它。最慢的一步（socket 探测绑定）放在锁外执行，
    避免一个线程做系统调用时把所有分配请求都堵住。

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

    port_range_size = max_port - min_port + 1
    attempts = max(1, min(int(max_attempts), port_range_size))
    tried: Set[int] = set()

    for _ in range(attempts):
        port = _reserve_candidate(min_port, max_port, containers, tried)
        if port is None:
            return None

        if _check_port_available(port):
            logger.debug("分配端口: %s", port)
            return port

        # 端口实际被占用（多半是本进程之外的程序）：撤销预留并短期拉黑
        with _port_allocation_lock:
            _allocating_ports.pop(port, None)
            _blocked_ports[port] = time.time()
        tried.add(port)

    logger.error("端口范围 %s-%s 内没有可用端口", min_port, max_port)
    return None


def release_port(port: int) -> None:
    """释放端口（从正在分配的集合中移除）

    Args:
        port: 要释放的端口号
    """
    with _port_allocation_lock:
        _allocating_ports.pop(port, None)
        logger.debug("释放端口: %s", port)


def extract_host_ports_from_container(container) -> Set[int]:
    """从容器对象提取已映射的宿主机端口。"""
    attrs = getattr(container, "attrs", None) or {}
    ports = ((attrs.get("NetworkSettings") or {}).get("Ports") or {})
    used: Set[int] = set()
    for mappings in ports.values():
        if not mappings:
            continue
        for mapping in mappings:
            if isinstance(mapping, dict):
                host_port = mapping.get("HostPort")
                if host_port:
                    try:
                        used.add(int(host_port))
                    except (TypeError, ValueError):
                        pass
    return used


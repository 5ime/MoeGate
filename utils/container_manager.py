"""容器管理器 - 封装容器生命周期和状态管理"""

import threading
import logging
import time
from typing import Dict, Optional, Callable, List, Any
from docker.models.containers import Container
from config import config
from core.exceptions import MaxRenewTimesExceededError

logger = logging.getLogger(__name__)


class ContainerManager:
    """容器管理器：缓存容器对象、管理到期销毁与续期。"""
    
    def __init__(self):
        self._containers: Dict[str, Container] = {}
        self._timers: Dict[str, threading.Timer] = {}
        self._counts: Dict[str, int] = {}
        self._containers_lock = threading.Lock()
        self._timers_lock = threading.Lock()
        self._count_lock = threading.Lock()
        self._destroy_callbacks: List[Callable[[str], None]] = []
    
    def register_destroy_callback(self, callback: Callable[[str], None]):
        """注册销毁回调（参数为 container_id）。"""
        self._destroy_callbacks.append(callback)
    
    def add_container(self, container_id: str, container: Container):
        """缓存容器对象（同时清理预留占位符）。"""
        with self._containers_lock:
            # 清理预留占位符
            pid = getattr(self, '_reserved_placeholder', None)
            if pid and pid in self._containers:
                self._containers.pop(pid, None)
                self._reserved_placeholder = None
            self._containers[container_id] = container
    
    def get_container(self, container_id: str) -> Optional[Container]:
        """获取容器对象（不存在则返回 None）。"""
        with self._containers_lock:
            return self._containers.get(container_id)
    
    def remove_container(self, container_id: str) -> Optional[Container]:
        """移除并返回容器对象（不存在则返回 None）。"""
        with self._containers_lock:
            return self._containers.pop(container_id, None)
    
    def get_all_containers(self) -> Dict[str, Container]:
        """获取容器字典副本。"""
        with self._containers_lock:
            return dict(self._containers)
    
    def get_container_ids(self) -> List[str]:
        """获取所有容器 ID。"""
        with self._containers_lock:
            return list(self._containers.keys())
    
    def check_and_reserve(self, max_containers: int) -> bool:
        """原子检查容器数是否超限并预留一个名额（解决 TOCTOU 竞态）。

        Returns:
            True 表示预留成功（调用方可继续创建容器）。
        """
        with self._containers_lock:
            if len(self._containers) >= max_containers:
                return False
            # 用占位值预留名额，add_container 时会覆盖
            placeholder_id = f"__reserved_{id(threading.current_thread())}_{threading.get_ident()}"
            self._containers[placeholder_id] = None  # type: ignore[assignment]
            self._reserved_placeholder = placeholder_id
            return True

    def release_reservation(self):
        """释放预留名额（创建失败时回滚）。"""
        with self._containers_lock:
            pid = getattr(self, '_reserved_placeholder', None)
            if pid and pid in self._containers:
                self._containers.pop(pid, None)
    
    def register_container(self, container: Container, max_time: int, metadata: Optional[Dict[str, Any]] = None):
        """登记容器并设置到期销毁（进程内定时器）。"""
        self.add_container(container.id, container)
        self.set_timer(container.id, max_time, container_name=container.name, metadata=metadata)

    def _set_local_timer(self, container_id: str, max_time: int):
        """设置本地进程内销毁定时器。"""
        log_func = logger.debug if not config.DEBUG else logger.info
        log_func(f"设置容器 {container_id} 的本地销毁定时器，将在 {max_time} 秒后销毁。")

        with self._timers_lock:
            timer = self._timers.pop(container_id, None)
            if timer:
                timer.cancel()

            timer = threading.Timer(max_time, self._trigger_destroy, args=[container_id])
            timer.start()
            self._timers[container_id] = timer
    
    def set_timer(
        self,
        container_id: str,
        max_time: int,
        container_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """设置容器的销毁定时器（初始设置，不增加续期计数）
        
        用于创建容器时设置初始定时器，不会增加续期计数。
        
        Args:
            container_id: 容器ID
            max_time: 销毁时间（秒）
        """
        self._set_local_timer(container_id, max_time)
    
    def renew(self, container_id: str, max_time: int, max_renew_times: int):
        """续期容器（更新到期时间并增加续期计数）。"""
        # 检查并增加续期计数
        with self._count_lock:
            current_count = self._counts.get(container_id, 0)
            new_count = current_count + 1
            
            if new_count > max_renew_times:
                logger.warning("容器 %s 续期次数已达上限 (%s/%s)，无法续期。", container_id, current_count, max_renew_times)
                raise MaxRenewTimesExceededError(container_id, current_count, max_renew_times)
            
            self._counts[container_id] = new_count
            logger.debug("容器 %s 续期计数已更新: %s -> %s", container_id, current_count, new_count)
        
        # 更新销毁定时器
        log_func = logger.debug if not config.DEBUG else logger.info
        log_func(f"容器 {container_id} 续期成功，将在 {max_time} 秒后销毁。")
        
        with self._timers_lock:
            # 如果已存在定时器，先取消
            timer = self._timers.pop(container_id, None)
            if timer:
                timer.cancel()
            
            # 创建新的定时器
            timer = threading.Timer(max_time, self._trigger_destroy, args=[container_id])
            timer.start()
            self._timers[container_id] = timer
    
    def cancel_timer(self, container_id: str):
        """取消到期销毁定时器。"""
        with self._timers_lock:
            timer = self._timers.pop(container_id, None)
            if timer:
                timer.cancel()
    
    def cancel_all_timers(self):
        """取消所有到期销毁定时器。"""
        with self._timers_lock:
            for container_id, timer in list(self._timers.items()):
                try:
                    timer.cancel()
                except Exception:
                    pass
            self._timers.clear()
    
    def get_renew_count(self, container_id: str) -> int:
        """获取续期次数。"""
        with self._count_lock:
            return self._counts.get(container_id, 0)
    
    def remove_count(self, container_id: str):
        """清理续期计数/元数据。"""
        with self._count_lock:
            self._counts.pop(container_id, None)
    
    def _trigger_destroy(self, container_id: str):
        """触发销毁回调。"""
        for callback in self._destroy_callbacks:
            try:
                callback(container_id)
            except Exception as e:
                logger.error("执行销毁回调时发生错误: %s", e)


# 全局单例
_container_manager: Optional[ContainerManager] = None
_manager_lock = threading.Lock()


def get_container_manager() -> ContainerManager:
    """获取容器管理器单例。"""
    global _container_manager
    if _container_manager is None:
        with _manager_lock:
            if _container_manager is None:
                _container_manager = ContainerManager()
    return _container_manager


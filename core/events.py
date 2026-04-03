"""事件系统 - 解耦服务层之间的依赖"""
import logging
import threading
from typing import Dict, Any, Callable, List

logger = logging.getLogger(__name__)


class EventBus:
    """线程安全的事件总线"""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: Callable):
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler in self._handlers[event_type]:
                logger.debug("事件 %s 已存在相同处理器，跳过重复订阅", event_type)
                return
            self._handlers[event_type].append(handler)
            logger.debug("已订阅事件: %s", event_type)

    def unsubscribe(self, event_type: str, handler: Callable):
        with self._lock:
            if event_type not in self._handlers:
                return
            handlers = self._handlers[event_type]
            if handler in handlers:
                handlers.remove(handler)
                logger.debug("已取消订阅事件: %s", event_type)
            if not handlers:
                self._handlers.pop(event_type, None)

    def publish(self, event_type: str, data: Dict[str, Any]):
        with self._lock:
            if event_type not in self._handlers:
                return
            handlers = list(self._handlers[event_type])

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error("事件处理器执行失败 [%s]: %s", event_type, e, exc_info=True)


_event_bus: EventBus = None
_event_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        with _event_bus_lock:
            if _event_bus is None:
                _event_bus = EventBus()
    return _event_bus

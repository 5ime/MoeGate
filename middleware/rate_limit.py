"""限流装饰器"""
import logging
import time
import threading
from collections import defaultdict
from functools import wraps
from typing import Dict, List
from flask import request
from config import config
from core.responses import error
from middleware.ip import get_client_ip

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT = config.RATE_LIMIT_PER_MIN if hasattr(config, 'RATE_LIMIT_PER_MIN') else 60
RATE_LIMIT_WINDOW = 60

_rate_limit_history: Dict[str, List[float]] = defaultdict(list)
_rate_limit_last_seen: Dict[str, float] = {}
_rate_limit_lock = threading.Lock()
_last_gc_time = 0.0


def _prune_expired_keys(now: float, window_seconds: int) -> None:
    stale_before = now - (window_seconds * 2)
    stale_keys = [k for k, t in _rate_limit_last_seen.items() if t < stale_before]
    for key in stale_keys:
        _rate_limit_history.pop(key, None)
        _rate_limit_last_seen.pop(key, None)


def _trim_oldest_keys(max_tracked_keys: int) -> None:
    if len(_rate_limit_history) <= max_tracked_keys:
        return
    overflow = len(_rate_limit_history) - max_tracked_keys
    for key, _ts in sorted(_rate_limit_last_seen.items(), key=lambda item: item[1])[:overflow]:
        _rate_limit_history.pop(key, None)
        _rate_limit_last_seen.pop(key, None)


def _build_rate_limit_key(ip: str) -> str:
    endpoint = request.endpoint or request.path or "unknown"
    method = (request.method or "GET").upper()
    return f"{ip}:{endpoint}:{method}"


def _rate_limit_with_memory(rate_key: str, max_per_min: int, window_seconds: int) -> bool:
    global _last_gc_time
    now = time.time()

    # 先快速判断是否需要 GC，减少持锁时间
    gc_interval = int(getattr(config, "RATE_LIMIT_GC_INTERVAL_SECONDS", 30) or 30)
    need_gc = (now - _last_gc_time) >= gc_interval

    with _rate_limit_lock:
        if need_gc and (now - _last_gc_time) >= gc_interval:
            _prune_expired_keys(now, window_seconds)
            _last_gc_time = now

        max_tracked_keys = int(getattr(config, "RATE_LIMIT_MAX_TRACKED_KEYS", 10000) or 10000)
        if rate_key not in _rate_limit_history and len(_rate_limit_history) >= max_tracked_keys:
            _trim_oldest_keys(max_tracked_keys)

        cutoff = now - window_seconds
        _rate_limit_history[rate_key] = [
            req_time for req_time in _rate_limit_history[rate_key]
            if req_time > cutoff
        ]
        _rate_limit_last_seen[rate_key] = now

        if len(_rate_limit_history[rate_key]) >= max_per_min:
            remaining = (
                window_seconds - (now - _rate_limit_history[rate_key][0])
                if _rate_limit_history[rate_key]
                else window_seconds
            )
            logger.warning(
                "限流键 %s 请求超过限制 (%d/%d) | 请等待 %.1f 秒",
                rate_key, len(_rate_limit_history[rate_key]), max_per_min, remaining,
            )
            return True

        _rate_limit_history[rate_key].append(now)
        return False


def rate_limit(max_per_min: int = DEFAULT_RATE_LIMIT, window_seconds: int = RATE_LIMIT_WINDOW):
    """限流装饰器（基于IP，线程安全）"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.method == "OPTIONS":
                return f(*args, **kwargs)

            ip = get_client_ip()
            rate_key = _build_rate_limit_key(ip)

            # 仅使用内存限流（已移除 Redis 支持）
            blocked = _rate_limit_with_memory(rate_key, max_per_min, window_seconds)

            if blocked:
                return error(
                    f"请求过于频繁，请稍后再试（限制: {max_per_min}次/{window_seconds}秒）",
                    429,
                )
            return f(*args, **kwargs)
        return wrapper
    return decorator

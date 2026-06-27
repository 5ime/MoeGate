"""认证失败限流（防 API Key 暴力猜解）。"""
import logging
import threading
import time
from collections import defaultdict
from typing import Dict, List

from config import config

logger = logging.getLogger(__name__)

_failure_history: Dict[str, List[float]] = defaultdict(list)
_failure_lock = threading.Lock()
_WINDOW_SECONDS = 60


def _limit() -> int:
    return int(getattr(config, "AUTH_FAILURE_LIMIT_PER_MIN", 10) or 10)


def is_auth_failure_blocked(ip: str) -> bool:
    """当前 IP 是否因连续认证失败被临时封禁。"""
    if not ip or ip == "unknown":
        return False

    now = time.time()
    cutoff = now - _WINDOW_SECONDS
    rate_key = f"auth-fail:{ip}"

    with _failure_lock:
        _failure_history[rate_key] = [
            ts for ts in _failure_history.get(rate_key, []) if ts > cutoff
        ]
        return len(_failure_history[rate_key]) >= _limit()


def record_auth_failure(ip: str) -> None:
    """记录一次认证失败。"""
    if not ip or ip == "unknown":
        return

    now = time.time()
    rate_key = f"auth-fail:{ip}"

    with _failure_lock:
        cutoff = now - _WINDOW_SECONDS
        _failure_history[rate_key] = [
            ts for ts in _failure_history.get(rate_key, []) if ts > cutoff
        ]
        _failure_history[rate_key].append(now)
        if len(_failure_history[rate_key]) >= _limit():
            logger.warning("认证失败次数过多，已临时限制来源 IP: %s", ip)


def clear_auth_failures(ip: str) -> None:
    """认证成功后清除该 IP 的失败计数。"""
    if not ip or ip == "unknown":
        return
    with _failure_lock:
        _failure_history.pop(f"auth-fail:{ip}", None)

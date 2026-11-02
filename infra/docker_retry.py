"""Docker 调用的瞬时错误重试。

Docker daemon 抖动、socket 半开、daemon 重启期间的 500/503 都属于"再试一次就好"的
瞬时故障。直接抛给用户只会表现为"偶发失败"，尤其在开考并发创建时最容易被撞上。

这里只重试**瞬时**错误：4xx（镜像不存在、名字冲突、参数非法）立即抛出，
网络地址池耗尽这类需要另行处理的错误也不重试。
"""
import logging
import random
import time
from typing import Any, Callable, Optional, TypeVar

import docker

from utils.docker_image import extract_docker_error_message

logger = logging.getLogger(__name__)

T = TypeVar("T")

_TRANSIENT_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_TRANSIENT_HINTS = (
    "connection reset",
    "connection refused",
    "connection aborted",
    "broken pipe",
    "timed out",
    "timeout",
    "temporary failure",
    "eof occurred",
    "no such host",
    "i/o timeout",
    "server error",
)
# 这些不是抖动，重试多少次都一样，必须交给上层按业务逻辑处理
_PERMANENT_HINTS = (
    "all predefined address pools",
    "could not find an available",
    "no such image",
    "conflict",
    "already in use",
)

_DEFAULT_ATTEMPTS = 3
_DEFAULT_BASE_DELAY = 0.4
_DEFAULT_MAX_DELAY = 3.0


def is_transient_docker_error(exc: BaseException) -> bool:
    """判断一次 Docker 调用是否值得重试。"""
    if isinstance(exc, docker.errors.NotFound):
        return False

    # APIError 带 response 时 str(exc) 会变成 "500 Server Error for url: reason"，
    # 真正的业务信息在 explanation 里，两边都要看。
    message = f"{str(exc)} {extract_docker_error_message(exc)}".lower()
    if any(hint in message for hint in _PERMANENT_HINTS):
        return False

    if isinstance(exc, docker.errors.APIError):
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None
        if status in _TRANSIENT_STATUS:
            return True
        if status is not None and 400 <= status < 500:
            return False
        return any(hint in message for hint in _TRANSIENT_HINTS)

    try:
        import requests

        if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            return True
    except Exception:  # pragma: no cover - requests 缺失时按非瞬时处理
        return False

    return isinstance(exc, docker.errors.DockerException) and any(
        hint in message for hint in _TRANSIENT_HINTS
    )


def docker_call(
    operation: Callable[[], T],
    *,
    label: str = "docker",
    attempts: int = _DEFAULT_ATTEMPTS,
    base_delay: float = _DEFAULT_BASE_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """执行一次 Docker 调用，遇到瞬时错误按指数退避重试。

    Args:
        operation: 真正发起的 Docker 调用（无参闭包）
        label: 日志标识，便于定位是哪一步在重试
        attempts: 总尝试次数（含首次）
        base_delay: 首次退避基数（秒）
        max_delay: 退避上限（秒）
        sleep: 注入用，测试里可替换成空函数

    Returns:
        operation 的返回值

    Raises:
        最后一次的异常（非瞬时错误则在首次就抛出）
    """
    total = max(1, int(attempts))
    last_exc: Optional[BaseException] = None

    for attempt in range(1, total + 1):
        try:
            return operation()
        except Exception as exc:
            last_exc = exc
            if attempt >= total or not is_transient_docker_error(exc):
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            # 抖动只是为了打散重试时刻，与安全性无关（nosec B311）
            delay += random.uniform(0, base_delay)  # nosec B311
            logger.warning(
                "Docker 调用遇到瞬时错误，%s 秒后重试（%s 第 %d/%d 次）: %s",
                round(delay, 2), label, attempt, total, exc,
            )
            sleep(delay)

    raise last_exc  # pragma: no cover - 循环内必定 return 或 raise

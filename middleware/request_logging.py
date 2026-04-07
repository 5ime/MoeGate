"""请求日志装饰器"""
import logging
import time
import uuid
from functools import wraps
from flask import request, g
from config import config
from middleware.ip import get_client_ip

logger = logging.getLogger(__name__)


def _is_high_frequency_request(action: str) -> bool:
    path = str(getattr(request, "path", "") or "")
    method = str(getattr(request, "method", "") or "").upper()
    if method != "GET":
        return False
    return (
        path.endswith("/destroy-status")
        or path.endswith("/status")
        or path.endswith("/metrics")
        or action in {"获取容器删除任务状态", "获取Compose项目删除任务状态", "获取系统状态"}
    )


def log_request(action: str):
    """记录请求日志的装饰器（带请求ID追踪）"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())[:8]
            g.request_id = request_id
            start_time = time.time()
            is_high_frequency = _is_high_frequency_request(action)
            log_fn = logger.debug if is_high_frequency else logger.info

            if config.DEBUG:
                log_fn(
                    "[%s] 执行操作: %s | 来源IP: %s | 方法: %s | 路径: %s",
                    request_id, action, get_client_ip(), request.method, request.path,
                )
            else:
                logger.debug("[%s] %s", request_id, action)

            try:
                result = f(*args, **kwargs)
                duration = time.time() - start_time

                if config.DEBUG:
                    log_fn("[%s] 操作 %s 执行成功 | 耗时: %.3fs", request_id, action, duration)
                elif duration > 1.0:
                    logger.info("[%s] %s 完成，耗时: %.3fs", request_id, action, duration)
                else:
                    logger.debug("[%s] %s 完成", request_id, action)

                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "[%s] 操作 %s 执行失败 | 错误: %s | 耗时: %.3fs",
                    request_id, action, e, duration,
                    exc_info=config.DEBUG,
                )
                raise
        return wrapper
    return decorator

"""JSON请求验证装饰器"""
import logging
from functools import wraps
from flask import request, g
from core.responses import error

logger = logging.getLogger(__name__)

DEFAULT_MAX_REQUEST_SIZE = 1024 * 1024


def validate_json(required=None, max_size=DEFAULT_MAX_REQUEST_SIZE):
    """验证JSON请求的装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                content_type = request.content_type or "unknown"
                return error(f"请求内容必须是JSON格式，当前类型: {content_type}", 400)

            content_length = request.content_length
            if content_length and content_length > max_size:
                return error(f"请求体大小超过限制 ({content_length} > {max_size} 字节)", 413)

            try:
                data = request.get_json(silent=False)
            except Exception as e:
                logger.warning("JSON解析失败: %s", e)
                return error("JSON格式错误", 400)

            if not data:
                return error("JSON数据不能为空", 400)

            if required:
                missing = [field for field in required if field not in data or data[field] is None]
                if missing:
                    return error(f"缺少必要字段: {', '.join(missing)}", 400)

            g.json = data
            return f(*args, **kwargs)
        return wrapper
    return decorator

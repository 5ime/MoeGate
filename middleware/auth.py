"""API密钥认证装饰器"""
import hmac
import logging
from functools import wraps
from flask import request
from config import config
from core.responses import error
from middleware.ip import get_client_ip

logger = logging.getLogger(__name__)


def require_api_key(f):
    """API认证装饰器，要求请求包含有效的API密钥（X-API-Key Header）"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not config.API_KEY:
            logger.error("未配置 API_KEY")
            return error("API认证配置错误", 500)

        api_key = request.headers.get('X-API-Key')

        if not api_key:
            logger.warning("API请求缺少认证信息，来源IP: %s", get_client_ip())
            return error("缺少API认证信息，请在Header中提供X-API-Key", 401)

        if not hmac.compare_digest(api_key, config.API_KEY):
            logger.warning("API密钥验证失败，来源IP: %s", get_client_ip())
            return error("API密钥无效", 401)

        return f(*args, **kwargs)
    return wrapper

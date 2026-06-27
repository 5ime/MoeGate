"""API密钥认证装饰器"""
import hmac
import logging
from functools import wraps
from typing import Tuple
from flask import request
from config import config
from core.responses import error
from middleware.ip import get_client_ip
from middleware.auth_guard import (
    clear_auth_failures,
    is_auth_failure_blocked,
    record_auth_failure,
)
from middleware.csrf import validate_csrf_for_session_request
from middleware.session import (
    read_session_token_from_request,
    session_cookie_enabled,
    verify_session_token,
)

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("moegate.audit")


def _extract_api_key() -> Tuple[str, str]:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key, "api_key"

    if session_cookie_enabled():
        token = read_session_token_from_request(request)
        if verify_session_token(token or ""):
            return config.API_KEY or "", "session"

    return "", "none"


def _log_api_audit(auth_method: str) -> None:
    """记录已认证 API 变更操作，便于事后追溯。"""
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    audit_logger.info(
        "API audit | ip=%s | method=%s | path=%s | auth=%s",
        get_client_ip(),
        request.method,
        request.path,
        auth_method,
    )


def require_api_key(f):
    """API认证装饰器，支持 X-API-Key Header 或 HttpOnly Session Cookie。"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not config.API_KEY:
            logger.error("未配置 API_KEY")
            return error("API认证配置错误", 500)

        client_ip = get_client_ip()
        if is_auth_failure_blocked(client_ip):
            return error("认证失败次数过多，请稍后再试", 429)

        api_key, auth_method = _extract_api_key()

        if not api_key:
            logger.warning("API请求缺少认证信息，来源IP: %s", client_ip)
            return error("缺少API认证信息，请在Header中提供X-API-Key或先登录", 401)

        if not hmac.compare_digest(api_key, config.API_KEY):
            logger.warning("API密钥验证失败，来源IP: %s", client_ip)
            record_auth_failure(client_ip)
            return error("API密钥无效", 401)

        clear_auth_failures(client_ip)

        if auth_method == "session" and not validate_csrf_for_session_request(request):
            return error("CSRF 校验失败", 403)

        _log_api_audit(auth_method)
        return f(*args, **kwargs)
    return wrapper

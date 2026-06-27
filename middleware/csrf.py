"""Cookie Session 的 CSRF 防护（Double-Submit Cookie）。"""
import hmac
import logging
import secrets
from typing import Optional

from flask import Request, Response

from config import config

logger = logging.getLogger(__name__)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def csrf_enabled() -> bool:
    if not getattr(config, "ENABLE_API_SESSION_COOKIE", True):
        return False
    return bool(getattr(config, "ENABLE_API_CSRF", True))


def csrf_cookie_name() -> str:
    return config.API_CSRF_COOKIE_NAME


def csrf_header_name() -> str:
    return config.API_CSRF_HEADER_NAME


def _cookie_secure() -> bool:
    return bool(getattr(config, "API_SESSION_COOKIE_SECURE", not config.DEBUG))


def _cookie_samesite() -> str:
    return getattr(config, "API_SESSION_COOKIE_SAMESITE", "Lax")


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def apply_csrf_cookie(response: Response, token: str) -> Response:
    max_age = int(getattr(config, "API_SESSION_TTL_SEC", 86400) or 86400)
    response.set_cookie(
        csrf_cookie_name(),
        token,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=max_age,
        path="/",
    )
    return response


def clear_csrf_cookie(response: Response) -> Response:
    response.set_cookie(
        csrf_cookie_name(),
        "",
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=0,
        path="/",
    )
    return response


def read_csrf_token_from_request(request: Request) -> Optional[str]:
    return request.cookies.get(csrf_cookie_name())


def ensure_csrf_token(request: Request) -> str:
    """返回请求中已有的 CSRF token，或生成新 token（尚未写入响应）。"""
    existing = read_csrf_token_from_request(request)
    if existing:
        return existing
    return generate_csrf_token()


def validate_csrf_for_session_request(request: Request) -> bool:
    """Session 认证下的变更请求须通过 Double-Submit 校验。"""
    if not csrf_enabled():
        return True
    if request.method.upper() in _SAFE_METHODS:
        return True

    cookie_token = read_csrf_token_from_request(request) or ""
    header_token = request.headers.get(csrf_header_name()) or ""
    if not cookie_token or not header_token:
        logger.warning("CSRF 校验失败：缺少 token（method=%s path=%s）", request.method, request.path)
        return False
    if not hmac.compare_digest(cookie_token, header_token):
        logger.warning("CSRF 校验失败：token 不匹配（method=%s path=%s）", request.method, request.path)
        return False
    return True

"""API 认证路由（HttpOnly Cookie Session）。"""
import hmac
import logging

from flask import Blueprint, make_response, request

from config import config
from core.responses import error, success
from middleware import rate_limit, validate_json
from middleware.auth_guard import (
    clear_auth_failures,
    is_auth_failure_blocked,
    record_auth_failure,
)
from middleware.ip import get_client_ip
from middleware.csrf import (
    apply_csrf_cookie,
    clear_csrf_cookie,
    csrf_enabled,
    ensure_csrf_token,
    generate_csrf_token,
    validate_csrf_for_session_request,
)
from middleware.session import (
    create_session_token,
    read_session_token_from_request,
    session_cookie_enabled,
    session_cookie_name,
    verify_session_token,
)

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")
logger = logging.getLogger(__name__)


def _cookie_secure() -> bool:
    return bool(getattr(config, "API_SESSION_COOKIE_SECURE", not config.DEBUG))


def _apply_session_cookie(response, token: str):
    response.set_cookie(
        session_cookie_name(),
        token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=getattr(config, "API_SESSION_COOKIE_SAMESITE", "Lax"),
        max_age=int(getattr(config, "API_SESSION_TTL_SEC", 86400) or 86400),
        path="/",
    )
    return response


def _clear_session_cookie(response):
    response.set_cookie(
        session_cookie_name(),
        "",
        httponly=True,
        secure=_cookie_secure(),
        samesite=getattr(config, "API_SESSION_COOKIE_SAMESITE", "Lax"),
        max_age=0,
        path="/",
    )
    return response


@bp.route("/session", methods=["GET"])
@rate_limit(max_per_min=60)
def get_session_status():
    if not session_cookie_enabled():
        return success({"authenticated": False, "mode": "header"})
    token = read_session_token_from_request(request)
    authenticated = verify_session_token(token or "")
    data = {"authenticated": authenticated, "mode": "cookie"}
    if authenticated and csrf_enabled():
        csrf_token = ensure_csrf_token(request)
        data["csrf_token"] = csrf_token
        response = make_response(success(data))
        apply_csrf_cookie(response, csrf_token)
        return response
    return success(data)


@bp.route("/login", methods=["POST"])
@rate_limit(max_per_min=30)
@validate_json(required=["api_key"])
def login_with_api_key():
    if not session_cookie_enabled():
        return error("当前未启用 Cookie Session 认证", 400)

    if not config.API_KEY:
        logger.error("未配置 API_KEY")
        return error("API认证配置错误", 500)

    client_ip = get_client_ip()
    if is_auth_failure_blocked(client_ip):
        return error("认证失败次数过多，请稍后再试", 429)

    api_key = str((request.get_json() or {}).get("api_key") or "").strip()
    if not api_key:
        return error("缺少 api_key", 400)
    if not hmac.compare_digest(api_key, config.API_KEY):
        logger.warning("Cookie 登录 API 密钥验证失败")
        record_auth_failure(client_ip)
        return error("API密钥无效", 401)

    clear_auth_failures(client_ip)

    data = {"authenticated": True}
    csrf_token = generate_csrf_token() if csrf_enabled() else None
    if csrf_token:
        data["csrf_token"] = csrf_token
    response = make_response(success(data, "登录成功"))
    _apply_session_cookie(response, create_session_token())
    if csrf_token:
        apply_csrf_cookie(response, csrf_token)
    return response


@bp.route("/logout", methods=["POST"])
@rate_limit(max_per_min=30)
def logout_session():
    token = read_session_token_from_request(request)
    if verify_session_token(token or "") and csrf_enabled():
        if not validate_csrf_for_session_request(request):
            return error("CSRF 校验失败", 403)
    response = make_response(success({"authenticated": False}, "已退出登录"))
    _clear_session_cookie(response)
    clear_csrf_cookie(response)
    return response

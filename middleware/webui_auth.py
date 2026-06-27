"""WebUI Basic 认证"""
import hmac
import logging
from typing import Optional

from flask import request, Response

from config import config

logger = logging.getLogger(__name__)

_PUBLIC_PATH_PREFIXES = (
    "/api/",
    "/healthz",
    "/metrics",
)


def webui_auth_enabled() -> bool:
    user = (getattr(config, "WEBUI_BASIC_AUTH_USER", None) or "").strip()
    password = getattr(config, "WEBUI_BASIC_AUTH_PASSWORD", None) or ""
    return bool(user and password)


def _is_public_path(path: str) -> bool:
    normalized = str(path or "/")
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


def check_webui_basic_auth() -> Optional[Response]:
    """校验 WebUI Basic 认证；通过时返回 None。"""
    if not webui_auth_enabled():
        return None
    if _is_public_path(request.path):
        return None

    auth = request.authorization
    expected_user = config.WEBUI_BASIC_AUTH_USER.strip()
    expected_password = config.WEBUI_BASIC_AUTH_PASSWORD
    if (
        auth
        and hmac.compare_digest(auth.username or "", expected_user)
        and hmac.compare_digest(auth.password or "", expected_password)
    ):
        return None

    logger.warning("WebUI Basic 认证失败: path=%s", request.path)
    return Response(
        "WebUI authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="MoeGate WebUI", charset="UTF-8"'},
    )

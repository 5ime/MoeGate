"""API Session Cookie 签发与校验。"""
import logging
from typing import Optional

from flask import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import config

logger = logging.getLogger(__name__)


def _serializer() -> URLSafeTimedSerializer:
    secret = getattr(config, "API_SESSION_SECRET", None)
    if not secret:
        raise RuntimeError("未配置 API_SESSION_SECRET，无法签发或校验 Session Cookie")
    return URLSafeTimedSerializer(secret, salt="moegate-api-session")


def session_cookie_name() -> str:
    return getattr(config, "API_SESSION_COOKIE_NAME", "moegate_session")


def create_session_token() -> str:
    return _serializer().dumps({"v": 1})


def verify_session_token(token: str) -> bool:
    if not token:
        return False
    max_age = int(getattr(config, "API_SESSION_TTL_SEC", 86400) or 86400)
    try:
        payload = _serializer().loads(token, max_age=max_age)
        return isinstance(payload, dict) and payload.get("v") == 1
    except SignatureExpired:
        logger.debug("API session cookie 已过期")
        return False
    except BadSignature:
        logger.debug("API session cookie 签名无效")
        return False


def read_session_token_from_request(request: Request) -> Optional[str]:
    return request.cookies.get(session_cookie_name())


def session_cookie_enabled() -> bool:
    return bool(getattr(config, "ENABLE_API_SESSION_COOKIE", True))

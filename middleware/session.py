"""API Session Cookie 签发、校验与吊销。

Cookie 本身是无状态签名串，一旦签发就无法从服务端收回——"退出登录"只是清了浏览器
Cookie，拿到过该 Cookie 的人照样能用。因此每个会话带一个 `sid`，服务端维护吊销表；
另有全局 `epoch`，用于"把所有已签发会话一次性踢下线"（例如轮换 API Key 之后）。
"""
import logging
import threading
import time
import uuid
from typing import Dict, Optional

from flask import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import config

logger = logging.getLogger(__name__)

SESSION_VERSION = 2

_revoke_lock = threading.Lock()
# sid -> 吊销时刻；只影响本进程（多实例部署需各自调用 revoke-all 或重启）
_revoked_sids: Dict[str, float] = {}
_epoch = 0


def _serializer() -> URLSafeTimedSerializer:
    secret = getattr(config, "API_SESSION_SECRET", None)
    if not secret:
        raise RuntimeError("未配置 API_SESSION_SECRET，无法签发或校验 Session Cookie")
    return URLSafeTimedSerializer(secret, salt="moegate-api-session")


def session_cookie_name() -> str:
    return getattr(config, "API_SESSION_COOKIE_NAME", "moegate_session")


def _ttl_seconds() -> int:
    return int(getattr(config, "API_SESSION_TTL_SEC", 86400) or 86400)


def _current_epoch() -> int:
    with _revoke_lock:
        return _epoch


def _prune_revoked(now: Optional[float] = None) -> None:
    """吊销记录不必长期保留：超过会话 TTL 后对应 Cookie 自然失效。"""
    now = time.time() if now is None else now
    cutoff = now - _ttl_seconds()
    for sid in [sid for sid, at in _revoked_sids.items() if at < cutoff]:
        del _revoked_sids[sid]


def create_session_token() -> str:
    payload = {
        "v": SESSION_VERSION,
        "sid": uuid.uuid4().hex,
        "e": _current_epoch(),
    }
    return _serializer().dumps(payload)


def _decode_token(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=_ttl_seconds())
    except SignatureExpired:
        logger.debug("API session cookie 已过期")
        return None
    except BadSignature:
        logger.debug("API session cookie 签名无效")
        return None
    except Exception as exc:
        logger.debug("API session cookie 解析失败: %s", exc)
        return None
    return payload if isinstance(payload, dict) else None


def verify_session_token(token: str) -> bool:
    payload = _decode_token(token)
    if not payload or payload.get("v") != SESSION_VERSION:
        return False

    sid = str(payload.get("sid") or "")
    if not sid:
        return False
    if int(payload.get("e") or 0) < _current_epoch():
        logger.debug("API session 已被全局吊销")
        return False

    with _revoke_lock:
        _prune_revoked()
        if sid in _revoked_sids:
            logger.debug("API session 已退出登录")
            return False
    return True


def revoke_session_token(token: str) -> bool:
    """吊销单个会话（退出登录）。Token 无效时返回 False。"""
    payload = _decode_token(token)
    if not payload:
        return False
    sid = str(payload.get("sid") or "")
    if not sid:
        return False
    with _revoke_lock:
        _prune_revoked()
        _revoked_sids[sid] = time.time()
    return True


def revoke_all_sessions() -> int:
    """吊销全部已签发会话，返回新的纪元值。"""
    global _epoch
    with _revoke_lock:
        _epoch += 1
        _revoked_sids.clear()
        return _epoch


def revoked_session_count() -> int:
    with _revoke_lock:
        _prune_revoked()
        return len(_revoked_sids)


def read_session_token_from_request(request: Request) -> Optional[str]:
    return request.cookies.get(session_cookie_name())


def session_cookie_enabled() -> bool:
    return bool(getattr(config, "ENABLE_API_SESSION_COOKIE", True))

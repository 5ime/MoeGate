"""FRP 敏感配置脱敏。"""

import re
from typing import Dict, Optional

_PASSWORD_PLACEHOLDER = "********"
_SECRET_LINE_RE = re.compile(
    r'^(\s*(?:password|token)\s*=\s*)"[^"]*"\s*$',
    re.IGNORECASE | re.MULTILINE,
)


def is_password_placeholder(value: Optional[str]) -> bool:
    text = (value or "").strip()
    return not text or text == _PASSWORD_PLACEHOLDER


def mask_frp_settings_payload(payload: Dict[str, object]) -> Dict[str, object]:
    """GET 响应脱敏：不返回 admin_password 明文。"""
    data = dict(payload or {})
    has_password = bool(str(data.get("admin_password") or "").strip())
    data["admin_password_set"] = has_password
    data["admin_password"] = ""
    return data


def redact_frp_config_toml(content: str) -> str:
    """脱敏 FRP TOML 中的 password/token 字段。"""
    if not content:
        return content or ""
    return _SECRET_LINE_RE.sub(rf'\1"{_PASSWORD_PLACEHOLDER}"', content)

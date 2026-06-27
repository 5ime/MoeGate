"""FRP 运行时设置辅助函数。"""

from typing import Dict, Optional, Tuple

from config import config
from core.events import get_event_bus
from services import runtime_store
from services.frp.event_handler import handle_container_created
from services.frp.redact import is_password_placeholder, mask_frp_settings_payload
FRP_SETTING_FIELD_MAP = {
    "enabled": "ENABLE_FRP",
    "server_addr": "FRP_SERVER_ADDR",
    "server_port": "FRP_SERVER_PORT",
    "vhost_http_port": "FRP_VHOST_HTTP_PORT",
    "admin_ip": "FRP_ADMIN_IP",
    "admin_port": "FRP_ADMIN_PORT",
    "admin_user": "FRP_ADMIN_USER",
    "admin_password": "FRP_ADMIN_PASSWORD",
    "use_domain": "FRP_USE_DOMAIN",
    "domain_suffix": "FRP_DOMAIN_SUFFIX",
}


def _build_frp_settings_payload() -> Dict[str, object]:
    return {
        "enabled": bool(config.ENABLE_FRP),
        "server_addr": config.FRP_SERVER_ADDR or "",
        "server_port": int(config.FRP_SERVER_PORT),
        "vhost_http_port": int(config.FRP_VHOST_HTTP_PORT) if config.FRP_VHOST_HTTP_PORT is not None else None,
        "admin_ip": config.FRP_ADMIN_IP or "",
        "admin_port": int(config.FRP_ADMIN_PORT),
        "admin_user": config.FRP_ADMIN_USER or "",
        "admin_password": config.FRP_ADMIN_PASSWORD or "",
        "use_domain": bool(config.FRP_USE_DOMAIN),
        "domain_suffix": (config.FRP_DOMAIN_SUFFIX or "").lstrip("."),
    }


def build_frp_settings_data() -> Dict[str, object]:
    return mask_frp_settings_payload(_build_frp_settings_payload())


def parse_frp_settings_update(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
    payload = dict(body or {})
    allowed_fields = set(FRP_SETTING_FIELD_MAP.keys())
    updates = {k: payload[k] for k in payload.keys() if k in allowed_fields}
    if not updates:
        return "未提供可更新的 FRP 设置字段", None

    if "enabled" in updates and not isinstance(updates["enabled"], bool):
        return "字段 enabled 必须为布尔值", None
    if "use_domain" in updates and not isinstance(updates["use_domain"], bool):
        return "字段 use_domain 必须为布尔值", None

    int_fields = ["server_port", "vhost_http_port", "admin_port"]
    for field in int_fields:
        if field not in updates:
            continue
        value = updates[field]
        if value is None and field == "vhost_http_port":
            continue
        try:
            cast_value = int(value)
        except (TypeError, ValueError):
            return f"字段 {field} 必须为整数", None
        if cast_value <= 0:
            return f"字段 {field} 必须大于 0", None
        updates[field] = cast_value

    str_fields = ["server_addr", "admin_ip", "admin_user", "admin_password", "domain_suffix"]
    for field in str_fields:
        if field in updates:
            if not isinstance(updates[field], str):
                return f"字段 {field} 必须为字符串", None
            updates[field] = updates[field].strip()

    return None, updates


def _set_frp_enabled_runtime(enabled: bool) -> None:
    event_bus = get_event_bus()
    if enabled:
        event_bus.subscribe("container.created", handle_container_created)
    else:
        event_bus.unsubscribe("container.created", handle_container_created)
    runtime_store.set("ENABLE_FRP", enabled)


def apply_frp_settings_update(updates: Dict[str, object]) -> None:
    """将校验后的更新应用到运行态存储。"""
    if "enabled" in updates:
        _set_frp_enabled_runtime(bool(updates["enabled"]))
    if "server_addr" in updates:
        runtime_store.set("FRP_SERVER_ADDR", updates["server_addr"] or None)
    if "server_port" in updates:
        runtime_store.set("FRP_SERVER_PORT", int(updates["server_port"]))
    if "vhost_http_port" in updates:
        runtime_store.set(
            "FRP_VHOST_HTTP_PORT",
            int(updates["vhost_http_port"]) if updates["vhost_http_port"] is not None else None,
        )
    if "admin_ip" in updates:
        runtime_store.set("FRP_ADMIN_IP", updates["admin_ip"] or "127.0.0.1")
    if "admin_port" in updates:
        runtime_store.set("FRP_ADMIN_PORT", int(updates["admin_port"]))
    if "admin_user" in updates:
        runtime_store.set("FRP_ADMIN_USER", updates["admin_user"] or None)
    if "admin_password" in updates:
        password_value = updates["admin_password"]
        if not is_password_placeholder(password_value):
            runtime_store.set("FRP_ADMIN_PASSWORD", password_value or None)
    if "use_domain" in updates:
        runtime_store.set("FRP_USE_DOMAIN", bool(updates["use_domain"]))
    if "domain_suffix" in updates:
        runtime_store.set("FRP_DOMAIN_SUFFIX", updates["domain_suffix"] or None)

    runtime_store.set("FRP_ADMIN_ADDR", f"http://{config.FRP_ADMIN_IP}:{config.FRP_ADMIN_PORT}")

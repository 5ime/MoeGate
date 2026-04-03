"""FRP代理管理路由"""
import logging
import socket
from pathlib import Path
from typing import Dict, Tuple
from flask import Blueprint, g
from dotenv import find_dotenv, set_key
from services.frp import (
    get_frp_config,
    get_proxy_config,
    list_proxies,
    add_proxy_config,
    update_proxy_config,
    delete_proxy_config,
    reload_frp_config,
    create_config,
    FRPConfigError,
)
from config import config
from core.events import get_event_bus
from middleware import (
    validate_json,
    log_request,
    rate_limit,
    require_api_key,
)
from core.responses import (
    error,
    success,
    exception,
)

bp = Blueprint("frp", __name__, url_prefix="/api/v1")
logger = logging.getLogger(__name__)

_FRP_SETTING_FIELD_MAP = {
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
        # domain_suffix 允许用户填 ".example.com" 或 "example.com"，内部会规范化为 "example.com"
        "domain_suffix": (config.FRP_DOMAIN_SUFFIX or "").lstrip("."),
    }


def _persist_frp_settings_values(values: Dict[str, object]) -> Tuple[bool, str]:
    if not getattr(config, "ALLOW_RUNTIME_CONFIG_WRITE", False):
        return False, "已禁用运行时配置写入（ALLOW_RUNTIME_CONFIG_WRITE=False）"
    try:
        env_path = find_dotenv(filename=".env", usecwd=True)
        if not env_path:
            candidate = Path(__file__).resolve().parents[1] / ".env"
            if not candidate.exists():
                return False, "未找到 .env 文件，设置仅在当前进程生效"
            env_path = str(candidate)

        for field, value in values.items():
            env_key = _FRP_SETTING_FIELD_MAP.get(field)
            if not env_key:
                continue
            if isinstance(value, bool):
                encoded = "True" if value else "False"
            elif value is None:
                encoded = ""
            else:
                encoded = str(value)
            set_key(env_path, env_key, encoded, quote_mode="never")
        return True, ""
    except Exception as exc:
        logger.warning("持久化 FRP 设置失败: %s", exc)
        return False, "写入 .env 失败，设置仅在当前进程生效"


def _handle_frp_call(func, success_message: str = "操作成功", *args, **kwargs):
    """统一处理FRP服务调用，将返回的数据格式化为响应"""
    try:
        data = func(*args, **kwargs)
        return success(data, success_message)
    except FRPConfigError as e:
        return exception(e)


def _check_tcp_connectivity(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def _set_frp_enabled_runtime(enabled: bool) -> None:
    event_bus = get_event_bus()
    if enabled:
        event_bus.subscribe('container.created', create_config)
    else:
        event_bus.unsubscribe('container.created', create_config)
    config.ENABLE_FRP = enabled


def _persist_frp_enabled_setting(enabled: bool) -> Tuple[bool, str]:
    if not getattr(config, "ALLOW_RUNTIME_CONFIG_WRITE", False):
        return False, "已禁用运行时配置写入（ALLOW_RUNTIME_CONFIG_WRITE=False）"
    try:
        env_path = find_dotenv(filename=".env", usecwd=True)
        if not env_path:
            candidate = Path(__file__).resolve().parents[1] / ".env"
            if not candidate.exists():
                return False, "未找到 .env 文件，开关仅在当前进程生效"
            env_path = str(candidate)

        set_key(env_path, "ENABLE_FRP", "True" if enabled else "False", quote_mode="never")
        return True, ""
    except Exception as exc:
        logger.warning("持久化 ENABLE_FRP 失败: %s", exc)
        return False, "写入 .env 失败，开关仅在当前进程生效"


def _require_frp_enabled_for_mutation():
    if not config.ENABLE_FRP:
        return error("FRP 当前未启用，已拒绝本次配置变更", 403)
    return None


def _short_circuit_when_frp_disabled(payload: Dict[str, object], message: str = "FRP 当前未启用"):
    """FRP 未启用时的统一短路响应。"""
    if not config.ENABLE_FRP:
        base = {"enabled": False}
        base.update(payload or {})
        return success(base, message, 200)
    return None


@bp.route("/frp/proxies", methods=["GET"])
@require_api_key
@log_request("获取FRP代理列表")
@rate_limit(max_per_min=30)
def get_frp_proxies():
    disabled = _short_circuit_when_frp_disabled({"proxies": [], "count": 0})
    if disabled:
        return disabled

    def _do():
        proxies = list_proxies()
        return {"proxies": proxies, "count": len(proxies)}
    return _handle_frp_call(_do, "获取代理列表成功")


@bp.route("/frp/proxies", methods=["POST"])
@require_api_key
@validate_json(required=["name", "localPort"])
@log_request("创建FRP代理")
@rate_limit(max_per_min=20)
def create_frp_proxy():
    disabled_resp = _require_frp_enabled_for_mutation()
    if disabled_resp:
        return disabled_resp

    proxy_config = g.json

    def _do():
        ok, msg = add_proxy_config(proxy_config)
        if not ok:
            raise FRPConfigError(msg)
        return {"proxy": proxy_config}
    return _handle_frp_call(_do, "创建代理配置成功")


@bp.route("/frp/proxies/<name>", methods=["GET"])
@require_api_key
@log_request("获取FRP代理详情")
@rate_limit(max_per_min=30)
def get_frp_proxy(name: str):
    # 读取接口也不应在禁用状态下触发对 FRP 管理 API 的请求
    disabled = _short_circuit_when_frp_disabled({"proxy": None})
    if disabled:
        return disabled

    def _do():
        return {"proxy": get_proxy_config(name)}
    return _handle_frp_call(_do, f"获取代理 '{name}' 配置成功")


@bp.route("/frp/proxies/<name>", methods=["PUT"])
@require_api_key
@validate_json()
@log_request("更新FRP代理")
@rate_limit(max_per_min=20)
def update_frp_proxy(name: str):
    disabled_resp = _require_frp_enabled_for_mutation()
    if disabled_resp:
        return disabled_resp

    proxy_config = g.json

    def _do():
        ok, msg = update_proxy_config(name, proxy_config)
        if not ok:
            raise FRPConfigError(msg)
        return {"proxy": get_proxy_config(name)}
    return _handle_frp_call(_do, "更新代理配置成功")


@bp.route("/frp/proxies/<name>", methods=["DELETE"])
@require_api_key
@log_request("删除FRP代理")
@rate_limit(max_per_min=20)
def delete_frp_proxy(name: str):
    disabled_resp = _require_frp_enabled_for_mutation()
    if disabled_resp:
        return disabled_resp

    def _do():
        ok, msg = delete_proxy_config(name)
        if not ok:
            raise FRPConfigError(msg)
        return {"name": name}
    return _handle_frp_call(_do, "删除代理配置成功")


@bp.route("/frp/config", methods=["GET"])
@require_api_key
@log_request("获取FRP完整配置")
@rate_limit(max_per_min=30)
def get_frp_config_route():
    disabled = _short_circuit_when_frp_disabled({"config": "", "proxies": [], "proxies_count": 0})
    if disabled:
        return disabled

    def _do():
        config_content = get_frp_config()
        proxies = list_proxies()
        return {
            "config": config_content,
            "proxies_count": len(proxies),
            "proxies": proxies,
        }
    return _handle_frp_call(_do, "获取FRP配置成功")


@bp.route("/frp/reload", methods=["POST"])
@require_api_key
@log_request("重载FRP配置")
@rate_limit(max_per_min=10)
def reload_frp():
    disabled_resp = _require_frp_enabled_for_mutation()
    if disabled_resp:
        return disabled_resp

    def _do():
        ok, msg = reload_frp_config()
        if not ok:
            raise FRPConfigError(msg)
        return None
    return _handle_frp_call(_do, "重载FRP配置成功")


@bp.route("/frp/health", methods=["GET"])
@require_api_key
@log_request("检查FRP健康状态")
@rate_limit(max_per_min=30)
def frp_health():
    server_ok = False
    if config.FRP_SERVER_ADDR and config.FRP_SERVER_PORT:
        server_ok = _check_tcp_connectivity(config.FRP_SERVER_ADDR, config.FRP_SERVER_PORT)

    admin_ok = False
    if config.FRP_ADMIN_IP and config.FRP_ADMIN_PORT:
        admin_ok = _check_tcp_connectivity(config.FRP_ADMIN_IP, config.FRP_ADMIN_PORT)

    overall_ok = bool(config.ENABLE_FRP and server_ok and admin_ok)

    data = {
        "enabled": bool(config.ENABLE_FRP),
        "overall_ok": overall_ok,
        "server": {
            "host": config.FRP_SERVER_ADDR,
            "port": config.FRP_SERVER_PORT,
            "reachable": server_ok,
        },
        "admin": {
            "host": config.FRP_ADMIN_IP,
            "port": config.FRP_ADMIN_PORT,
            "reachable": admin_ok,
        },
    }

    if overall_ok:
        return success(data, "FRP健康状态正常")
    return success(data, "FRP健康检查未通过", 503)


@bp.route("/frp/settings", methods=["GET"])
@require_api_key
@log_request("获取FRP开关设置")
@rate_limit(max_per_min=30)
def get_frp_settings():
    return success(_build_frp_settings_payload(), "获取FRP设置成功")


@bp.route("/frp/settings", methods=["PUT"])
@require_api_key
@validate_json()
@log_request("更新FRP开关设置")
@rate_limit(max_per_min=20)
def update_frp_settings():
    payload = dict(g.json or {})
    allowed_fields = set(_FRP_SETTING_FIELD_MAP.keys())
    updates = {k: payload[k] for k in payload.keys() if k in allowed_fields}
    if not updates:
        return error("未提供可更新的 FRP 设置字段", 400)

    if "enabled" in updates and not isinstance(updates["enabled"], bool):
        return error("字段 enabled 必须为布尔值", 400)
    if "use_domain" in updates and not isinstance(updates["use_domain"], bool):
        return error("字段 use_domain 必须为布尔值", 400)

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
            return error(f"字段 {field} 必须为整数", 400)
        if cast_value <= 0:
            return error(f"字段 {field} 必须大于 0", 400)
        updates[field] = cast_value

    str_fields = ["server_addr", "admin_ip", "admin_user", "admin_password", "domain_suffix"]
    for field in str_fields:
        if field in updates:
            if not isinstance(updates[field], str):
                return error(f"字段 {field} 必须为字符串", 400)
            updates[field] = updates[field].strip()

    if "enabled" in updates:
        _set_frp_enabled_runtime(bool(updates["enabled"]))
    if "server_addr" in updates:
        config.FRP_SERVER_ADDR = updates["server_addr"] or None
    if "server_port" in updates:
        config.FRP_SERVER_PORT = int(updates["server_port"])
    if "vhost_http_port" in updates:
        config.FRP_VHOST_HTTP_PORT = int(updates["vhost_http_port"]) if updates["vhost_http_port"] is not None else None
    if "admin_ip" in updates:
        config.FRP_ADMIN_IP = updates["admin_ip"] or "127.0.0.1"
    if "admin_port" in updates:
        config.FRP_ADMIN_PORT = int(updates["admin_port"])
    if "admin_user" in updates:
        config.FRP_ADMIN_USER = updates["admin_user"] or None
    if "admin_password" in updates:
        config.FRP_ADMIN_PASSWORD = updates["admin_password"] or None
    if "use_domain" in updates:
        config.FRP_USE_DOMAIN = bool(updates["use_domain"])
    if "domain_suffix" in updates:
        config.FRP_DOMAIN_SUFFIX = updates["domain_suffix"] or None

    config.FRP_ADMIN_ADDR = f"http://{config.FRP_ADMIN_IP}:{config.FRP_ADMIN_PORT}"

    persisted, persist_msg = _persist_frp_settings_values(updates)
    data = _build_frp_settings_payload()
    data["persisted"] = persisted
    if persist_msg:
        data["persist_message"] = persist_msg
    msg = "FRP设置更新成功" if persisted else "FRP设置更新成功（仅当前进程生效）"
    return success(data, msg)


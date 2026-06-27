"""FRP代理管理路由"""
import logging
import socket
from typing import Dict
from flask import Blueprint, g
from services.frp.redact import redact_frp_config_toml
from services.frp import (
    get_frp_config,
    get_proxy_config,
    list_proxies,
    add_proxy_config,
    update_proxy_config,
    delete_proxy_config,
    reload_frp_config,
    FRPConfigError,
)
from config import config
import services.runtime_settings as runtime_settings
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
            "config": redact_frp_config_toml(config_content),
            "config_redacted": True,
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
    return success(runtime_settings.get_frp_settings(), "获取FRP设置成功")


@bp.route("/frp/settings", methods=["PUT"])
@require_api_key
@validate_json()
@log_request("更新FRP开关设置")
@rate_limit(max_per_min=20)
def update_frp_settings():
    validation_error, result = runtime_settings.update_frp_settings(g.json or {})
    if validation_error:
        return error(validation_error, 400)
    message, data = result
    return success(data, message)


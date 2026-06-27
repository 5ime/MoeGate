"""系统设置相关路由。"""

from flask import Blueprint, g

from core.responses import error, success
from middleware import rate_limit, require_api_key, validate_json
import services.runtime_settings as runtime_settings

bp = Blueprint("system_settings", __name__, url_prefix="/api/v1")


@bp.route("/settings/image-source", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_image_source_setting():
    return success(runtime_settings.get_image_source_setting(), "获取镜像源设置成功")


@bp.route("/settings/image-source", methods=["PUT"])
@require_api_key
@validate_json(required=["image_source"])
@rate_limit(max_per_min=20)
def update_image_source_setting():
    validation_error, result = runtime_settings.update_image_source(g.json or {})
    if validation_error:
        return error(validation_error, 400)
    message, data = result
    return success(data, message)


@bp.route("/settings/webui", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_webui_settings():
    return success(runtime_settings.get_webui_settings(), "获取 WebUI 设置成功")


@bp.route("/settings/container-defaults", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_container_defaults_setting():
    return success(runtime_settings.get_container_defaults(), "获取容器默认配置成功")


@bp.route("/settings/networking", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_networking_settings():
    return success(runtime_settings.get_networking_settings(), "获取网络设置成功")


@bp.route("/settings/webui", methods=["PUT"])
@require_api_key
@validate_json(required=["api_base", "poll_interval_sec"])
@rate_limit(max_per_min=20)
def update_webui_settings():
    validation_error, result = runtime_settings.update_webui_settings(g.json or {})
    if validation_error:
        return error(validation_error, 400)
    message, data = result
    return success(data, message)


@bp.route("/settings/networking", methods=["PUT"])
@require_api_key
@validate_json(required=["compose_managed_subnet_pool", "compose_managed_subnet_prefix"])
@rate_limit(max_per_min=20)
def update_networking_settings():
    validation_error, result = runtime_settings.update_networking_settings(g.json or {})
    if validation_error:
        return error(validation_error, 400)
    message, data = result
    return success(data, message)

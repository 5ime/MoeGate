"""系统告警设置相关路由。"""

from flask import Blueprint, g

from core.responses import error, success
from middleware import rate_limit, require_api_key, validate_json
import services.runtime_settings as runtime_settings

bp = Blueprint("system_alerts", __name__, url_prefix="/api/v1")


@bp.route("/settings/alerts/webhook", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_alert_webhook_setting():
    return success(runtime_settings.get_alert_webhook_settings(), "获取告警 Webhook 设置成功")


@bp.route("/settings/alerts/webhook", methods=["PUT"])
@require_api_key
@validate_json()
@rate_limit(max_per_min=20)
def update_alert_webhook_setting():
    validation_error, result = runtime_settings.update_alert_webhook(g.json or {})
    if validation_error:
        return error(validation_error, 400)
    message, data = result
    return success(data, message)

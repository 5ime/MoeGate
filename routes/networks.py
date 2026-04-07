"""受管网络路由。"""
from flask import Blueprint, g

from core.exceptions import ContainerServiceError
from core.responses import exception, success
from middleware import log_request, rate_limit, require_api_key, validate_json
from services.network import (
    create_managed_network,
    delete_managed_network,
    get_managed_network_detail,
    list_managed_networks,
    update_managed_network,
)

bp = Blueprint("networks", __name__, url_prefix="/api/v1")


def handle_service_call(func, success_message: str = "操作成功", success_code: int = 200, *args, **kwargs):
    try:
        data = func(*args, **kwargs)
        return success(data, success_message, code=success_code)
    except ContainerServiceError as exc:
        return exception(exc)


@bp.route("/networks", methods=["GET"])
@require_api_key
@log_request("获取受管网络列表")
@rate_limit(max_per_min=60)
def get_networks():
    return handle_service_call(list_managed_networks, "获取受管网络列表成功")


@bp.route("/networks/<network_id>", methods=["GET"])
@require_api_key
@log_request("获取受管网络详情")
@rate_limit(max_per_min=60)
def get_network(network_id: str):
    return handle_service_call(get_managed_network_detail, "获取受管网络详情成功", 200, network_id)


@bp.route("/networks", methods=["POST"])
@require_api_key
@validate_json(required=["name"])
@log_request("创建受管网络")
@rate_limit(max_per_min=20)
def create_network():
    payload = dict(g.json or {})
    return handle_service_call(create_managed_network, "受管网络创建成功", 201, payload)


@bp.route("/networks/<network_id>", methods=["PUT"])
@require_api_key
@validate_json()
@log_request("更新受管网络")
@rate_limit(max_per_min=20)
def update_network(network_id: str):
    payload = dict(g.json or {})
    return handle_service_call(update_managed_network, "受管网络更新成功", 200, network_id, payload)


@bp.route("/networks/<network_id>", methods=["DELETE"])
@require_api_key
@log_request("删除受管网络")
@rate_limit(max_per_min=20)
def delete_network(network_id: str):
    return handle_service_call(delete_managed_network, "受管网络删除成功", 200, network_id)

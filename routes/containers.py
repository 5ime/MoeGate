"""容器管理路由"""
import logging
from flask import Blueprint, request, g, Response, send_file
from services.container import (
    start_container,
    start_container_streaming,
    list_containers,
    restart_container,
    restart_compose_project,
    restart_any,
    stop_container,
    stop_compose_project,
    stop_any,
    get_destroy_status,
    get_compose_project_destroy_status,
    renew_task,
    renew_compose_project,
    renew_any,
    get_container_detail,
    get_compose_project_detail,
)
from middleware import (
    validate_json,
    log_request,
    rate_limit,
    require_api_key,
    get_client_ip,
)
from core.route_helpers import handle_service_call
from core.sse_helpers import iter_sse_events
from core.responses import error, success
from config import config

bp = Blueprint("containers", __name__, url_prefix="/api/v1")
logger = logging.getLogger(__name__)

_SSE_INTERNAL_ERROR_MSG = "流式操作失败，请稍后重试"


@bp.route("/containers", methods=["POST"])
@require_api_key
@validate_json()
@log_request("创建容器")
@rate_limit(max_per_min=30)
def create_container():
    """创建容器。"""
    dto = dict(g.json or {})
    dto["_meta"] = {
        "request_id": getattr(g, "request_id", None),
        "source_ip": get_client_ip(),
        "created_by": request.headers.get("X-User-Id") or request.headers.get("X-Operator-Id"),
    }
    return handle_service_call(start_container, "容器创建成功", 200, dto, app_config=config)


@bp.route("/containers/stream", methods=["POST"])
@require_api_key
@validate_json()
@log_request("创建容器(流式)")
@rate_limit(max_per_min=30)
def create_container_stream():
    """创建容器（SSE 流式输出构建日志）。"""
    dto = dict(g.json or {})
    dto["_meta"] = {
        "request_id": getattr(g, "request_id", None),
        "source_ip": get_client_ip(),
        "created_by": request.headers.get("X-User-Id") or request.headers.get("X-Operator-Id"),
    }
    max_events = int(getattr(config, "SSE_MAX_LOG_EVENTS", 2000) or 2000)
    max_line_len = int(getattr(config, "SSE_MAX_LOG_LINE_LENGTH", 2000) or 2000)

    def generate():
        yield from iter_sse_events(
            start_container_streaming(dto, app_config=config),
            max_events=max_events,
            max_line_len=max_line_len,
            internal_error_msg=_SSE_INTERNAL_ERROR_MSG,
            logger=logger,
        )

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/containers", methods=["GET"])
@require_api_key
@log_request("获取容器列表")
@rate_limit(max_per_min=60)
def get_containers():
    """获取容器列表。"""
    return handle_service_call(list_containers, "获取容器列表成功")


@bp.route("/containers/<container_id>", methods=["GET"])
@require_api_key
@log_request("获取容器详情")
@rate_limit(max_per_min=60)
def get_container(container_id: str):
    """获取容器详情。"""
    verbose = str(request.args.get("verbose", "")).strip().lower() in {"1", "true", "yes", "on"}
    dto = {"container_id": container_id, "verbose": verbose}
    return handle_service_call(
        lambda payload: get_container_detail(payload["container_id"], verbose=payload["verbose"]),
        "获取容器详情成功",
        200,
        dto
    )


@bp.route("/containers/project/<compose_project_id>", methods=["GET"])
@require_api_key
@log_request("获取Compose项目详情")
@rate_limit(max_per_min=60)
def get_compose_project(compose_project_id: str):
    """获取 Compose 项目详情。"""
    verbose = str(request.args.get("verbose", "")).strip().lower() in {"1", "true", "yes", "on"}
    dto = {"compose_project_id": compose_project_id, "verbose": verbose}
    return handle_service_call(
        lambda payload: get_compose_project_detail(
            payload["compose_project_id"],
            verbose=payload["verbose"],
        ),
        "获取Compose项目详情成功",
        200,
        dto,
    )


@bp.route("/containers/<container_id>", methods=["PATCH"])
@require_api_key
@log_request("重启容器")
@rate_limit(max_per_min=30)
def update_container(container_id: str):
    """重启容器。"""
    dto = {"container_id": container_id}
    return handle_service_call(restart_container, "容器重启成功", 200, dto)


@bp.route("/containers/<container_id>", methods=["DELETE"])
@require_api_key
@log_request("删除容器")
@rate_limit(max_per_min=30)
def delete_container(container_id: str):
    """删除容器（异步任务，返回 202）。"""
    dto = {"container_id": container_id}
    return handle_service_call(stop_container, "容器删除任务已提交", 202, dto)


@bp.route("/containers/project/<compose_project_id>", methods=["DELETE"])
@require_api_key
@log_request("删除Compose项目")
@rate_limit(max_per_min=30)
def delete_compose_project(compose_project_id: str):
    """删除 Compose 项目（停止并删除项目下全部容器）。"""
    dto = {"compose_project_id": compose_project_id}
    return handle_service_call(stop_compose_project, "Compose项目删除任务已提交", 202, dto)


@bp.route("/containers/destroy/<entity_id>", methods=["DELETE"])
@require_api_key
@log_request("删除实体(自动识别容器/项目)")
@rate_limit(max_per_min=30)
def delete_any(entity_id: str):
    """统一删除入口：自动识别是 Compose 项目还是单容器（异步任务，返回 202）。"""
    dto = {"id": entity_id}
    return handle_service_call(stop_any, "删除任务已提交", 202, dto)


@bp.route("/containers/restart/<entity_id>", methods=["PATCH"])
@require_api_key
@log_request("重启实体(自动识别容器/项目)")
@rate_limit(max_per_min=30)
def restart_any_route(entity_id: str):
    """统一重启入口：自动识别是 Compose 项目还是单容器。"""
    dto = {"id": entity_id}
    return handle_service_call(restart_any, "重启成功", 200, dto)


@bp.route("/containers/renew/<entity_id>", methods=["POST"])
@require_api_key
@log_request("续期实体(自动识别容器/项目)")
@rate_limit(max_per_min=30)
def renew_any_route(entity_id: str):
    """统一续期入口：自动识别是 Compose 项目还是单容器。"""
    dto = {"id": entity_id}
    return handle_service_call(renew_any, "续期成功", 200, dto, app_config=config)


@bp.route("/containers/<container_id>/destroy-status", methods=["GET"])
@require_api_key
@log_request("获取容器删除任务状态")
@rate_limit(max_per_min=60)
def get_container_destroy_status(container_id: str):
    """获取容器删除任务状态。"""
    dto = {"container_id": container_id}
    return handle_service_call(get_destroy_status, "获取容器删除任务状态成功", 200, dto)


@bp.route("/containers/project/<compose_project_id>/destroy-status", methods=["GET"])
@require_api_key
@log_request("获取Compose项目删除任务状态")
@rate_limit(max_per_min=60)
def get_compose_project_destroy_status_route(compose_project_id: str):
    """获取 Compose 项目删除任务状态。"""
    dto = {"compose_project_id": compose_project_id}
    return handle_service_call(get_compose_project_destroy_status, "获取Compose项目删除任务状态成功", 200, dto)


@bp.route("/containers/project/<compose_project_id>", methods=["PATCH"])
@require_api_key
@log_request("重启Compose项目")
@rate_limit(max_per_min=30)
def update_compose_project(compose_project_id: str):
    """重启 Compose 项目（重启项目下全部容器）。"""
    dto = {"compose_project_id": compose_project_id}
    return handle_service_call(restart_compose_project, "Compose项目重启成功", 200, dto)


@bp.route("/containers/project/<compose_project_id>/renew", methods=["POST"])
@require_api_key
@log_request("续期Compose项目")
@rate_limit(max_per_min=30)
def renew_compose_project_route(compose_project_id: str):
    """续期 Compose 项目（续期项目下全部容器）。"""
    dto = {"compose_project_id": compose_project_id}
    return handle_service_call(renew_compose_project, "Compose项目续期成功", 200, dto, app_config=config)


@bp.route("/containers/<container_id>/renew", methods=["POST"])
@require_api_key
@log_request("续期容器")
@rate_limit(max_per_min=30)
def renew_container(container_id: str):
    """续期容器。"""
    dto = {"container_id": container_id}
    return handle_service_call(renew_task, "容器续期成功", 200, dto, app_config=config)



@bp.route("/containers/<container_id>/traffic", methods=["GET"])
@require_api_key
@log_request("获取容器流量取证状态")
@rate_limit(max_per_min=60)
def get_container_traffic(container_id: str):
    """查看取证 sidecar 状态与已落盘 pcap 列表。"""
    from services.container.tap import get_capture_status

    return handle_service_call(get_capture_status, "获取流量取证信息成功", 200, container_id)


@bp.route("/containers/<container_id>/traffic/summary", methods=["GET"])
@require_api_key
@log_request("生成容器流量取证摘要")
@rate_limit(max_per_min=20)
def get_container_traffic_summary(container_id: str):
    """基于 pcap 生成取证摘要（HTTP 明文、客户端画像、自动化特征）。"""
    from services.container.tap import get_capture_summary

    try:
        max_packets = int(request.args.get("max_packets", 50000))
    except (TypeError, ValueError):
        max_packets = 50000
    try:
        max_http = int(request.args.get("max_http", 200))
    except (TypeError, ValueError):
        max_http = 200

    max_packets = min(max(max_packets, 1000), 500000)
    max_http = min(max(max_http, 0), 2000)

    return handle_service_call(
        get_capture_summary,
        "生成流量取证摘要成功",
        200,
        container_id,
        max_packets,
        max_http,
    )


@bp.route("/containers/<container_id>/traffic/start", methods=["POST"])
@require_api_key
@log_request("开启容器流量取证")
@rate_limit(max_per_min=30)
def start_container_traffic(container_id: str):
    """手动开启取证（默认在容器创建时自动开启）。"""
    from services.container.tap import start_capture

    return handle_service_call(start_capture, "流量取证已开启", 200, container_id)


@bp.route("/containers/<container_id>/traffic/stop", methods=["POST"])
@require_api_key
@log_request("停止容器流量取证")
@rate_limit(max_per_min=30)
def stop_container_traffic(container_id: str):
    """停止取证 sidecar，已抓取的 pcap 保留。"""
    from services.container.tap import stop_capture

    return handle_service_call(stop_capture, "流量取证已停止", 200, container_id)


@bp.route("/containers/<container_id>/traffic/<path:filename>", methods=["GET"])
@require_api_key
@log_request("下载容器流量 pcap")
@rate_limit(max_per_min=30)
def download_container_traffic(container_id: str, filename: str):
    """下载指定 pcap 文件。"""
    from services.container.tap import resolve_capture_file

    path = resolve_capture_file(container_id, filename)
    if path is None:
        return error("流量文件不存在", 404)
    return send_file(
        str(path),
        mimetype="application/vnd.tcpdump.pcap",
        as_attachment=True,
        download_name=path.name,
    )

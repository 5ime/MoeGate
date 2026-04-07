"""容器管理路由"""
import json
from flask import Blueprint, request, g, Response
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
from core.responses import (
    success,
    exception,
)
from core.exceptions import (
    ContainerServiceError,
)
from config import config

bp = Blueprint("containers", __name__, url_prefix="/api/v1")


def handle_service_call(func, success_message: str = "操作成功", success_code: int = 200, *args, **kwargs):
    """调用服务函数并统一封装响应。"""
    try:
        data = func(*args, **kwargs)
        return success(data, success_message, code=success_code)
    except ContainerServiceError as e:
        return exception(e)
    # 其余异常交给全局 errorhandler 处理


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
        emitted_events = 0
        try:
            for item in start_container_streaming(dto, app_config=config):
                if isinstance(item, (dict, list)):
                    yield f"event: result\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
                    emitted_events += 1
                else:
                    text = str(item)
                    if len(text) > max_line_len:
                        text = f"{text[:max_line_len]}... [truncated]"
                    yield f"event: log\ndata: {text}\n\n"
                    emitted_events += 1

                if emitted_events >= max_events:
                    yield (
                        "event: error\ndata: "
                        + json.dumps(
                            {
                                "msg": f"SSE日志事件超过上限({max_events})，已提前终止",
                                "code": 429,
                            },
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                    break
        except ContainerServiceError as e:
            yield f"event: error\ndata: {json.dumps({'msg': e.message, 'code': e.code}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'msg': str(e), 'code': 500}, ensure_ascii=False)}\n\n"

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
    dto = {"container_id": container_id}
    return handle_service_call(
        lambda payload: get_container_detail(payload["container_id"]),
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
    dto = {"compose_project_id": compose_project_id}
    return handle_service_call(
        lambda payload: get_compose_project_detail(payload["compose_project_id"]),
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


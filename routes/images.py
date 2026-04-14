"""镜像管理路由。"""
import json
from flask import Blueprint, g, request, Response

from core.exceptions import ContainerServiceError
from core.responses import exception, success
from middleware import log_request, rate_limit, require_api_key, validate_json
from services.image import delete_image, get_image_detail, list_images, pull_image, pull_image_streaming, prune_images
from config import config

bp = Blueprint("images", __name__, url_prefix="/api/v1")


def handle_service_call(func, success_message: str = "操作成功", success_code: int = 200, *args, **kwargs):
    try:
        data = func(*args, **kwargs)
        return success(data, success_message, code=success_code)
    except ContainerServiceError as exc:
        return exception(exc)


@bp.route("/images", methods=["GET"])
@require_api_key
@log_request("获取镜像列表")
@rate_limit(max_per_min=60)
def get_images():
    return handle_service_call(list_images, "获取镜像列表成功")


@bp.route("/images/detail/<path:image_ref>", methods=["GET"])
@require_api_key
@log_request("获取镜像详情")
@rate_limit(max_per_min=60)
def get_image(image_ref: str):
    return handle_service_call(get_image_detail, "获取镜像详情成功", 200, image_ref)


@bp.route("/images/pull", methods=["POST"])
@require_api_key
@validate_json(required=["image"])
@log_request("拉取镜像")
@rate_limit(max_per_min=20)
def pull_image_route():
    payload = dict(g.json or {})
    return handle_service_call(pull_image, "镜像拉取成功", 200, payload.get("image"))


@bp.route("/images/pull/stream", methods=["POST"])
@require_api_key
@validate_json(required=["image"])
@log_request("拉取镜像(流式)")
@rate_limit(max_per_min=20)
def pull_image_stream_route():
    payload = dict(g.json or {})
    max_events = int(getattr(config, "SSE_MAX_LOG_EVENTS", 2000) or 2000)
    max_line_len = int(getattr(config, "SSE_MAX_LOG_LINE_LENGTH", 2000) or 2000)

    def generate():
        emitted_events = 0
        try:
            for item in pull_image_streaming(payload.get("image"), app_config=config):
                if isinstance(item, dict):
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
        except ContainerServiceError as exc:
            yield f"event: error\ndata: {json.dumps({'msg': exc.message, 'code': exc.code}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'msg': str(exc), 'code': 500}, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/images/prune", methods=["POST"])
@require_api_key
@log_request("清理悬空镜像")
@rate_limit(max_per_min=10)
def prune_images_route():
    return handle_service_call(prune_images, "悬空镜像清理成功")


@bp.route("/images/<path:image_ref>", methods=["DELETE"])
@require_api_key
@log_request("删除镜像")
@rate_limit(max_per_min=20)
def delete_image_route(image_ref: str):
    force = str(request.args.get("force", "")).strip().lower() in {"1", "true", "yes", "on"}
    return handle_service_call(delete_image, "镜像删除成功", 200, image_ref, force)
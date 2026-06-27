"""Prometheus metrics 访问控制"""
import hmac
from typing import Optional

from flask import request, Response

from config import config


def metrics_endpoint_enabled() -> bool:
    return bool(getattr(config, "ENABLE_PUBLIC_METRICS", False) or getattr(config, "METRICS_TOKEN", None))


def check_metrics_access() -> Optional[Response]:
    """校验 /metrics 访问权限；通过时返回 None。"""
    if not metrics_endpoint_enabled():
        return Response("Not Found", 404)

    token = getattr(config, "METRICS_TOKEN", None)
    if not token:
        return Response("Unauthorized", 401)

    # 仅接受 Header，避免 token 出现在 URL、访问日志与 Referer 中
    provided = request.headers.get("X-Metrics-Token")
    if provided and hmac.compare_digest(str(provided), str(token)):
        return None
    return Response("Unauthorized", 401)

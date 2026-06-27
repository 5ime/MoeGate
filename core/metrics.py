"""Prometheus 指标生成"""
from flask import Response

from config import config
from infra.docker import ensure_client


def render_prometheus_metrics() -> Response:
    """生成 Prometheus 文本格式指标响应。"""
    alert_webhook_enabled = 1 if config.ALERT_WEBHOOK_URL else 0

    docker_running = 0
    docker_total = 0
    try:
        client = ensure_client()
        if client:
            info = client.info()
            docker_running = int(info.get("ContainersRunning", 0) or 0)
            docker_total = int(info.get("Containers", 0) or 0)
    except Exception:
        pass

    lines = [
        "# HELP moegate_alert_webhook_enabled Whether alert webhook is configured",
        "# TYPE moegate_alert_webhook_enabled gauge",
        f"moegate_alert_webhook_enabled {alert_webhook_enabled}",
        "# HELP moegate_docker_containers_total Docker containers total",
        "# TYPE moegate_docker_containers_total gauge",
        f"moegate_docker_containers_total {docker_total}",
        "# HELP moegate_docker_containers_running Docker containers running",
        "# TYPE moegate_docker_containers_running gauge",
        f"moegate_docker_containers_running {docker_running}",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")

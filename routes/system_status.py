"""系统状态与告警相关路由。"""

import logging
import platform
import time

from flask import Blueprint

from config import config
from core.responses import error, success
from middleware import rate_limit, require_api_key
from utils.alerts import collect_runtime_snapshot, send_webhook_alert

bp = Blueprint("system_status", __name__, url_prefix="/api/v1")
logger = logging.getLogger(__name__)


@bp.route("/metrics", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_metrics():
    """WebUI 用：经 API 认证返回 Prometheus 文本指标。"""
    from core.metrics import render_prometheus_metrics

    return render_prometheus_metrics()


@bp.route("/status", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_status():
    """获取服务器状态信息。"""
    try:
        sys_info = platform.uname()
        snapshot = collect_runtime_snapshot()
        sys_s = (snapshot or {}).get("system") or {}
        docker_s = (snapshot or {}).get("docker") or {}

        docker_ver = str(docker_s.get("docker_version") or "").strip()
        if not docker_ver or docker_ver.lower() == "unavailable":
            docker_ver = "不可用"
        running = int(docker_s.get("containers_running", 0) or 0)
        total = int(docker_s.get("containers_total", 0) or 0)
        standalone_count = int(docker_s.get("standalone_managed", 0) or 0)
        compose_count = int(docker_s.get("compose_managed", 0) or 0)

        app_version = getattr(config, "APP_VERSION", "0.1.0")

        release_raw = sys_info.release or ""
        release_short = (release_raw.split("-")[0] or release_raw).strip()
        system_name = sys_info.system or ""
        version_raw = getattr(sys_info, "version", "") or ""
        combined = f"{release_raw} {version_raw}".lower()
        if "wsl2" in combined:
            display_system = "WSL2"
        elif ("microsoft" in combined) or ("wsl" in combined):
            display_system = "WSL"
        else:
            display_system = system_name

        data = {
            "system": f"{display_system} {release_short}",
            "cpu_cores": sys_s.get("cpu_cores"),
            "cpu_usage": sys_s.get("cpu_usage"),
            "memory_total": sys_s.get("memory_total"),
            "memory_usage": sys_s.get("memory_usage"),
            "disk_total": sys_s.get("disk_total"),
            "disk_used": sys_s.get("disk_used"),
            "disk_usage": sys_s.get("disk_usage"),
            "docker_version": docker_ver,
            "containers_running": running,
            "containers_total": total,
            "standalone_containers": standalone_count,
            "compose_containers": compose_count,
            "app_version": app_version,
        }

        return success(data, "获取服务器状态成功")
    except Exception as exc:
        logger.error("获取服务器状态失败: %s", exc)
        return error("获取服务器状态失败", 500)


@bp.route("/alerts/test", methods=["POST"])
@require_api_key
@rate_limit(max_per_min=10)
def trigger_test_alert():
    """手动触发一次告警（用于验证飞书/通用 webhook 配置）。"""
    try:
        ok = send_webhook_alert(
            "manual_test",
            {
                "message": "这是一条手动测试告警",
                "ts": int(time.time()),
            },
        )
        if ok:
            return success({"sent": True}, "告警测试已发送")
        return success({"sent": False}, "未发送（可能未配置 ALERT_WEBHOOK_URL 或发送失败）")
    except Exception as exc:
        logger.warning("告警测试触发失败: %s", exc)
        return error("告警测试触发失败", 500)

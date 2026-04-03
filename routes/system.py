"""系统状态路由"""
import logging
import platform
import time
from dotenv import find_dotenv, set_key, unset_key, dotenv_values
from flask import Blueprint, Response, g, request
from middleware import (
    rate_limit,
    require_api_key,
    validate_json,
)
from core.responses import (
    error,
    success,
)
from infra.docker import ensure_client
from config import config
from utils.alerts import send_webhook_alert, collect_runtime_snapshot

bp = Blueprint("system", __name__, url_prefix="/api/v1")
logger = logging.getLogger(__name__)


def _unset_key_if_exists(env_path: str, key: str) -> None:
    """仅当 .env 存在该键时才 unset，避免 python-dotenv 的无意义告警。"""
    try:
        values = dotenv_values(env_path) or {}
        if key not in values:
            return
    except Exception:
        # 读取失败时回退到直接 unset（保持行为一致）
        pass
    unset_key(env_path, key)


def _persist_image_source_setting(image_source: str):
    """持久化 IMAGE_SOURCE 到 .env（为空时删除该键）"""
    if not getattr(config, "ALLOW_RUNTIME_CONFIG_WRITE", False):
        return False, "已禁用运行时配置写入（ALLOW_RUNTIME_CONFIG_WRITE=False）"
    try:
        env_path = find_dotenv(filename=".env", usecwd=True)
        if not env_path:
            return False, "未找到 .env，当前仅进程内生效"

        if image_source:
            set_key(env_path, "IMAGE_SOURCE", image_source, quote_mode="never")
        else:
            _unset_key_if_exists(env_path, "IMAGE_SOURCE")

        return True, ""
    except Exception as exc:
        logger.warning("持久化 IMAGE_SOURCE 失败: %s", exc)
        return False, f"持久化失败: {exc}"


def _persist_webui_settings(api_base: str, poll_interval_sec: int, max_containers: int, max_renew_times: int):
    """持久化 WebUI 设置到 .env。"""
    if not getattr(config, "ALLOW_RUNTIME_CONFIG_WRITE", False):
        return False, "已禁用运行时配置写入（ALLOW_RUNTIME_CONFIG_WRITE=False）"
    try:
        env_path = find_dotenv(filename=".env", usecwd=True)
        if not env_path:
            return False, "未找到 .env，当前仅进程内生效"

        api_base_value = (api_base or "").strip()
        if api_base_value:
            set_key(env_path, "WEBUI_API_BASE", api_base_value, quote_mode="never")
        else:
            _unset_key_if_exists(env_path, "WEBUI_API_BASE")

        set_key(env_path, "WEBUI_POLL_INTERVAL_SEC", str(poll_interval_sec), quote_mode="never")
        set_key(env_path, "MAX_CONTAINERS", str(max_containers), quote_mode="never")
        set_key(env_path, "MAX_RENEW_TIMES", str(max_renew_times), quote_mode="never")
        return True, ""
    except Exception as exc:
        logger.warning("持久化 WEBUI 设置失败: %s", exc)
        return False, f"持久化失败: {exc}"


def _persist_alert_webhook_setting(webhook_url: str):
    """持久化 ALERT_WEBHOOK_URL 到 .env（为空时删除该键）"""
    if not getattr(config, "ALLOW_RUNTIME_CONFIG_WRITE", False):
        return False, "已禁用运行时配置写入（ALLOW_RUNTIME_CONFIG_WRITE=False）"
    try:
        env_path = find_dotenv(filename=".env", usecwd=True)
        if not env_path:
            return False, "未找到 .env，当前仅进程内生效"

        if webhook_url:
            set_key(env_path, "ALERT_WEBHOOK_URL", webhook_url, quote_mode="never")
        else:
            unset_key(env_path, "ALERT_WEBHOOK_URL")

        return True, ""
    except Exception as exc:
        logger.warning("持久化 ALERT_WEBHOOK_URL 失败: %s", exc)
        return False, f"持久化失败: {exc}"


def _persist_alert_webhook_timeout_setting(timeout_sec: int):
    """持久化 ALERT_WEBHOOK_TIMEOUT 到 .env。"""
    if not getattr(config, "ALLOW_RUNTIME_CONFIG_WRITE", False):
        return False, "已禁用运行时配置写入（ALLOW_RUNTIME_CONFIG_WRITE=False）"
    try:
        env_path = find_dotenv(filename=".env", usecwd=True)
        if not env_path:
            return False, "未找到 .env，当前仅进程内生效"

        set_key(env_path, "ALERT_WEBHOOK_TIMEOUT", str(timeout_sec), quote_mode="never")
        return True, ""
    except Exception as exc:
        logger.warning("持久化 ALERT_WEBHOOK_TIMEOUT 失败: %s", exc)
        return False, f"持久化失败: {exc}"


def _persist_alert_perf_settings(values: dict):
    """批量持久化性能/告警相关设置到 .env。"""
    if not getattr(config, "ALLOW_RUNTIME_CONFIG_WRITE", False):
        return False, "已禁用运行时配置写入（ALLOW_RUNTIME_CONFIG_WRITE=False）"
    try:
        env_path = find_dotenv(filename=".env", usecwd=True)
        if not env_path:
            return False, "未找到 .env，当前仅进程内生效"
        for key, val in (values or {}).items():
            set_key(env_path, key, str(val), quote_mode="never")
        return True, ""
    except Exception as exc:
        logger.warning("持久化性能/告警设置失败: %s", exc)
        return False, f"持久化失败: {exc}"


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

        # 缩短内核版本显示
        release_raw = sys_info.release or ""
        release_short = (release_raw.split("-")[0] or release_raw).strip()
        system_name = sys_info.system or ""
        # 检测 WSL/WSL2，并用更直观的系统名显示
        version_raw = getattr(sys_info, "version", "") or ""
        _combined = f"{release_raw} {version_raw}".lower()
        if "wsl2" in _combined:
            display_system = "WSL2"
        elif ("microsoft" in _combined) or ("wsl" in _combined):
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
            # 前端阈值展示所需（从 env/config 读取）
            "alert_cpu_threshold": int(getattr(config, "ALERT_CPU_THRESHOLD", 95) or 95),
            "alert_cpu_sustained_intervals": int(getattr(config, "ALERT_CPU_SUSTAINED_INTERVALS", 3) or 3),
            "alert_mem_threshold": int(getattr(config, "ALERT_MEM_THRESHOLD", 90) or 90),
            "alert_mem_sustained_intervals": int(getattr(config, "ALERT_MEM_SUSTAINED_INTERVALS", 3) or 3),
            "alert_cooldown_sec": int(getattr(config, "ALERT_COOLDOWN_SEC", 900) or 900),
            "enable_performance_monitoring": bool(getattr(config, "ENABLE_PERFORMANCE_MONITORING", False)),
            "performance_log_interval": int(getattr(config, "PERFORMANCE_LOG_INTERVAL", 300) or 300),
        }

        return success(data, "获取服务器状态成功")
        
    except Exception as e:
        logger.error("获取服务器状态失败: %s", e)
        return error("获取服务器状态失败", 500)


@bp.route("/metrics", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=60)
def get_metrics():
    """Prometheus 文本格式指标。"""
    try:
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
    except Exception as e:
        logger.error("获取指标失败: %s", e)
        return error("获取指标失败", 500)


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
    except Exception as e:
        logger.warning("告警测试触发失败: %s", e)
        return error(f"告警测试触发失败: {e}", 500)


@bp.route("/settings/alerts/webhook", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_alert_webhook_setting():
    """获取告警 webhook 设置。"""
    return success(
        {
            "webhook_url": (config.ALERT_WEBHOOK_URL or ""),
            "webhook_timeout": int(getattr(config, "ALERT_WEBHOOK_TIMEOUT", 5) or 5),
        },
        "获取告警 Webhook 设置成功",
    )


@bp.route("/settings/alerts/webhook", methods=["PUT"])
@require_api_key
@validate_json(required=["webhook_url"])
@rate_limit(max_per_min=20)
def update_alert_webhook_setting():
    """更新告警 webhook 设置，并尝试持久化到 .env。"""
    webhook_url_raw = g.json.get("webhook_url")
    if not isinstance(webhook_url_raw, str):
        return error("字段 webhook_url 必须为字符串", 400)

    webhook_url = webhook_url_raw.strip()
    config.ALERT_WEBHOOK_URL = webhook_url or None

    webhook_timeout_raw = g.json.get("webhook_timeout", None)
    timeout_sec = None
    if webhook_timeout_raw is not None:
        try:
            timeout_sec = int(webhook_timeout_raw)
        except (TypeError, ValueError):
            return error("字段 webhook_timeout 必须为正整数", 400)
        if timeout_sec <= 0:
            return error("字段 webhook_timeout 必须为正整数", 400)
        config.ALERT_WEBHOOK_TIMEOUT = timeout_sec

    persisted_url, persist_msg_url = _persist_alert_webhook_setting(webhook_url)
    persisted_timeout = None
    persist_msg_timeout = ""
    if timeout_sec is not None:
        persisted_timeout, persist_msg_timeout = _persist_alert_webhook_timeout_setting(timeout_sec)

    persisted = bool(persisted_url and (persisted_timeout if persisted_timeout is not None else True))
    persist_msg = persist_msg_url or persist_msg_timeout
    data = {
        "webhook_url": webhook_url,
        "webhook_timeout": int(getattr(config, "ALERT_WEBHOOK_TIMEOUT", 5) or 5),
        "persisted": persisted,
    }
    if persist_msg:
        data["persist_message"] = persist_msg

    msg = "告警 Webhook 设置更新成功" if persisted else "告警 Webhook 设置更新成功（仅当前进程生效）"
    return success(data, msg)


@bp.route("/settings/image-source", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_image_source_setting():
    """获取全局镜像源设置"""
    return success({"image_source": (config.IMAGE_SOURCE or "")}, "获取镜像源设置成功")


@bp.route("/settings/image-source", methods=["PUT"])
@require_api_key
@validate_json(required=["image_source"])
@rate_limit(max_per_min=20)
def update_image_source_setting():
    """更新全局镜像源设置"""
    image_source_raw = g.json.get("image_source")
    if not isinstance(image_source_raw, str):
        return error("字段 image_source 必须为字符串", 400)

    image_source = image_source_raw.strip()
    config.IMAGE_SOURCE = image_source or None

    persisted, persist_msg = _persist_image_source_setting(image_source)
    data = {
        "image_source": image_source,
        "persisted": persisted,
    }
    if persist_msg:
        data["persist_message"] = persist_msg

    msg = "镜像源设置更新成功" if persisted else "镜像源设置更新成功（仅当前进程生效）"
    return success(data, msg)


@bp.route("/settings/webui", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_webui_settings():
    """获取 WebUI 偏好设置。"""
    data = {
        "api_base": (config.WEBUI_API_BASE or "").strip(),
        "poll_interval_sec": int(config.WEBUI_POLL_INTERVAL_SEC or 30),
        "max_containers": int(config.MAX_CONTAINERS or 30),
        "max_renew_times": int(config.MAX_RENEW_TIMES or 3),
    }
    return success(data, "获取 WebUI 设置成功")


@bp.route("/settings/container-defaults", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_container_defaults_setting():
    """获取创建容器默认参数（来源于当前配置/.env）。"""
    data = {
        "max_time": int(config.MAX_TIME or 3600),
        "min_port": int(config.MIN_PORT or 20000),
        "max_port": int(config.MAX_PORT or 30000),
        "memory_limit": str(config.CONTAINER_MEMORY_LIMIT or "512m"),
        "cpu_limit": None if config.CONTAINER_CPU_LIMIT is None else float(config.CONTAINER_CPU_LIMIT),
        "cpu_shares": int(config.CONTAINER_CPU_SHARES or 1024),
    }
    return success(data, "获取容器默认配置成功")


@bp.route("/settings/webui", methods=["PUT"])
@require_api_key
@validate_json(required=["api_base", "poll_interval_sec"])
@rate_limit(max_per_min=20)
def update_webui_settings():
    """更新 WebUI 偏好设置，并尝试持久化到 .env。"""
    api_base_raw = g.json.get("api_base")
    poll_interval_sec_raw = g.json.get("poll_interval_sec")
    max_containers_raw = g.json.get("max_containers", config.MAX_CONTAINERS)
    max_renew_times_raw = g.json.get("max_renew_times", config.MAX_RENEW_TIMES)

    if not isinstance(api_base_raw, str):
        return error("字段 api_base 必须为字符串", 400)

    try:
        poll_interval_sec = int(poll_interval_sec_raw)
    except (TypeError, ValueError):
        return error("字段 poll_interval_sec 必须为正整数", 400)

    try:
        max_containers = int(max_containers_raw)
    except (TypeError, ValueError):
        return error("字段 max_containers 必须为正整数", 400)

    try:
        max_renew_times = int(max_renew_times_raw)
    except (TypeError, ValueError):
        return error("字段 max_renew_times 必须为非负整数", 400)

    if poll_interval_sec <= 0:
        return error("字段 poll_interval_sec 必须为正整数", 400)
    if max_containers <= 0:
        return error("字段 max_containers 必须为正整数", 400)
    if max_renew_times < 0:
        return error("字段 max_renew_times 必须为非负整数", 400)

    api_base = api_base_raw.strip()
    config.WEBUI_API_BASE = api_base or None
    config.WEBUI_POLL_INTERVAL_SEC = poll_interval_sec
    config.MAX_CONTAINERS = max_containers
    config.MAX_RENEW_TIMES = max_renew_times

    persisted, persist_msg = _persist_webui_settings(api_base, poll_interval_sec, max_containers, max_renew_times)
    data = {
        "api_base": api_base,
        "poll_interval_sec": poll_interval_sec,
        "max_containers": max_containers,
        "max_renew_times": max_renew_times,
        "persisted": persisted,
    }
    if persist_msg:
        data["persist_message"] = persist_msg

    msg = "WebUI 设置更新成功" if persisted else "WebUI 设置更新成功（仅当前进程生效）"
    return success(data, msg)


@bp.route("/settings/alerts/perf", methods=["GET"])
@require_api_key
@rate_limit(max_per_min=30)
def get_alert_perf_settings():
    """获取性能/告警相关设置（用于前端展示/编辑）。"""
    data = {
        # 显示为“是否启用”，但值为推断：存在 Webhook 则启用，否则看旧的开关
        "enable_performance_monitoring": bool(getattr(config, "ALERT_WEBHOOK_URL", None)) or bool(getattr(config, "ENABLE_PERFORMANCE_MONITORING", False)),
        "performance_log_interval": int(getattr(config, "PERFORMANCE_LOG_INTERVAL", 300) or 300),
        "alert_cpu_threshold": int(getattr(config, "ALERT_CPU_THRESHOLD", 95) or 95),
        "alert_cpu_sustained_intervals": int(getattr(config, "ALERT_CPU_SUSTAINED_INTERVALS", 3) or 3),
        "alert_mem_threshold": int(getattr(config, "ALERT_MEM_THRESHOLD", 90) or 90),
        "alert_mem_sustained_intervals": int(getattr(config, "ALERT_MEM_SUSTAINED_INTERVALS", 3) or 3),
        "alert_cooldown_sec": int(getattr(config, "ALERT_COOLDOWN_SEC", 900) or 900),
    }
    return success(data, "获取性能/告警设置成功")


@bp.route("/settings/alerts/perf", methods=["PUT"])
@require_api_key
@rate_limit(max_per_min=20)
def update_alert_perf_settings():
    """更新性能/告警相关设置，并尝试持久化到 .env。所有字段均为可选，传入则更新。"""
    body = request.get_json(silent=True) or {}
    updated_env: dict = {}
    try:
        # 忽略 enable_performance_monitoring：按照业务规则仅凭 webhook 是否存在决定是否启用
        if "performance_log_interval" in body:
            ival = int(body.get("performance_log_interval"))
            if ival <= 0:
                return error("字段 performance_log_interval 必须为正整数", 400)
            config.PERFORMANCE_LOG_INTERVAL = ival
            updated_env["PERFORMANCE_LOG_INTERVAL"] = ival
        if "alert_cpu_threshold" in body:
            ival = int(body.get("alert_cpu_threshold"))
            if ival <= 0 or ival > 100:
                return error("字段 alert_cpu_threshold 必须在 1-100 之间", 400)
            config.ALERT_CPU_THRESHOLD = ival
            updated_env["ALERT_CPU_THRESHOLD"] = ival
        if "alert_cpu_sustained_intervals" in body:
            ival = int(body.get("alert_cpu_sustained_intervals"))
            if ival <= 0:
                return error("字段 alert_cpu_sustained_intervals 必须大于 0", 400)
            config.ALERT_CPU_SUSTAINED_INTERVALS = ival
            updated_env["ALERT_CPU_SUSTAINED_INTERVALS"] = ival
        if "alert_mem_threshold" in body:
            ival = int(body.get("alert_mem_threshold"))
            if ival <= 0 or ival > 100:
                return error("字段 alert_mem_threshold 必须在 1-100 之间", 400)
            config.ALERT_MEM_THRESHOLD = ival
            updated_env["ALERT_MEM_THRESHOLD"] = ival
        if "alert_mem_sustained_intervals" in body:
            ival = int(body.get("alert_mem_sustained_intervals"))
            if ival <= 0:
                return error("字段 alert_mem_sustained_intervals 必须大于 0", 400)
            config.ALERT_MEM_SUSTAINED_INTERVALS = ival
            updated_env["ALERT_MEM_SUSTAINED_INTERVALS"] = ival
        if "alert_cooldown_sec" in body:
            ival = int(body.get("alert_cooldown_sec"))
            if ival < 0:
                return error("字段 alert_cooldown_sec 不能为负数", 400)
            config.ALERT_COOLDOWN_SEC = ival
            updated_env["ALERT_COOLDOWN_SEC"] = ival
    except (TypeError, ValueError):
        return error("存在无效的数字字段，请检查参数", 400)

    persisted, persist_msg = _persist_alert_perf_settings(updated_env) if updated_env else (False, "")
    # 通知性能监控线程尽快读取新配置（例如采样间隔）
    try:
        from workers.performance import notify_performance_monitor_config_updated

        notify_performance_monitor_config_updated()
    except Exception:
        pass
    data = {
        "persisted": bool(persisted),
        "settings": {
            "enable_performance_monitoring": bool(getattr(config, "ALERT_WEBHOOK_URL", None)) or bool(getattr(config, "ENABLE_PERFORMANCE_MONITORING", False)),
            "performance_log_interval": int(getattr(config, "PERFORMANCE_LOG_INTERVAL", 300) or 300),
            "alert_cpu_threshold": int(getattr(config, "ALERT_CPU_THRESHOLD", 95) or 95),
            "alert_cpu_sustained_intervals": int(getattr(config, "ALERT_CPU_SUSTAINED_INTERVALS", 3) or 3),
            "alert_mem_threshold": int(getattr(config, "ALERT_MEM_THRESHOLD", 90) or 90),
            "alert_mem_sustained_intervals": int(getattr(config, "ALERT_MEM_SUSTAINED_INTERVALS", 3) or 3),
            "alert_cooldown_sec": int(getattr(config, "ALERT_COOLDOWN_SEC", 900) or 900),
        },
    }
    if persist_msg:
        data["persist_message"] = persist_msg
    msg = "性能/告警设置更新成功" if persisted else "性能/告警设置更新成功（仅当前进程生效）"
    return success(data, msg)


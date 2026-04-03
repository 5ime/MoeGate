"""性能监控模块"""
import logging
import threading
import time
from typing import Optional

import psutil

from config import config
from utils.alerts import send_webhook_alert

logger = logging.getLogger(__name__)

_monitor_thread: Optional[threading.Thread] = None
_monitor_running = False
_monitor_lock = threading.Lock()
_high_cpu_intervals = 0
_last_alert_ts: Optional[float] = None
_high_mem_intervals = 0
_wakeup_event = threading.Event()


def notify_performance_monitor_config_updated():
    """通知性能监控线程尽快读取新配置（如采样间隔/冷却时间）。"""
    try:
        _wakeup_event.set()
    except Exception:
        pass


def _format_bytes(bytes_value: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f}PB"


def _log_performance_metrics():
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        try:
            from utils.container_manager import get_container_manager
            container_count = len(get_container_manager().get_container_ids())
        except Exception:
            container_count = 0

        logger.info(
            "[性能监控] CPU: %.1f%% (%d核物理/%d核逻辑) | 内存: %.1f%% (%s/%s) | "
            "磁盘: %.1f%% (%s/%s) | 容器数: %d",
            cpu_percent, cpu_count, cpu_count_logical,
            mem.percent, _format_bytes(mem.used), _format_bytes(mem.total),
            disk.percent, _format_bytes(disk.used), _format_bytes(disk.total),
            container_count,
        )
        return {"cpu_percent": cpu_percent, "mem_percent": mem.percent}
    except Exception as e:
        logger.error("记录性能指标失败: %s", e)
        return None


def _monitor_loop():
    global _monitor_running, _high_cpu_intervals, _high_mem_intervals, _last_alert_ts
    while _monitor_running:
        try:
            metrics = _log_performance_metrics()
            if metrics is not None and config.ALERT_WEBHOOK_URL:
                cpu = float(metrics.get("cpu_percent") or 0.0)
                memp = float(metrics.get("mem_percent") or 0.0)
                threshold = float(config.ALERT_CPU_THRESHOLD)
                mem_threshold = float(config.ALERT_MEM_THRESHOLD)
                if cpu >= threshold:
                    _high_cpu_intervals += 1
                else:
                    _high_cpu_intervals = 0

                if memp >= mem_threshold:
                    _high_mem_intervals += 1
                else:
                    _high_mem_intervals = 0

                cpu_met = _high_cpu_intervals >= int(config.ALERT_CPU_SUSTAINED_INTERVALS)
                mem_met = _high_mem_intervals >= int(config.ALERT_MEM_SUSTAINED_INTERVALS)

                # 任一达标即告警（OR 条件）
                if cpu_met or mem_met:
                    now_ts = time.time()
                    cooldown = int(config.ALERT_COOLDOWN_SEC)
                    if (not _last_alert_ts) or (now_ts - _last_alert_ts >= cooldown):
                        parts = []
                        if cpu_met:
                            parts.append(f"CPU {cpu:.1f}% ≥ 阈值 {threshold}%")
                        if mem_met:
                            parts.append(f"内存 {memp:.1f}% ≥ 阈值 {mem_threshold}%")
                        message = " / ".join(parts) or "资源使用率高"
                        logger.warning("触发资源告警：%s（冷却 %ds）", message, cooldown)
                        sent = send_webhook_alert(
                            "resource_high_usage",
                            {
                                "message": f"资源持续高于阈值：{message}",
                            },
                        )
                        if sent:
                            _last_alert_ts = now_ts
                            # 重置已达标的计数，避免连续重复触发
                            if cpu_met:
                                _high_cpu_intervals = 0
                            if mem_met:
                                _high_mem_intervals = 0
            # 用 Event.wait 代替 sleep，便于配置更新后立刻生效
            timeout = int(getattr(config, "PERFORMANCE_LOG_INTERVAL", 300) or 300)
            if timeout < 1:
                timeout = 1
            _wakeup_event.wait(timeout=timeout)
            _wakeup_event.clear()
        except Exception as e:
            logger.error("性能监控循环错误: %s", e)
            timeout = int(getattr(config, "PERFORMANCE_LOG_INTERVAL", 300) or 300)
            if timeout < 1:
                timeout = 1
            _wakeup_event.wait(timeout=timeout)
            _wakeup_event.clear()


def start_performance_monitoring():
    global _monitor_thread, _monitor_running

    # 自动启用规则：设置了 Webhook 即默认启用；也兼容老的 ENABLE_PERFORMANCE_MONITORING 开关
    if not (bool(getattr(config, "ALERT_WEBHOOK_URL", None)) or bool(getattr(config, "ENABLE_PERFORMANCE_MONITORING", False))):
        return

    with _monitor_lock:
        if _monitor_running:
            logger.warning("性能监控已在运行")
            return
        _monitor_running = True
        _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True, name="PerformanceMonitor")
        _monitor_thread.start()
        logger.info("性能监控已启动，记录间隔: %d秒", config.PERFORMANCE_LOG_INTERVAL)


def stop_performance_monitoring():
    global _monitor_thread, _monitor_running

    with _monitor_lock:
        if not _monitor_running:
            return
        _monitor_running = False
        if _monitor_thread:
            _monitor_thread.join(timeout=5)
            _monitor_thread = None
        logger.info("性能监控已停止")

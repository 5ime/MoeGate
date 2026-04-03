"""告警发送工具"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any

import requests

from config import config
from infra.docker import ensure_client

logger = logging.getLogger(__name__)


_FEISHU_HOOK_RE = re.compile(r"/open-apis/bot/v2/hook/[^/]+", re.IGNORECASE)


def _is_feishu_bot_webhook(url: str) -> bool:
    return bool(url and _FEISHU_HOOK_RE.search(url))


def _format_feishu_text(event_type: str, payload: Dict[str, Any]) -> str:
    # 飞书机器人 text 消息（作为 interactive 卡片失败时的降级方案）
    now = datetime.now(timezone.utc).astimezone()
    parts = [
        "[MoeGate] 告警通知",
        "服务：moegate-api",
        f"时间：{now.strftime('%Y-%m-%d %H:%M:%S %z')}",
    ]
    try:
        snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        if isinstance(snapshot, dict):
            sys_s = snapshot.get("system") or {}
            if sys_s:
                parts.append(
                    "系统负载："
                    f"CPU {sys_s.get('cpu_usage', '-')}, "
                    f"内存 {sys_s.get('memory_usage', '-')}, "
                    f"核心 {sys_s.get('cpu_cores', '-')}, "
                    f"总内存 {sys_s.get('memory_total', '-')}"
                )

            docker_s = snapshot.get("docker") or {}
            if docker_s:
                parts.append(
                    "Docker："
                    f"版本 {docker_s.get('docker_version', '-')}, "
                    f"运行 {docker_s.get('containers_running', '-')}/{docker_s.get('containers_total', '-')}, "
                    f"受管 {docker_s.get('managed_total', '-')}, "
                    f"独立 {docker_s.get('standalone_managed', '-')}, "
                    f"Compose {docker_s.get('compose_managed', '-')}/{docker_s.get('compose_projects', '-')}"
                )

            frp_s = snapshot.get("frp") or {}
            if frp_s:
                enabled = frp_s.get("enabled")
                cnt = frp_s.get("proxies_count")
                parts.append(f"FRP：{'已启用' if enabled else '未启用'}，代理数 {cnt if cnt is not None else '-'}")

        container_id = payload.get("container_id")
        if container_id:
            parts.append(f"容器ID：{container_id}")
        container_name = payload.get("container_name")
        if container_name:
            parts.append(f"容器名：{container_name}")
        container_uuid = payload.get("container_uuid")
        if container_uuid:
            parts.append(f"容器UUID：{container_uuid}")
        source_ip = payload.get("source_ip")
        if source_ip:
            parts.append(f"来源IP：{source_ip}")
        request_id = payload.get("request_id")
        if request_id:
            parts.append(f"请求ID：{request_id}")
        created_by = payload.get("created_by")
        if created_by:
            parts.append(f"创建者：{created_by}")
        err = payload.get("error")
        if err:
            parts.append(f"错误：{err}")

        msg = payload.get("message")
        if msg:
            parts.append(f"说明：{msg}")
    except Exception:
        # payload 结构不稳定时，忽略格式化错误
        pass
    return "\n".join(parts)


def _build_feishu_card(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """构造飞书 interactive 卡片消息"""
    now = datetime.now(timezone.utc).astimezone()
    snapshot = (payload or {}).get("snapshot") if isinstance(payload, dict) else None
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    sys_s = snapshot.get("system") or {}
    docker_s = snapshot.get("docker") or {}
    frp_s = snapshot.get("frp") or {}

    def _val(v):
        return "-" if v is None or v == "" else str(v)

    frp_enabled = frp_s.get("enabled")
    frp_enabled_txt = "已启用" if frp_enabled else "未启用"

    fields = [
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**时间**\n{now.strftime('%Y-%m-%d %H:%M:%S %z')}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**CPU**\n{_val(sys_s.get('cpu_usage'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**内存**\n{_val(sys_s.get('memory_usage'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**核心/总内存**\n{_val(sys_s.get('cpu_cores'))} / {_val(sys_s.get('memory_total'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Docker 版本**\n{_val(docker_s.get('docker_version'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**总容器数/运行上限**\n{_val(docker_s.get('containers_total'))} / {_val(docker_s.get('max_containers'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**受管容器**\n{_val(docker_s.get('managed_total'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**独立容器数**\n{_val(docker_s.get('standalone_managed'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Compose/Project**\n{_val(docker_s.get('compose_managed'))} / {_val(docker_s.get('compose_projects'))}"}},
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**FRP**\n{frp_enabled_txt}，代理 {_val(frp_s.get('proxies_count'))}"}},
    ]

    detail_lines = []
    for k, label in [
        ("container_id", "容器ID"),
        ("container_name", "容器名"),
        ("source_ip", "来源IP"),
        ("request_id", "请求ID"),
        ("created_by", "创建者"),
    ]:
        v = (payload or {}).get(k)
        if v:
            detail_lines.append(f"**{label}**：{v}")
    err = (payload or {}).get("error")
    if err:
        detail_lines.append(f"**错误**：{err}")
    msg = (payload or {}).get("message")
    if msg:
        detail_lines.append(f"**说明**：{msg}")

    elements: list = [
        {"tag": "div", "fields": fields},
    ]
    if detail_lines:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(detail_lines)}})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red",
            "title": {"tag": "plain_text", "content": "MoeGate 告警"},
        },
        "elements": elements,
    }


def _collect_system_snapshot() -> Dict[str, Any]:
    """采集系统快照"""
    try:
        import psutil  # 本项目依赖中已包含

        mem_total_gb = psutil.virtual_memory().total / (1024**3)
        disk = psutil.disk_usage("/")
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)
        return {
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_usage": f"{psutil.cpu_percent(interval=0.1):.1f}%",
            "memory_total": f"{mem_total_gb:.2f}GB",
            "memory_usage": f"{psutil.virtual_memory().percent:.1f}%",
            # 磁盘：用于前端展示 (SystemTab) 与告警详情
            "disk_usage": f"{disk.percent:.1f}%",
            "disk_used": f"{disk_used_gb:.2f}GB",
            "disk_total": f"{disk_total_gb:.2f}GB",
        }
    except Exception:
        return {}


def _collect_docker_snapshot() -> Dict[str, Any]:
    """采集 Docker 快照"""
    try:
        client = ensure_client()
        if not client:
            return {"docker_version": "unavailable"}

        docker_ver = (client.version() or {}).get("Version")
        docker_info = client.info() or {}
        docker_running = int(docker_info.get("ContainersRunning", 0) or 0)
        docker_total = int(docker_info.get("Containers", 0) or 0)

        managed_containers = client.containers.list(all=True, filters={"label": "moegate.managed=true"})
        standalone_count = 0
        compose_count = 0
        compose_projects = set()
        for container in managed_containers:
            try:
                if not getattr(container, "attrs", None):
                    container.reload()
            except Exception:
                pass

            labels = ((container.attrs or {}).get("Config") or {}).get("Labels") or {}
            compose_project_id = str(labels.get("moegate.compose_project_id") or "").strip()
            if compose_project_id:
                compose_count += 1
                compose_projects.add(compose_project_id)
            else:
                standalone_count += 1

        return {
            "docker_version": docker_ver or "unknown",
            "containers_running": docker_running,
            "containers_total": docker_total,
            "max_containers": int(getattr(config, "MAX_CONTAINERS", 0) or 0) or None,
            "managed_total": len(managed_containers),
            "standalone_managed": standalone_count,
            "compose_managed": compose_count,
            "compose_projects": len(compose_projects),
        }
    except Exception:
        return {"docker_version": "unavailable"}


def _collect_frp_snapshot() -> Dict[str, Any]:
    """采集 FRP 快照"""
    try:
        if bool(getattr(config, "ENABLE_FRP", False)):
            from services.frp import list_proxies

            proxies = list_proxies()
            return {"enabled": True, "proxies_count": len(proxies)}
        return {"enabled": False}
    except Exception:
        return {"enabled": bool(getattr(config, "ENABLE_FRP", False)), "proxies_count": None}


def collect_runtime_snapshot() -> Dict[str, Any]:
    """采集运行时快照"""
    snapshot: Dict[str, Any] = {}

    # system
    snapshot["system"] = _collect_system_snapshot()

    # docker
    snapshot["docker"] = _collect_docker_snapshot()

    # frp
    snapshot["frp"] = _collect_frp_snapshot()

    return snapshot


def send_webhook_alert(event_type: str, payload: Dict[str, Any]) -> bool:
    """发送 webhook 告警"""
    if not config.ALERT_WEBHOOK_URL:
        return False

    url = str(config.ALERT_WEBHOOK_URL or "").strip()
    if not url:
        return False

    payload = dict(payload or {})
    # 自动附加运行时快照（若调用方已提供则不覆盖）
    if "snapshot" not in payload:
        payload["snapshot"] = collect_runtime_snapshot()

    # 飞书机器人 webhook 适配
    if _is_feishu_bot_webhook(url):
        body = {"msg_type": "interactive", "card": _build_feishu_card(event_type, payload)}
    else:
        body = {
            "event_type": event_type,
            "service": "moegate-api",
            "payload": payload,
        }

    try:
        resp = requests.post(
            url,
            json=body,
            timeout=config.ALERT_WEBHOOK_TIMEOUT,
        )
        if 200 <= resp.status_code < 300:
            return True

        # 飞书卡片不被支持时降级为 text
        if _is_feishu_bot_webhook(url):
            try:
                fallback = {
                    "msg_type": "text",
                    "content": {"text": _format_feishu_text(event_type, payload)},
                }
                resp2 = requests.post(url, json=fallback, timeout=config.ALERT_WEBHOOK_TIMEOUT)
                if 200 <= resp2.status_code < 300:
                    return True
            except Exception:
                pass
        logger.warning("告警发送失败，HTTP %s: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.warning("告警发送异常: %s", e)
        return False

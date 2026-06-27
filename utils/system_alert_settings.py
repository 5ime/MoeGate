"""系统告警相关设置辅助函数。"""

from typing import Dict, Optional, Tuple

from config import config
from services import runtime_store
from utils.url_validator import mask_webhook_url, validate_webhook_url


def build_alert_webhook_settings_data() -> Dict[str, object]:
    raw_url = (config.ALERT_WEBHOOK_URL or "")
    return {
        "webhook_url": mask_webhook_url(raw_url) if raw_url else "",
        "webhook_url_set": bool(str(raw_url).strip()),
        "webhook_timeout": int(getattr(config, "ALERT_WEBHOOK_TIMEOUT", 5) or 5),
    }


def apply_alert_webhook_update(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
    webhook_url = (config.ALERT_WEBHOOK_URL or "").strip()
    timeout_sec = None

    if "webhook_url" in body:
        webhook_url_raw = body.get("webhook_url")
        if not isinstance(webhook_url_raw, str):
            return "字段 webhook_url 必须为字符串", None

        webhook_url = webhook_url_raw.strip()
        if webhook_url:
            ok, reason = validate_webhook_url(webhook_url)
            if not ok:
                return reason, None

        runtime_store.set("ALERT_WEBHOOK_URL", webhook_url or None)

    webhook_timeout_raw = body.get("webhook_timeout", None)
    if webhook_timeout_raw is not None:
        try:
            timeout_sec = int(webhook_timeout_raw)
        except (TypeError, ValueError):
            return "字段 webhook_timeout 必须为正整数", None
        if timeout_sec <= 0:
            return "字段 webhook_timeout 必须为正整数", None
        runtime_store.set("ALERT_WEBHOOK_TIMEOUT", timeout_sec)

    return None, {
        "webhook_url": webhook_url,
        "webhook_url_masked": mask_webhook_url(webhook_url) if webhook_url else "",
        "webhook_timeout": int(getattr(config, "ALERT_WEBHOOK_TIMEOUT", 5) or 5),
        "timeout_sec": timeout_sec,
    }

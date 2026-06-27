"""运行态设置更新服务：解析、应用与响应组装。"""

from typing import Dict, Optional, Tuple

from services import runtime_store
from utils.system_alert_settings import (
    apply_alert_webhook_update,
    build_alert_webhook_settings_data,
)
from utils.frp_settings import (
    apply_frp_settings_update,
    build_frp_settings_data,
    parse_frp_settings_update,
)
from utils.system_settings import (
    apply_networking_settings_update,
    apply_webui_settings_update,
    build_container_defaults_data,
    build_image_source_setting_data,
    build_networking_settings_data,
    build_webui_settings_data,
    parse_image_source_update,
    parse_networking_settings_update,
    parse_webui_settings_update,
)

_PROCESS_ONLY_SUFFIX = "（仅当前进程生效）"


def _finalize_update(data: Dict[str, object], success_label: str) -> Tuple[str, Dict[str, object]]:
    return f"{success_label}{_PROCESS_ONLY_SUFFIX}", data


def update_image_source(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Tuple[str, Dict[str, object]]]]:
    validation_error, image_source = parse_image_source_update(body)
    if validation_error:
        return validation_error, None

    runtime_store.set("IMAGE_SOURCE", image_source or None)
    data = build_image_source_setting_data(image_source=image_source)
    return None, _finalize_update(data, "镜像源设置更新成功")


def update_webui_settings(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Tuple[str, Dict[str, object]]]]:
    validation_error, values = parse_webui_settings_update(body)
    if validation_error:
        return validation_error, None

    apply_webui_settings_update(values)
    data = build_webui_settings_data(
        api_base=values["api_base"],
        poll_interval_sec=values["poll_interval_sec"],
        max_containers=values.get("max_containers"),
        max_renew_times=values.get("max_renew_times"),
    )
    return None, _finalize_update(data, "WebUI 设置更新成功")


def update_networking_settings(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Tuple[str, Dict[str, object]]]]:
    validation_error, values = parse_networking_settings_update(body)
    if validation_error:
        return validation_error, None

    apply_networking_settings_update(values)
    data = build_networking_settings_data(
        compose_managed_subnet_pool=values["compose_managed_subnet_pool"],
        compose_managed_subnet_prefix=values["compose_managed_subnet_prefix"],
    )
    return None, _finalize_update(data, "网络设置更新成功")


def update_alert_webhook(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Tuple[str, Dict[str, object]]]]:
    validation_error, applied = apply_alert_webhook_update(body)
    if validation_error:
        return validation_error, None

    data = {
        "webhook_url": applied["webhook_url_masked"],
        "webhook_url_set": bool(applied["webhook_url"]),
        "webhook_timeout": applied["webhook_timeout"],
    }
    return None, _finalize_update(data, "告警 Webhook 设置更新成功")


def get_image_source_setting() -> Dict[str, object]:
    return build_image_source_setting_data()


def get_webui_settings() -> Dict[str, object]:
    return build_webui_settings_data()


def get_container_defaults() -> Dict[str, object]:
    return build_container_defaults_data()


def get_networking_settings() -> Dict[str, object]:
    return build_networking_settings_data()


def get_alert_webhook_settings() -> Dict[str, object]:
    return build_alert_webhook_settings_data()


def get_frp_settings() -> Dict[str, object]:
    return build_frp_settings_data()


def update_frp_settings(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Tuple[str, Dict[str, object]]]]:
    validation_error, updates = parse_frp_settings_update(body)
    if validation_error:
        return validation_error, None

    apply_frp_settings_update(updates)
    data = build_frp_settings_data()
    return None, _finalize_update(data, "FRP设置更新成功")

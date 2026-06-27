"""系统设置相关辅助函数。"""

from typing import Dict, Optional, Tuple

from config import config
from services import runtime_store
from utils.runtime_config import (
    validate_runtime_compose_subnet,
    validate_runtime_max_containers,
    validate_runtime_quota_ceiling,
)


def build_image_source_setting_data(*, image_source: Optional[str] = None) -> Dict[str, object]:
    return {
        "image_source": image_source if image_source is not None else (config.IMAGE_SOURCE or ""),
    }


def parse_image_source_update(body: Dict[str, object]) -> Tuple[Optional[str], Optional[str]]:
    image_source_raw = body.get("image_source")
    if not isinstance(image_source_raw, str):
        return "字段 image_source 必须为字符串", None
    return None, image_source_raw.strip()


def build_webui_settings_data(
    *,
    api_base: Optional[str] = None,
    poll_interval_sec: Optional[int] = None,
    max_containers: Optional[int] = None,
    max_renew_times: Optional[int] = None,
) -> Dict[str, object]:
    return {
        "api_base": (config.WEBUI_API_BASE or "").strip() if api_base is None else api_base,
        "poll_interval_sec": int(config.WEBUI_POLL_INTERVAL_SEC or 30) if poll_interval_sec is None else poll_interval_sec,
        "max_containers": int(config.MAX_CONTAINERS or 30) if max_containers is None else max_containers,
        "max_renew_times": int(config.MAX_RENEW_TIMES or 3) if max_renew_times is None else max_renew_times,
    }


def build_container_defaults_data() -> Dict[str, object]:
    return {
        "max_time": int(config.MAX_TIME or 3600),
        "min_port": int(config.MIN_PORT or 20000),
        "max_port": int(config.MAX_PORT or 30000),
        "memory_limit": str(config.CONTAINER_MEMORY_LIMIT or "512m"),
        "cpu_limit": None if config.CONTAINER_CPU_LIMIT is None else float(config.CONTAINER_CPU_LIMIT),
        "cpu_shares": int(config.CONTAINER_CPU_SHARES or 1024),
    }


def build_networking_settings_data(
    *,
    compose_managed_subnet_pool: Optional[str] = None,
    compose_managed_subnet_prefix: Optional[int] = None,
) -> Dict[str, object]:
    return {
        "compose_managed_subnet_pool": (
            str(getattr(config, "COMPOSE_MANAGED_SUBNET_POOL", "172.30.0.0/16") or "172.30.0.0/16")
            if compose_managed_subnet_pool is None
            else compose_managed_subnet_pool
        ),
        "compose_managed_subnet_prefix": (
            int(getattr(config, "COMPOSE_MANAGED_SUBNET_PREFIX", 24) or 24)
            if compose_managed_subnet_prefix is None
            else compose_managed_subnet_prefix
        ),
    }


def parse_webui_settings_update(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
    api_base_raw = body.get("api_base")
    poll_interval_sec_raw = body.get("poll_interval_sec")
    update_max_containers = "max_containers" in body
    update_max_renew_times = "max_renew_times" in body

    if not isinstance(api_base_raw, str):
        return "字段 api_base 必须为字符串", None

    try:
        poll_interval_sec = int(poll_interval_sec_raw)
    except (TypeError, ValueError):
        return "字段 poll_interval_sec 必须为正整数", None

    if poll_interval_sec <= 0:
        return "字段 poll_interval_sec 必须为正整数", None

    values: Dict[str, object] = {
        "api_base": api_base_raw.strip(),
        "poll_interval_sec": poll_interval_sec,
    }

    if update_max_containers:
        try:
            max_containers = int(body["max_containers"])
        except (TypeError, ValueError):
            return "字段 max_containers 必须为正整数", None
        if max_containers <= 0:
            return "字段 max_containers 必须为正整数", None

        max_containers_err = validate_runtime_max_containers(max_containers)
        if max_containers_err:
            return max_containers_err, None

        quota_err = validate_runtime_quota_ceiling("max_containers", max_containers, "MAX_CONTAINERS")
        if quota_err:
            return quota_err, None

        values["max_containers"] = max_containers

    if update_max_renew_times:
        try:
            max_renew_times = int(body["max_renew_times"])
        except (TypeError, ValueError):
            return "字段 max_renew_times 必须为非负整数", None
        if max_renew_times < 0:
            return "字段 max_renew_times 必须为非负整数", None

        renew_err = validate_runtime_quota_ceiling("max_renew_times", max_renew_times, "MAX_RENEW_TIMES")
        if renew_err:
            return renew_err, None

        values["max_renew_times"] = max_renew_times

    return None, values


def apply_webui_settings_update(values: Dict[str, object]) -> None:
    runtime_store.set("WEBUI_API_BASE", values["api_base"] or None)
    runtime_store.set("WEBUI_POLL_INTERVAL_SEC", int(values["poll_interval_sec"]))
    if "max_containers" in values:
        runtime_store.set("MAX_CONTAINERS", int(values["max_containers"]))
    if "max_renew_times" in values:
        runtime_store.set("MAX_RENEW_TIMES", int(values["max_renew_times"]))


def parse_networking_settings_update(body: Dict[str, object]) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
    subnet_pool_raw = body.get("compose_managed_subnet_pool")
    subnet_prefix_raw = body.get("compose_managed_subnet_prefix")

    if not isinstance(subnet_pool_raw, str):
        return "字段 compose_managed_subnet_pool 必须为字符串", None

    try:
        subnet_prefix = int(subnet_prefix_raw)
    except (TypeError, ValueError):
        return "字段 compose_managed_subnet_prefix 必须为整数", None

    normalized_pool, subnet_err = validate_runtime_compose_subnet(subnet_pool_raw, subnet_prefix)
    if subnet_err:
        return subnet_err, None

    return None, {
        "compose_managed_subnet_pool": normalized_pool,
        "compose_managed_subnet_prefix": subnet_prefix,
    }


def apply_networking_settings_update(values: Dict[str, object]) -> None:
    runtime_store.set("COMPOSE_MANAGED_SUBNET_POOL", str(values["compose_managed_subnet_pool"]))
    runtime_store.set("COMPOSE_MANAGED_SUBNET_PREFIX", int(values["compose_managed_subnet_prefix"]))

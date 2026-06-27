"""运行时设置 API 二次校验。"""
import ipaddress
from typing import Optional, Tuple

from config import config


def validate_runtime_quota_ceiling(field_name: str, value: int, boot_key: str) -> Optional[str]:
    """运行态配额不得高于进程启动时 .env 配置（可经 LOCK_RUNTIME_QUOTA_TO_BOOT 关闭）。"""
    if not getattr(config, "LOCK_RUNTIME_QUOTA_TO_BOOT", True):
        return None

    from services.runtime_store import get_boot_snapshot

    boot = get_boot_snapshot()
    if boot_key not in boot:
        return None
    try:
        ceiling = int(boot[boot_key])
        candidate = int(value)
    except (TypeError, ValueError):
        return f"字段 {field_name} 必须是整数"

    if candidate > ceiling:
        return f"字段 {field_name} 不能超过启动配置上限 ({ceiling})"
    return None


def validate_runtime_max_containers(
    max_containers: int,
    min_port: Optional[int] = None,
    max_port: Optional[int] = None,
) -> Optional[str]:
    """校验 MAX_CONTAINERS 是否与端口池等业务约束一致。"""
    min_port = int(min_port if min_port is not None else getattr(config, "MIN_PORT", 20000))
    max_port = int(max_port if max_port is not None else getattr(config, "MAX_PORT", 30000))

    if max_containers <= 0:
        return "字段 max_containers 必须为正整数"
    if max_containers > 1000:
        return "字段 max_containers 不应超过 1000"
    port_range = max_port - min_port
    if port_range < max_containers:
        return (
            f"端口范围 ({port_range}) 小于最大容器数 ({max_containers})，可能导致端口不足"
        )
    return None


def validate_runtime_compose_subnet(
    subnet_pool_text: str,
    subnet_prefix: int,
) -> Tuple[Optional[str], Optional[str]]:
    """校验 Compose 受管网段设置，返回 (normalized_pool, error_message)。"""
    text = str(subnet_pool_text or "").strip()
    if not text:
        return None, "字段 compose_managed_subnet_pool 不能为空"

    try:
        subnet_pool = ipaddress.ip_network(text, strict=False)
    except ValueError:
        return None, "字段 compose_managed_subnet_pool 必须是合法的 IPv4 CIDR 网段"

    if subnet_pool.version != 4:
        return None, "字段 compose_managed_subnet_pool 目前仅支持 IPv4 网段"

    try:
        prefix = int(subnet_prefix)
    except (TypeError, ValueError):
        return None, "字段 compose_managed_subnet_prefix 必须为整数"

    if prefix < subnet_pool.prefixlen:
        return None, "字段 compose_managed_subnet_prefix 不能小于地址池前缀长度"
    if prefix > 30:
        return None, "字段 compose_managed_subnet_prefix 不能大于 30"

    return str(subnet_pool), None

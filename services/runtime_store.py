"""运行态设置存储：API 可变字段的统一写入入口。

启动时 ``config`` 从环境变量加载；运行期修改经此模块写入同一 ``config`` 对象。
读侧仍可直接 ``from config import config``，无需全量迁移读路径。

多 worker 场景可设置 ``RUNTIME_STORE_PERSIST=true``，运行态字段写入
``ALLOWED_BASE_DIR/.moegate/runtime_settings.json`` 供进程间共享；进程重启仍恢复
环境变量启动值（与 lifecycle.json 类似，仅服务运行期有效）。
"""

from typing import Any, Dict, FrozenSet, Optional

from config import config
from services.runtime_store_backend import create_runtime_backend

RUNTIME_FIELDS: FrozenSet[str] = frozenset({
    "IMAGE_SOURCE",
    "WEBUI_API_BASE",
    "WEBUI_POLL_INTERVAL_SEC",
    "MAX_CONTAINERS",
    "MAX_RENEW_TIMES",
    "COMPOSE_MANAGED_SUBNET_POOL",
    "COMPOSE_MANAGED_SUBNET_PREFIX",
    "ALERT_WEBHOOK_URL",
    "ALERT_WEBHOOK_TIMEOUT",
    "ENABLE_FRP",
    "FRP_SERVER_ADDR",
    "FRP_SERVER_PORT",
    "FRP_VHOST_HTTP_PORT",
    "FRP_ADMIN_IP",
    "FRP_ADMIN_PORT",
    "FRP_ADMIN_USER",
    "FRP_ADMIN_PASSWORD",
    "FRP_USE_DOMAIN",
    "FRP_DOMAIN_SUFFIX",
    "FRP_ADMIN_ADDR",
})

_boot_snapshot: Optional[Dict[str, Any]] = None
_backend = None


def _get_backend():
    global _backend
    if _backend is None:
        _backend = create_runtime_backend(
            persist=bool(config.RUNTIME_STORE_PERSIST),
            allowed_fields=RUNTIME_FIELDS,
            base_dir=getattr(config, "ALLOWED_BASE_DIR", None),
        )
    return _backend


def _capture_current_values() -> Dict[str, Any]:
    return {name: getattr(config, name) for name in RUNTIME_FIELDS}


def _apply_values(values: Dict[str, Any]) -> None:
    for name, value in values.items():
        if name in RUNTIME_FIELDS:
            setattr(config, name, value)


def capture_boot_snapshot() -> Dict[str, Any]:
    """记录启动时运行态字段快照，供对比或调试。"""
    global _boot_snapshot
    _boot_snapshot = _capture_current_values()
    return dict(_boot_snapshot)


def get_boot_snapshot() -> Dict[str, Any]:
    if _boot_snapshot is None:
        return capture_boot_snapshot()
    return dict(_boot_snapshot)


def reload_from_backend() -> None:
    """从后端重载运行态字段到 config（文件后端在 mtime 变化时生效）。"""
    updates = _get_backend().reload_if_changed()
    if updates:
        _apply_values(updates)


def get(name: str) -> Any:
    if name not in RUNTIME_FIELDS:
        raise KeyError(f"{name} 不是运行态可变字段")
    reload_from_backend()
    return getattr(config, name)


def get_all() -> Dict[str, Any]:
    reload_from_backend()
    return _capture_current_values()


def set(name: str, value: Any) -> None:
    if name not in RUNTIME_FIELDS:
        raise KeyError(f"{name} 不是运行态可变字段")
    setattr(config, name, value)
    _get_backend().save(_capture_current_values())


def reset_session() -> None:
    """将共享后端对齐到启动快照（进程组启动时调用，保证重启后恢复环境变量）。"""
    values = get_boot_snapshot()
    _apply_values(values)
    _get_backend().save(values)


capture_boot_snapshot()

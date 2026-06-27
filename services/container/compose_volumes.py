"""Compose bind mount 解析与路径校验。"""
import os
from typing import Any, Dict, List, Optional, Tuple

from core.exceptions import InvalidPathError, ValidationError
from services.container.compose_policy import blocked_volume_reason
from utils.path_validator import validate_path


def _is_bind_source(source: str) -> bool:
    text = str(source or "").strip()
    if not text:
        return False
    if text.startswith((".", "/", "~")):
        return True
    if len(text) > 1 and text[1] == ":":
        return True
    return False


def _parse_volume_entry(item: Any) -> Tuple[str, str, str]:
    """解析 volume 条目，返回 (source, target, mode)。"""
    if isinstance(item, dict):
        vol_type = str(item.get("type") or "volume").strip().lower()
        if vol_type and vol_type != "bind":
            raise ValidationError(f"不支持的 volume 类型: {vol_type}，MoeGate 仅支持 bind mount")
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if not source or not target:
            raise ValidationError("bind volume 必须同时指定 source 与 target")
        mode = "ro" if item.get("read_only") else str(item.get("mode") or "rw").strip() or "rw"
        return source, target, mode

    if isinstance(item, str):
        text = item.strip()
        if not text:
            raise ValidationError("volume 条目不能为空")
        parts = text.split(":")
        if len(parts) < 2:
            raise ValidationError(f"volume 格式无效: {item}")
        source = parts[0].strip()
        target = parts[1].strip()
        mode = parts[2].strip() if len(parts) > 2 else "rw"
        if not source or not target:
            raise ValidationError(f"volume 格式无效: {item}")
        return source, target, mode

    raise ValidationError(f"volume 配置格式无效: {item!r}")


def _resolve_bind_source(source: str, compose_dir: str) -> str:
    text = str(source or "").strip()
    if os.path.isabs(text):
        candidate = os.path.normpath(text)
    else:
        candidate = os.path.normpath(os.path.join(compose_dir, text))
    try:
        return validate_path(candidate)
    except InvalidPathError as exc:
        raise ValidationError(str(exc)) from exc


def resolve_compose_service_volumes(
    compose_path: str,
    service_name: str,
    service: Dict[str, Any],
) -> Dict[str, Dict[str, str]]:
    """将 compose service.volumes 解析为 Docker SDK volumes 字典。"""
    raw_volumes = service.get("volumes") or []
    if not raw_volumes:
        return {}

    compose_dir = os.path.dirname(os.path.abspath(compose_path))
    resolved: Dict[str, Dict[str, str]] = {}

    for item in raw_volumes:
        source, target, mode = _parse_volume_entry(item)
        if not _is_bind_source(source):
            raise ValidationError(
                f"Compose 服务 {service_name}: named volume 不受支持（{source}），请使用 bind mount"
            )

        blocked = blocked_volume_reason(f"{source}:{target}")
        if blocked:
            raise ValidationError(f"Compose 服务 {service_name}: {blocked}")

        host_path = _resolve_bind_source(source, compose_dir)
        if host_path in resolved:
            raise ValidationError(f"Compose 服务 {service_name}: 重复挂载宿主机路径 {host_path}")

        bind_mode = "ro" if str(mode).lower() in ("ro", "readonly") else "rw"
        resolved[host_path] = {"bind": target, "mode": bind_mode}

    return resolved

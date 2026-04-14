"""受管镜像注册表。"""
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_registry_lock = threading.Lock()
_registry_cache: Optional[Dict[str, Dict[str, Any]]] = None


def _registry_file_path() -> str:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    runtime_dir = os.path.join(project_root, "runtime")
    return os.path.join(runtime_dir, "managed-images.json")


def _ensure_runtime_dir() -> None:
    os.makedirs(os.path.dirname(_registry_file_path()), exist_ok=True)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _load_registry() -> Dict[str, Dict[str, Any]]:
    global _registry_cache
    with _registry_lock:
        if _registry_cache is not None:
            return dict(_registry_cache)

        path = _registry_file_path()
        if not os.path.exists(path):
            _registry_cache = {}
            return {}

        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle) or {}
            if not isinstance(data, dict):
                data = {}
        except Exception as exc:
            logger.warning("读取受管镜像注册表失败，将回退为空表: %s", exc)
            data = {}

        normalized = {str(key): value for key, value in data.items() if isinstance(value, dict)}
        _registry_cache = normalized
        return dict(normalized)


def _save_registry(records: Dict[str, Dict[str, Any]]) -> None:
    global _registry_cache
    with _registry_lock:
        _ensure_runtime_dir()
        path = _registry_file_path()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2, sort_keys=True)
        _registry_cache = dict(records)


def list_managed_image_records() -> Dict[str, Dict[str, Any]]:
    return _load_registry()


def register_managed_image(
    image_id: str,
    *,
    source: str,
    requested_image: Optional[str] = None,
    resolved_image: Optional[str] = None,
    tags: Optional[list] = None,
) -> Dict[str, Any]:
    normalized_id = str(image_id or "").strip()
    if not normalized_id:
        raise ValueError("image_id 不能为空")

    records = _load_registry()
    current = dict(records.get(normalized_id) or {})
    created_at = current.get("created_at") or _now_iso()
    merged_tags = list(dict.fromkeys([str(item).strip() for item in (current.get("tags") or []) + (tags or []) if str(item).strip()]))

    record = {
        "image_id": normalized_id,
        "source": str(source or current.get("source") or "managed").strip() or "managed",
        "requested_image": str(requested_image or current.get("requested_image") or "").strip(),
        "resolved_image": str(resolved_image or current.get("resolved_image") or "").strip(),
        "tags": merged_tags,
        "created_at": created_at,
        "updated_at": _now_iso(),
    }
    records[normalized_id] = record
    _save_registry(records)
    return record


def unregister_managed_image(image_id: str) -> None:
    normalized_id = str(image_id or "").strip()
    if not normalized_id:
        return
    records = _load_registry()
    if normalized_id not in records:
        return
    records.pop(normalized_id, None)
    _save_registry(records)


def upsert_managed_image_tags(image_id: str, tags: Optional[list]) -> None:
    normalized_id = str(image_id or "").strip()
    if not normalized_id:
        return
    records = _load_registry()
    if normalized_id not in records:
        return
    record = dict(records[normalized_id])
    current_tags = list(record.get("tags") or [])
    merged_tags = list(dict.fromkeys([str(item).strip() for item in current_tags + (tags or []) if str(item).strip()]))
    record["tags"] = merged_tags
    record["updated_at"] = _now_iso()
    records[normalized_id] = record
    _save_registry(records)


def resolve_registered_image_ref(image_ref: str) -> Optional[str]:
    target = str(image_ref or "").strip()
    if not target:
        return None
    records = _load_registry()
    if target in records:
        return target
    for image_id, record in records.items():
        if target == str(record.get("resolved_image") or "").strip():
            return image_id
        if target == str(record.get("requested_image") or "").strip():
            return image_id
        if target in [str(item).strip() for item in (record.get("tags") or []) if str(item).strip()]:
            return image_id
    return None
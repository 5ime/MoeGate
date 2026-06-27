"""容器生命周期持久化。

Docker 容器 labels 在创建后不可变，续期与到期时间变更写入本地 JSON。
"""

import json
import logging
import os
import threading
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class LifecycleStore:
    def __init__(self, base_dir: str):
        self._path = os.path.join(base_dir, ".moegate", "lifecycle.json")
        self._lock = threading.Lock()
        self._data: Optional[Dict[str, Dict[str, int]]] = None

    def _ensure_loaded(self) -> None:
        if self._data is not None:
            return
        self._data = {}
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                self._data = raw
        except Exception as exc:
            logger.warning("加载 lifecycle.json 失败: %s", exc)
            self._data = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp_path = f"{self._path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_path, self._path)

    def get(self, container_id: str) -> Optional[Dict[str, int]]:
        with self._lock:
            self._ensure_loaded()
            entry = self._data.get(container_id)
            if not isinstance(entry, dict):
                return None
            result: Dict[str, int] = {}
            if "expires_at" in entry:
                result["expires_at"] = int(entry["expires_at"])
            if "renew_count" in entry:
                result["renew_count"] = max(0, int(entry["renew_count"]))
            return result or None

    def upsert(
        self,
        container_id: str,
        *,
        expires_at: Optional[int] = None,
        renew_count: Optional[int] = None,
    ) -> None:
        with self._lock:
            self._ensure_loaded()
            entry = dict(self._data.get(container_id) or {})
            if expires_at is not None:
                entry["expires_at"] = int(expires_at)
            if renew_count is not None:
                entry["renew_count"] = max(0, int(renew_count))
            self._data[container_id] = entry
            self._save()

    def remove(self, container_id: str) -> None:
        with self._lock:
            self._ensure_loaded()
            if container_id not in self._data:
                return
            del self._data[container_id]
            self._save()

    def prune(self, active_ids: Set[str]) -> None:
        with self._lock:
            self._ensure_loaded()
            stale_ids = [container_id for container_id in self._data if container_id not in active_ids]
            if not stale_ids:
                return
            for container_id in stale_ids:
                del self._data[container_id]
            self._save()

"""跨进程共享容器配额预留（基于 ALLOWED_BASE_DIR 下文件锁）。"""
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_RESERVATION_TTL_SECONDS = 600


class SharedQuotaStore:
    """在共享 ALLOWED_BASE_DIR 上协调多实例容器名额预留。"""

    def __init__(self, base_dir: str):
        self._dir = os.path.join(os.path.abspath(base_dir), ".moegate")
        self._path = os.path.join(self._dir, "quota_reservations.json")
        self._lock_path = os.path.join(self._dir, "quota.lock")

    @contextmanager
    def _file_lock(self):
        os.makedirs(self._dir, exist_ok=True)
        lock_fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(lock_fd)

    def _load(self) -> Dict[str, Dict[str, int]]:
        if not os.path.isfile(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                reservations = raw.get("reservations")
                if isinstance(reservations, dict):
                    return {
                        str(key): value
                        for key, value in reservations.items()
                        if isinstance(value, dict)
                    }
        except Exception as exc:
            logger.warning("加载 quota_reservations.json 失败: %s", exc)
        return {}

    def _save(self, reservations: Dict[str, Dict[str, int]]) -> None:
        os.makedirs(self._dir, exist_ok=True)
        tmp_path = f"{self._path}.tmp"
        payload = {"reservations": reservations}
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_path, self._path)

    def _prune_stale(self, reservations: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        now = int(time.time())
        cutoff = now - _RESERVATION_TTL_SECONDS
        kept: Dict[str, Dict[str, int]] = {}
        for reservation_id, entry in reservations.items():
            created_at = int(entry.get("created_at") or 0)
            slots = int(entry.get("slots") or 0)
            if slots <= 0 or created_at < cutoff:
                continue
            kept[reservation_id] = {"slots": slots, "created_at": created_at}
        return kept

    def _pending_slots(self, reservations: Dict[str, Dict[str, int]]) -> int:
        return sum(int(entry.get("slots") or 0) for entry in reservations.values())

    def try_reserve(
        self,
        slots: int,
        max_containers: int,
        managed_count: int,
    ) -> Optional[str]:
        slots = max(1, int(slots))
        with self._file_lock():
            reservations = self._prune_stale(self._load())
            pending = self._pending_slots(reservations)
            if int(managed_count) + pending + slots > int(max_containers):
                return None
            reservation_id = str(uuid.uuid4())
            reservations[reservation_id] = {
                "slots": slots,
                "created_at": int(time.time()),
            }
            self._save(reservations)
            return reservation_id

    def release(self, reservation_id: str) -> None:
        reservation_id = str(reservation_id or "").strip()
        if not reservation_id:
            return
        with self._file_lock():
            reservations = self._prune_stale(self._load())
            if reservation_id in reservations:
                del reservations[reservation_id]
                self._save(reservations)


_store: Optional[SharedQuotaStore] = None
_store_base_dir: Optional[str] = None


def get_shared_quota_store(base_dir: Optional[str] = None) -> SharedQuotaStore:
    global _store, _store_base_dir
    resolved_base = os.path.abspath(base_dir or "")
    if not resolved_base:
        from config import config

        resolved_base = os.path.abspath(config.ALLOWED_BASE_DIR)
    if _store is None or _store_base_dir != resolved_base:
        _store = SharedQuotaStore(resolved_base)
        _store_base_dir = resolved_base
    return _store

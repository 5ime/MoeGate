"""取证元数据持久化。

Docker 标签不可变、容器销毁后对象消失，而 pcap 需要长期保留并可在容器不存在时
继续下载/生成摘要。这里把「靶机 -> 取证目录」的映射与「管理员已停止抓包」的覆盖
状态写入 ``<ALLOWED_BASE_DIR>/.moegate/captures.json``：

- 靶机销毁后仍可按容器 UUID / Docker ID / 名称解析到 capture_key；
- ``POST /traffic/stop`` 的停止状态在 reconcile 重建 sidecar 时依然生效；
- 新容器复用同一 ``uid``（同目录）时，新的 Docker ID 不会继承旧的停止状态。

写入使用临时文件 + ``os.replace``，与 lifecycle_store 保持一致。
"""

import json
import logging
import os
import threading
import time
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

_STORE_LOCK = threading.Lock()
_STORES: Dict[str, "CaptureStore"] = {}


class CaptureStore:
    """capture_key 与靶机身份、停止状态的持久化索引。"""

    def __init__(self, base_dir: str):
        self._path = os.path.join(str(base_dir or "."), ".moegate", "captures.json")
        self._lock = threading.Lock()
        self._data: Optional[Dict[str, Dict[str, Dict[str, Dict[str, float]]]]] = None

    # ---- 内部读写 ----

    def _ensure_loaded(self) -> None:
        if self._data is not None:
            return
        self._data = {"captures": {}}
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict) and isinstance(raw.get("captures"), dict):
                self._data = {"captures": raw["captures"]}
        except Exception as exc:
            logger.warning("加载 captures.json 失败: %s", exc)
            self._data = {"captures": {}}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp_path = f"{self._path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(self._data or {"captures": {}}, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(tmp_path, self._path)
        except Exception as exc:
            # 元数据是旁路能力：写不进去也不能影响取证主流程，但要留痕
            logger.warning("保存 captures.json 失败: %s", exc)

    def _entry(self, capture_key: str, create: bool = False) -> Optional[Dict]:
        captures = (self._data or {}).get("captures") or {}
        entry = captures.get(capture_key)
        if not isinstance(entry, dict) and create:
            entry = {"targets": {}, "stopped": {}}
            captures[capture_key] = entry
            self._data["captures"] = captures
        return entry if isinstance(entry, dict) else None

    # ---- 对外接口 ----

    def record(self, target_id: str, target_name: str, capture_key: str) -> None:
        """登记靶机与取证目录的映射（幂等）。"""
        target_id = str(target_id or "").strip()
        capture_key = str(capture_key or "").strip()
        if not target_id or not capture_key:
            return
        with self._lock:
            self._ensure_loaded()
            entry = self._entry(capture_key, create=True)
            targets = entry.setdefault("targets", {})
            current = targets.get(target_id) if isinstance(targets.get(target_id), dict) else {}
            current.update({
                "name": str(target_name or current.get("name") or ""),
                "recorded_at": float(current.get("recorded_at") or time.time()),
            })
            targets[target_id] = current
            self._save()

    def lookup(self, identifier: str) -> Optional[str]:
        """按 Docker ID / 容器名 / capture_key 解析 capture_key。"""
        value = str(identifier or "").strip()
        if not value:
            return None
        with self._lock:
            self._ensure_loaded()
            captures = (self._data or {}).get("captures") or {}
            if value in captures:
                return value
            for key, entry in captures.items():
                targets = entry.get("targets") if isinstance(entry, dict) else None
                if not isinstance(targets, dict):
                    continue
                for target_id, meta in targets.items():
                    if value == target_id or (isinstance(meta, dict) and value == str(meta.get("name") or "")):
                        return key
        return None

    def mark_stopped(self, capture_key: str, target_id: str) -> None:
        target_id = str(target_id or "").strip()
        if not capture_key or not target_id:
            return
        with self._lock:
            self._ensure_loaded()
            entry = self._entry(str(capture_key), create=True)
            stopped = entry.setdefault("stopped", {})
            stopped[target_id] = time.time()
            self._save()

    def is_stopped(self, capture_key: str, target_id: str) -> bool:
        with self._lock:
            self._ensure_loaded()
            entry = self._entry(str(capture_key))
            if not entry:
                return False
            stopped = entry.get("stopped")
            return isinstance(stopped, dict) and str(target_id or "") in stopped

    def clear_stopped(self, capture_key: str, target_id: str) -> None:
        with self._lock:
            self._ensure_loaded()
            entry = self._entry(str(capture_key))
            if not entry:
                return
            stopped = entry.get("stopped")
            if isinstance(stopped, dict) and stopped.pop(str(target_id or ""), None) is not None:
                self._save()

    def prune(self, existing_keys: Set[str]) -> None:
        """清掉取证目录已不存在的索引条目。"""
        with self._lock:
            self._ensure_loaded()
            captures = (self._data or {}).get("captures") or {}
            stale = [key for key in captures if key not in existing_keys]
            if not stale:
                return
            for key in stale:
                captures.pop(key, None)
            self._data["captures"] = captures
            self._save()


def get_capture_store() -> CaptureStore:
    """按 ALLOWED_BASE_DIR 缓存实例（测试用不同 tmp 目录时互不干扰）。"""
    from config import config

    base_dir = str(getattr(config, "ALLOWED_BASE_DIR", ".") or ".")
    with _STORE_LOCK:
        store = _STORES.get(base_dir)
        if store is None:
            store = CaptureStore(base_dir)
            _STORES[base_dir] = store
        return store


def reset_capture_stores() -> None:
    """测试辅助：清空按目录缓存的实例。"""
    with _STORE_LOCK:
        _STORES.clear()

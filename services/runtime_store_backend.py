"""运行态设置存储后端：默认进程内；可选文件持久化供多 worker 共享。"""

from __future__ import annotations

import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, FrozenSet, Optional

logger = logging.getLogger(__name__)


class RuntimeStoreBackend(ABC):
    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """读取后端存储的运行态字段。"""

    @abstractmethod
    def save(self, values: Dict[str, Any]) -> None:
        """持久化全部运行态字段。"""

    def reload_if_changed(self) -> Dict[str, Any]:
        """多 worker 场景下按需重载；默认实现等同 load。"""
        return self.load()


class MemoryRuntimeBackend(RuntimeStoreBackend):
    """默认后端：仅依赖进程内 config，不做跨进程同步。"""

    def load(self) -> Dict[str, Any]:
        return {}

    def save(self, values: Dict[str, Any]) -> None:
        return None

    def reload_if_changed(self) -> Dict[str, Any]:
        return {}


class FileRuntimeBackend(RuntimeStoreBackend):
    """文件后端：写入 ALLOWED_BASE_DIR/.moegate/runtime_settings.json。"""

    def __init__(self, path: str, allowed_fields: FrozenSet[str]):
        self._path = path
        self._allowed_fields = allowed_fields
        self._lock = threading.Lock()
        self._last_mtime: Optional[float] = None

    def load(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.isfile(self._path):
                self._last_mtime = None
                return {}
            try:
                mtime = os.path.getmtime(self._path)
                with open(self._path, "r", encoding="utf-8") as handle:
                    raw = json.load(handle)
                self._last_mtime = mtime
            except Exception as exc:
                logger.warning("加载 runtime_settings.json 失败: %s", exc)
                self._last_mtime = None
                return {}

            if not isinstance(raw, dict):
                return {}

            values: Dict[str, Any] = {}
            for name in self._allowed_fields:
                if name in raw:
                    values[name] = raw[name]
            return values

    def reload_if_changed(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.isfile(self._path):
                self._last_mtime = None
                return {}
            try:
                mtime = os.path.getmtime(self._path)
            except OSError:
                return {}
            if self._last_mtime is not None and mtime <= self._last_mtime:
                return {}
        return self.load()

    def save(self, values: Dict[str, Any]) -> None:
        payload = {name: values[name] for name in self._allowed_fields if name in values}
        with self._lock:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp_path = f"{self._path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(tmp_path, self._path)
            try:
                self._last_mtime = os.path.getmtime(self._path)
            except OSError:
                self._last_mtime = None


def create_runtime_backend(
    *,
    persist: bool,
    allowed_fields: FrozenSet[str],
    base_dir: Optional[str] = None,
) -> RuntimeStoreBackend:
    if not persist:
        return MemoryRuntimeBackend()
    if not base_dir:
        logger.warning("RUNTIME_STORE_PERSIST 已启用但未配置 ALLOWED_BASE_DIR，回退至内存后端")
        return MemoryRuntimeBackend()
    path = os.path.join(base_dir, ".moegate", "runtime_settings.json")
    return FileRuntimeBackend(path, allowed_fields)

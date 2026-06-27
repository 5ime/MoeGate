"""WebUI 静态资源构建信息校验。"""
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

BUILD_INFO_FILENAME = ".moegate-build.json"


def load_static_build_info(static_dir: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(static_dir, BUILD_INFO_FILENAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取 WebUI 构建信息失败 (%s): %s", path, exc)
        return None


def verify_static_build_info(static_dir: str) -> None:
    """启动时检查 static 是否经 frontend 构建；缺失时写 warning 日志。"""
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.isfile(index_path):
        logger.warning("WebUI 静态目录缺少 index.html: %s", static_dir)
        return

    info = load_static_build_info(static_dir)
    if info is None:
        logger.warning(
            "WebUI 缺少 %s，可能未执行 frontend 构建；"
            "请运行: cd frontend && npm ci && npm run build",
            BUILD_INFO_FILENAME,
        )
        return

    version = str(info.get("version") or "").strip() or "unknown"
    built_at = str(info.get("built_at") or "").strip() or "unknown"
    logger.info("WebUI 静态资源已加载 (version=%s, built_at=%s)", version, built_at)

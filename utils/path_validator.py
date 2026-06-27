"""路径验证工具"""
import os
import re
import platform
import logging
from pathlib import Path

from config import config
from core.exceptions import InvalidPathError

logger = logging.getLogger(__name__)

_UNIX_SENSITIVE_DIRS = (
    "/etc",
    "/bin",
    "/sbin",
    "/sys",
    "/proc",
    "/boot",
    "/root",
    "/dev",
    "/usr/bin",
    "/usr/sbin",
    "/usr/lib",
    "/usr/libexec",
)


def _get_allowed_base_dir() -> str:
    return os.path.realpath(config.ALLOWED_BASE_DIR)


def _path_client_error(detail: str) -> InvalidPathError:
    """生产模式不向客户端返回绝对路径等内部细节。"""
    logger.debug("路径验证失败: %s", detail)
    if getattr(config, "DEBUG", False):
        return InvalidPathError(detail)
    return InvalidPathError("路径不在允许目录内或不可访问")


def _reject_sensitive_path(abs_path: str) -> None:
    system = platform.system()
    if system == "Windows":
        sensitive_dirs = [
            "C:\\Windows",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
            "C:\\System32",
            "C:\\SysWOW64",
            "C:\\ProgramData",
        ]
        abs_path_lower = abs_path.lower()
        for sensitive_dir in sensitive_dirs:
            prefix = sensitive_dir.lower()
            if abs_path_lower == prefix or abs_path_lower.startswith(prefix + "\\"):
                raise _path_client_error(f"禁止访问系统敏感目录: {sensitive_dir}")
        return

    normalized = abs_path.replace("\\", "/")
    for sensitive_dir in _UNIX_SENSITIVE_DIRS:
        if normalized == sensitive_dir or normalized.startswith(sensitive_dir + "/"):
            raise _path_client_error(f"禁止访问系统敏感目录: {sensitive_dir}")


def _path_under_base(resolved: Path, base: Path) -> bool:
    try:
        resolved.relative_to(base)
        return True
    except ValueError:
        return False


def validate_path(path: str) -> str:
    """验证路径安全性，返回标准化的绝对路径。"""
    if not path or not isinstance(path, str):
        raise _path_client_error("路径不能为空")

    if re.search(r'[<>"|?*\x00-\x1f]', path):
        raise _path_client_error("路径包含非法字符")

    allowed_base_dir = _get_allowed_base_dir()
    allowed_base_path = Path(allowed_base_dir)

    normalized_path = os.path.normpath(path.strip())
    if os.path.isabs(normalized_path):
        candidate = Path(normalized_path)
    else:
        candidate = allowed_base_path / normalized_path

    _reject_sensitive_path(str(candidate))

    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise _path_client_error("路径不存在")
    except OSError as exc:
        raise _path_client_error("路径不可访问") from exc

    abs_real_path = str(resolved)
    _reject_sensitive_path(abs_real_path)

    if not _path_under_base(resolved, allowed_base_path):
        detail = (
            f"路径必须在允许的目录下: {allowed_base_dir}。当前路径: {abs_real_path}"
        )
        raise _path_client_error(detail)

    logger.debug("路径验证通过: %s", abs_real_path)
    return abs_real_path

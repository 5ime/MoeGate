"""路径验证工具"""
import os
import re
import platform
import logging
from config import config
from core.exceptions import InvalidPathError

logger = logging.getLogger(__name__)


def _get_allowed_base_dir() -> str:
    return os.path.realpath(config.ALLOWED_BASE_DIR)


def validate_path(path: str) -> str:
    """验证路径安全性，返回标准化的绝对路径。"""
    if not path or not isinstance(path, str):
        raise InvalidPathError("路径不能为空")

    if '..' in path:
        raise InvalidPathError("路径不能包含上级目录引用")

    if re.search(r'[<>"|?*\x00-\x1f]', path):
        raise InvalidPathError("路径包含非法字符")

    normalized_path = os.path.normpath(path)
    if not os.path.exists(normalized_path):
        raise InvalidPathError("路径不存在")

    abs_path = os.path.abspath(normalized_path)

    system = platform.system()
    if system == 'Windows':
        sensitive_dirs = [
            'C:\\Windows', 'C:\\Program Files', 'C:\\Program Files (x86)',
            'C:\\System32', 'C:\\SysWOW64', 'C:\\ProgramData',
        ]
        abs_path_lower = abs_path.lower()
        for sensitive_dir in sensitive_dirs:
            if abs_path_lower.startswith(sensitive_dir.lower()):
                raise InvalidPathError(f"禁止访问系统敏感目录: {sensitive_dir}")
    else:
        sensitive_dirs = ['/etc', '/usr', '/bin', '/sbin', '/sys', '/proc', '/boot', '/root', '/dev']
        for sensitive_dir in sensitive_dirs:
            if abs_path.startswith(sensitive_dir):
                raise InvalidPathError(f"禁止访问系统敏感目录: {sensitive_dir}")

    allowed_base_dir = _get_allowed_base_dir()
    abs_real_path = os.path.realpath(abs_path)
    try:
        common_path = os.path.commonpath([abs_real_path, allowed_base_dir])
    except ValueError as e:
        raise InvalidPathError(
            f"路径必须在允许的目录下: {allowed_base_dir}。当前路径: {abs_real_path}"
        ) from e

    if os.path.normcase(common_path) != os.path.normcase(allowed_base_dir):
        raise InvalidPathError(
            f"路径必须在允许的目录下: {allowed_base_dir}。当前路径: {abs_real_path}"
        )

    logger.debug("路径验证通过: %s", abs_real_path)
    return abs_real_path

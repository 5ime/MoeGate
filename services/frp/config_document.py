"""FRP 配置文档：tomllib 解析与结构化序列化。"""
import logging
import tomllib
from typing import Any, Dict, List, Optional

from services.frp.exceptions import FRPConfigError
from services.frp.utils import escape_toml_string, generate_proxy_section, normalize_proxy_config

logger = logging.getLogger(__name__)

_TOP_LEVEL_SCALAR_ORDER = ("serverAddr", "serverPort")
_TABLE_SECTIONS = ("auth", "webServer")


def load_config_document(config_content: str) -> Dict[str, Any]:
    """将 FRP 配置文本解析为文档字典；空内容或解析失败时返回空字典。"""
    if not config_content or not config_content.strip():
        return {}
    try:
        data = tomllib.loads(config_content)
    except tomllib.TOMLDecodeError as exc:
        logger.warning("TOML 解析 FRP 配置失败: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}


def _serialize_scalar(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return f'{key} = {"true" if value else "false"}'
    if isinstance(value, int):
        return f"{key} = {value}"
    return f'{key} = "{escape_toml_string(str(value))}"'


def _serialize_table(section: str, table: Dict[str, Any]) -> str:
    lines = [f"[{section}]"]
    for key, value in table.items():
        if isinstance(value, (str, int, bool)):
            lines.append(_serialize_scalar(key, value))
    return "\n".join(lines)


def serialize_config_document(data: Dict[str, Any]) -> str:
    """将文档字典序列化为 FRP TOML 文本。"""
    if not data:
        return ""

    header_lines: List[str] = []
    for key in _TOP_LEVEL_SCALAR_ORDER:
        if key in data and isinstance(data[key], (str, int, bool)):
            header_lines.append(_serialize_scalar(key, data[key]))

    for key, value in data.items():
        if key in _TOP_LEVEL_SCALAR_ORDER or key in _TABLE_SECTIONS or key == "proxies":
            continue
        if isinstance(value, (str, int, bool)):
            header_lines.append(_serialize_scalar(key, value))

    sections: List[str] = []
    for section in _TABLE_SECTIONS:
        table = data.get(section)
        if isinstance(table, dict) and table:
            sections.append(_serialize_table(section, table))

    proxy_sections: List[str] = []
    proxies = data.get("proxies")
    if isinstance(proxies, list):
        for entry in proxies:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            try:
                proxy_sections.append(generate_proxy_section(entry).strip())
            except FRPConfigError:
                continue

    blocks = []
    if header_lines:
        blocks.append("\n".join(header_lines))
    if sections:
        blocks.append("\n\n".join(sections))
    if proxy_sections:
        blocks.append("\n\n".join(proxy_sections))

    if not blocks:
        return ""
    return "\n\n".join(blocks).strip() + "\n"


def proxies_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    proxies = data.get("proxies")
    if not isinstance(proxies, list):
        return []
    return [entry for entry in proxies if isinstance(entry, dict)]


def find_proxy_in_document(data: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    target = str(name or "").strip()
    if not target:
        return None
    for entry in proxies_list(data):
        if str(entry.get("name", "")) == target:
            return dict(entry)
    return None


def remove_proxy_from_document(data: Dict[str, Any], name: str) -> Dict[str, Any]:
    if not name:
        return data
    result = dict(data)
    target = str(name)
    result["proxies"] = [
        entry for entry in proxies_list(data) if str(entry.get("name", "")) != target
    ]
    return result


def upsert_proxy_in_document(data: Dict[str, Any], proxy_config: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_proxy_config(proxy_config)
    result = remove_proxy_from_document(data, normalized["name"])
    proxies = proxies_list(result)
    proxies.append(normalized)
    result["proxies"] = proxies
    return result


def validate_and_fix_document(data: Dict[str, Any]) -> Dict[str, Any]:
    """移除缺少域名的无效 HTTP 代理。"""
    result = dict(data)
    fixed: List[Dict[str, Any]] = []
    for entry in proxies_list(data):
        proxy_type = str(entry.get("type") or "tcp").lower()
        domains = entry.get("customDomains") or []
        if proxy_type == "http" and not domains:
            logger.warning("发现无效的HTTP代理配置 '%s'（缺少域名），将移除", entry.get("name"))
            continue
        fixed.append(entry)
    result["proxies"] = fixed
    return result

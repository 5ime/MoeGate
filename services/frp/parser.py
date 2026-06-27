"""FRP配置解析"""
import logging
import tomllib
from typing import Any, Dict, List, Optional

from services.frp.client import get_frp_config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)


def _normalize_proxy_entry(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将 TOML 代理表规范化为统一字段。"""
    name = raw.get("name")
    if not name:
        return None

    result: Dict[str, Any] = {"name": str(name)}

    proxy_type = raw.get("type")
    if proxy_type is not None:
        result["type"] = str(proxy_type)

    local_ip = raw.get("localIP")
    if local_ip is not None:
        result["localIP"] = str(local_ip)

    local_port = raw.get("localPort")
    if local_port is not None:
        try:
            result["localPort"] = int(local_port)
        except (TypeError, ValueError):
            pass

    remote_port = raw.get("remotePort")
    if remote_port is not None:
        try:
            result["remotePort"] = int(remote_port)
        except (TypeError, ValueError):
            pass

    domains = raw.get("customDomains")
    if isinstance(domains, list):
        items = [str(item).strip() for item in domains if str(item).strip()]
        if items:
            result["customDomains"] = items

    return result


def list_proxies_from_content(config_content: str) -> List[Dict[str, Any]]:
    """从配置文本列出所有代理（tomllib）。"""
    if not config_content or not config_content.strip():
        return []

    try:
        data = tomllib.loads(config_content)
    except tomllib.TOMLDecodeError as exc:
        logger.warning("TOML 解析 FRP 配置失败: %s", exc)
        return []

    proxies_raw = data.get("proxies")
    if proxies_raw is None:
        return []
    if not isinstance(proxies_raw, list):
        logger.warning("FRP 配置 proxies 字段非数组")
        return []

    proxies: List[Dict[str, Any]] = []
    for item in proxies_raw:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_proxy_entry(item)
        if normalized:
            proxies.append(normalized)
    return proxies


def parse_proxy_config(config_content: str, name: str) -> Optional[Dict[str, Any]]:
    """从配置内容中解析指定代理的配置。"""
    if not name:
        return None
    target = str(name).strip()
    if not target:
        return None

    for section_info in list_proxies_from_content(config_content or ""):
        if section_info.get("name") != target:
            continue
        logger.debug("解析代理配置 %s: %s", target, section_info)
        return section_info

    return None


def list_proxies() -> List[Dict[str, Any]]:
    """列出所有代理配置。"""
    return list_proxies_from_content(get_frp_config())


def list_proxies_for_container(container_name: str, config_content: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出属于指定容器的全部代理配置（含多端口附加代理）。"""
    from services.frp.utils import proxy_belongs_to_container

    if not container_name:
        return []
    content = config_content if config_content is not None else get_frp_config()
    return [
        proxy
        for proxy in list_proxies_from_content(content)
        if proxy_belongs_to_container(proxy.get("name"), container_name)
    ]


def get_proxy_config(name: str) -> Dict[str, Any]:
    """获取指定代理的配置。"""
    if not name:
        raise FRPConfigError("代理名称不能为空", 400)

    config_content = get_frp_config()
    proxy_config = parse_proxy_config(config_content, name)

    if not proxy_config:
        raise FRPConfigError(f"未找到名为 '{name}' 的代理配置", 404)

    logger.debug("解析代理配置 %s: %s", name, proxy_config)
    return proxy_config

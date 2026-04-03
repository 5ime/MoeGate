"""FRP配置解析"""
import re
import logging
from typing import Optional, Dict, Any, List
from services.frp.client import get_frp_config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)

# 预编译正则，避免重复构建
RE_SECTION_SPLIT = re.compile(r'\n\s*\[\[proxies\]\]\s*', re.IGNORECASE)
RE_NAME = re.compile(r'name\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_TYPE = re.compile(r'type\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_LOCAL_IP = re.compile(r'localIP\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_LOCAL_PORT = re.compile(r'localPort\s*=\s*(\d+)', re.IGNORECASE)
RE_REMOTE_PORT = re.compile(r'remotePort\s*=\s*(\d+)', re.IGNORECASE)
RE_DOMAINS = re.compile(r'customDomains\s*=\s*\[(.*?)\]', re.IGNORECASE | re.DOTALL)


def _split_proxy_sections(config_content: str) -> List[str]:
    """将配置按 [[proxies]] 分段，返回每个代理段的原始文本（不含头部以外内容）。"""
    if not config_content:
        return []
    parts = RE_SECTION_SPLIT.split('\n' + config_content)
    # 第一个 part 是头部公共配置，后续每个都是一个代理段
    return ['[[proxies]]\n' + part for part in parts[1:]]


def _parse_proxy_section(section_text: str) -> Optional[Dict[str, Any]]:
    """解析单个 [[proxies]] 段为字典。"""
    if not section_text:
        return None
    name_match = RE_NAME.search(section_text)
    if not name_match:
        return None
    name = name_match.group(1)

    result: Dict[str, Any] = {"name": name}

    m = RE_TYPE.search(section_text)
    if m:
        result["type"] = m.group(1)
    m = RE_LOCAL_IP.search(section_text)
    if m:
        result["localIP"] = m.group(1)
    m = RE_LOCAL_PORT.search(section_text)
    if m:
        try:
            result["localPort"] = int(m.group(1))
        except (TypeError, ValueError):
            pass
    m = RE_REMOTE_PORT.search(section_text)
    if m:
        try:
            result["remotePort"] = int(m.group(1))
        except (TypeError, ValueError):
            pass

    dm = RE_DOMAINS.search(section_text)
    if dm:
        domains_str = dm.group(1).replace('\n', ' ').strip()
        items = [d.strip().strip('"').strip("'") for d in domains_str.split(',') if d.strip()]
        if items:
            result["customDomains"] = items

    return result


def parse_proxy_config(config_content: str, name: str) -> Optional[Dict[str, Any]]:
    """从配置内容中解析指定代理的配置
    
    Args:
        config_content: FRP配置内容
        name: 代理名称
        
    Returns:
        Optional[Dict[str, Any]]: 代理配置字典，未找到返回None
    """
    if not name:
        return None
    target = str(name).strip()
    if not target:
        return None

    sections = _split_proxy_sections(config_content or "")
    for section_text in sections:
        section_info = _parse_proxy_section(section_text)
        if not section_info:
            continue
        if section_info.get("name") != target:
            continue
        logger.debug("解析代理配置 %s: %s", target, section_info)
        return section_info

    return None


def list_proxies() -> List[Dict[str, Any]]:
    """列出所有代理配置"""
    config_content = get_frp_config()
    sections = _split_proxy_sections(config_content or "")
    proxies: List[Dict[str, Any]] = []
    for section in sections:
        cfg = _parse_proxy_section(section)
        if cfg:
            proxies.append(cfg)
    return proxies


def get_proxy_config(name: str) -> Dict[str, Any]:
    """获取指定代理的配置
    
    Args:
        name: 代理名称
        
    Returns:
        Dict[str, Any]: 代理配置字典
        
    Raises:
        FRPConfigError: 代理不存在时抛出
    """
    if not name:
        raise FRPConfigError("代理名称不能为空", 400)
    
    config_content = get_frp_config()
    proxy_config = parse_proxy_config(config_content, name)
    
    if not proxy_config:
        raise FRPConfigError(f"未找到名为 '{name}' 的代理配置", 404)
    
    # 添加调试日志，确保配置解析正确
    logger.debug("解析代理配置 %s: %s", name, proxy_config)
    
    return proxy_config
"""FRP配置解析"""
import re
import logging
from typing import Optional, Dict, Any, List
from services.frp.client import get_frp_config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)

# 预编译正则，避免重复构建
RE_SECTION_SPLIT = re.compile(r'\n\s*\[\[proxies\]\]\s*', re.IGNORECASE)
RE_NAME = re.compile(r'name\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_TYPE = re.compile(r'type\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_LOCAL_IP = re.compile(r'localIP\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_LOCAL_PORT = re.compile(r'localPort\s*=\s*(\d+)', re.IGNORECASE)
RE_REMOTE_PORT = re.compile(r'remotePort\s*=\s*(\d+)', re.IGNORECASE)
RE_DOMAINS = re.compile(r'customDomains\s*=\s*\[(.*?)\]', re.IGNORECASE | re.DOTALL)


def _split_proxy_sections(config_content: str) -> List[str]:
    """将配置按 [[proxies]] 分段，返回每个代理段的原始文本（不含头部以外内容）。"""
    if not config_content:
        return []
    parts = RE_SECTION_SPLIT.split('\n' + config_content)
    # 第一个 part 是头部公共配置，后续每个都是一个代理段
    return ['[[proxies]]\n' + part for part in parts[1:]]


def _parse_proxy_section(section_text: str) -> Optional[Dict[str, Any]]:
    """解析单个 [[proxies]] 段为字典。"""
    if not section_text:
        return None
    name_match = RE_NAME.search(section_text)
    if not name_match:
        return None
    name = name_match.group(1)

    result: Dict[str, Any] = {"name": name}

    m = RE_TYPE.search(section_text)
    if m:
        result["type"] = m.group(1)
    m = RE_LOCAL_IP.search(section_text)
    if m:
        result["localIP"] = m.group(1)
    m = RE_LOCAL_PORT.search(section_text)
    if m:
        try:
            result["localPort"] = int(m.group(1))
        except (TypeError, ValueError):
            pass
    m = RE_REMOTE_PORT.search(section_text)
    if m:
        try:
            result["remotePort"] = int(m.group(1))
        except (TypeError, ValueError):
            pass

    dm = RE_DOMAINS.search(section_text)
    if dm:
        domains_str = dm.group(1).replace('\n', ' ').strip()
        items = [d.strip().strip('"').strip("'") for d in domains_str.split(',') if d.strip()]
        if items:
            result["customDomains"] = items

    return result


def parse_proxy_config(config_content: str, name: str) -> Optional[Dict[str, Any]]:
    """从配置内容中解析指定代理的配置
    
    Args:
        config_content: FRP配置内容
        name: 代理名称
        
    Returns:
        Optional[Dict[str, Any]]: 代理配置字典，未找到返回None
    """
    if not name:
        return None
    target = str(name).strip()
    if not target:
        return None

    sections = _split_proxy_sections(config_content or "")
    for section_text in sections:
        section_info = _parse_proxy_section(section_text)
        if not section_info:
            continue
        if section_info.get("name") != target:
            continue
        logger.debug("解析代理配置 %s: %s", target, section_info)
        return section_info

    return None


def list_proxies() -> List[Dict[str, Any]]:
    """列出所有代理配置"""
    config_content = get_frp_config()
    sections = _split_proxy_sections(config_content or "")
    proxies: List[Dict[str, Any]] = []
    for section in sections:
        cfg = _parse_proxy_section(section)
        if cfg:
            proxies.append(cfg)
    return proxies


def get_proxy_config(name: str) -> Dict[str, Any]:
    """获取指定代理的配置
    
    Args:
        name: 代理名称
        
    Returns:
        Dict[str, Any]: 代理配置字典
        
    Raises:
        FRPConfigError: 代理不存在时抛出
    """
    if not name:
        raise FRPConfigError("代理名称不能为空", 400)
    
    config_content = get_frp_config()
    proxy_config = parse_proxy_config(config_content, name)
    
    if not proxy_config:
        raise FRPConfigError(f"未找到名为 '{name}' 的代理配置", 404)
    
    # 添加调试日志，确保配置解析正确
    logger.debug("解析代理配置 %s: %s", name, proxy_config)
    
    return proxy_config


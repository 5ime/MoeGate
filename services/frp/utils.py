"""FRP工具函数"""
import re
import logging
from typing import Optional, Tuple, Dict, Any
from config import config
from services.frp.parser import get_proxy_config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)


def generate_domain(container_name: str, container_uuid: Optional[str] = None) -> str:
    """生成域名
    
    Args:
        container_name: 容器名称（就是 UUID）
        container_uuid: 容器 UUID（优先使用，如果提供）
        
    Returns:
        str: 生成的域名
    """
    # 优先使用 UUID，如果没有则使用容器名称（容器名称就是 UUID）
    if container_uuid:
        subdomain = container_uuid
    else:
        # 容器名称就是 UUID（标准格式）
        subdomain = container_name
    
    # UUID 中的连字符需要替换为横线（域名中连字符是合法的）
    # 但为了兼容性，保持 UUID 的原始格式
    # FRP_DOMAIN_SUFFIX 在配置加载时已规范化为不带前导点的 "example.com"
    domain_suffix = (config.FRP_DOMAIN_SUFFIX or "").lstrip(".")
    return f"{subdomain}.{domain_suffix}"


def generate_proxy_section(proxy_config: Dict[str, Any]) -> str:
    """生成代理配置段（TOML格式）
    
    Args:
        proxy_config: 代理配置字典
        
    Returns:
        str: TOML格式的代理配置段
        
    Raises:
        FRPConfigError: 配置缺少必要字段时抛出
    """
    name = proxy_config.get('name', '')
    proxy_type = proxy_config.get('type', 'tcp')
    local_ip = proxy_config.get('localIP', '127.0.0.1')
    local_port = proxy_config.get('localPort')
    
    if not name or not local_port:
        raise FRPConfigError("代理配置缺少必要字段: name 和 localPort", 400)
    
    custom_domains = proxy_config.get('customDomains', [])
    if proxy_type == 'http' and not custom_domains:
        logger.warning("HTTP类型代理 '%s' 缺少域名配置，自动转换为TCP类型", name)
        proxy_type = 'tcp'
        proxy_config['type'] = 'tcp'
    
    section = f'[[proxies]]\nname = "{name}"\ntype = "{proxy_type}"\nlocalIP = "{local_ip}"\nlocalPort = {local_port}\n'
    
    if proxy_type == 'http':
        if custom_domains:
            domains_str = ', '.join([f'"{d}"' for d in custom_domains])
            section += f'customDomains = [{domains_str}]\n'
            if 'remotePort' in proxy_config:
                section += f'remotePort = {proxy_config["remotePort"]}\n'
    else:
        remote_port = proxy_config.get('remotePort')
        if remote_port:
            section += f'remotePort = {remote_port}\n'
    
    section += '\n'
    return section


def validate_and_fix_config(config_content: str) -> str:
    """验证并修复配置中的无效HTTP代理
    
    Args:
        config_content: FRP配置内容
        
    Returns:
        str: 修复后的配置内容
    """
    from services.frp.proxy_manager import remove_proxy_from_config
    
    pattern = r'\[\[proxies\]\][\s\S]*?name\s*=\s*"([^"]+)"[\s\S]*?type\s*=\s*"http"[\s\S]*?(?=\[\[proxies\]\]|$)'
    matches = list(re.finditer(pattern, config_content))
    
    for match in matches:
        section = match.group(0)
        name_match = re.search(r'name\s*=\s*"([^"]+)"', section)
        if not name_match:
            continue
        
        name = name_match.group(1)
        has_domains = bool(re.search(r'customDomains\s*=', section)) or bool(re.search(r'subdomain\s*=', section))
        
        if not has_domains:
            logger.warning("发现无效的HTTP代理配置 '%s'（缺少域名），将移除", name)
            config_content = remove_proxy_from_config(config_content, name)
    
    return config_content


def get_common_config() -> str:
    """获取FRP通用配置段（TOML格式）"""
    common_config = f'serverAddr = "{config.FRP_SERVER_ADDR}"\nserverPort = {config.FRP_SERVER_PORT}\n'
    
    auth_token = getattr(config, 'FRP_AUTH_TOKEN', None)
    if auth_token:
        common_config += f'\n[auth]\nmethod = "token"\ntoken = "{auth_token}"\n'
    
    admin_ip = config.FRP_ADMIN_IP
    admin_port = config.FRP_ADMIN_PORT
    common_config += f'\n[webServer]\naddr = "{admin_ip}"\nport = {admin_port}\n'
    if config.FRP_ADMIN_USER:
        common_config += f'user = "{config.FRP_ADMIN_USER}"\n'
    if config.FRP_ADMIN_PASSWORD:
        common_config += f'password = "{config.FRP_ADMIN_PASSWORD}"\n'
    
    return common_config + '\n'


def determine_proxy_type(user_type: Optional[str], container_name: str, local_port: int) -> Tuple[bool, str]:
    """确定代理类型和来源
    
    Args:
        user_type: 用户指定的代理类型
        container_name: 容器名称
        local_port: 本地端口
        
    Returns:
        Tuple[bool, str]: (是否为HTTP类型, 类型来源说明)
    """
    if not config.FRP_USE_DOMAIN:
        return False, "TCP类型(FRP_USE_DOMAIN=false)"
    
    if user_type:
        user_type = user_type.lower().strip()
        if user_type == 'http':
            if config.FRP_DOMAIN_SUFFIX:
                return True, "用户指定(http)"
            else:
                logger.warning("用户指定HTTP类型但未配置域名后缀，已回退到TCP类型")
                return False, "用户指定(http)但回退到TCP(缺少域名后缀)"
        elif user_type == 'tcp':
            return False, "用户指定(tcp)"
        else:
            logger.warning("无效的代理类型 '%s'，默认使用TCP类型", user_type)
    
    if config.FRP_DOMAIN_SUFFIX:
        return True, "域名配置"
    
    return False, "默认(TCP)"


def build_proxy_config(container_name: str, local_port: int, remote_port: int, 
                       user_type: Optional[str] = None, container_uuid: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
    """构建代理配置字典
    
    Args:
        container_name: 容器名称
        local_port: 本地端口
        remote_port: 远程端口
        user_type: 用户指定的代理类型
        container_uuid: 容器 UUID（用于生成域名）
        
    Returns:
        Tuple[Dict[str, Any], str]: (代理配置字典, 类型来源说明)
    """
    proxy_config = {
        'name': container_name,
        'localIP': '127.0.0.1',
        'localPort': int(local_port),
    }
    
    is_http, type_source = determine_proxy_type(user_type, container_name, local_port)
    
    if is_http:
        proxy_config['type'] = 'http'
        proxy_config['customDomains'] = [generate_domain(container_name, container_uuid)]
        if not config.FRP_VHOST_HTTP_PORT:
            proxy_config['remotePort'] = remote_port
    else:
        proxy_config['type'] = 'tcp'
        proxy_config['remotePort'] = remote_port
    
    return proxy_config, type_source


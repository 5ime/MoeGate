"""FRP代理管理"""
import re
import logging
import threading
from typing import Tuple, Dict, Any, Optional
from services.frp.client import get_frp_config, update_frp_config
from services.frp.parser import get_proxy_config
from services.frp.utils import generate_proxy_section, get_common_config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)

# 配置更新锁，确保配置更新的原子性
_config_update_lock = threading.Lock()


def remove_proxy_from_config(config_content: str, name: str) -> str:
    """从配置内容中移除指定代理配置
    
    Args:
        config_content: FRP配置内容
        name: 代理名称
        
    Returns:
        str: 移除后的配置内容
    """
    if not name:
        return config_content
    
    pattern = rf'\[\[proxies\]\][\s\S]*?name\s*=\s*"{re.escape(name)}"[\s\S]*?(?=\[\[proxies\]\]|$)'
    new_config = re.sub(pattern, "", config_content).strip()
    return re.sub(r'\n{3,}', '\n\n', new_config)


def find_proxy_section(config_content: str, name: str) -> Tuple[Optional[str], Optional[str]]:
    """查找指定名称的代理配置段
    
    Args:
        config_content: FRP配置内容
        name: 代理名称
        
    Returns:
        Tuple[Optional[str], Optional[str]]: (配置段内容, 错误消息)
    """
    if not name:
        return None, "未提供代理名称"
    
    pattern = rf'(\[\[proxies\]\][\s\S]*?name\s*=\s*"{re.escape(name)}"[\s\S]*?)(?=\[\[proxies\]\]|$)'
    match = re.search(pattern, config_content)
    
    if not match:
        return None, f"未找到名为 '{name}' 的代理配置"
    
    return match.group(0), None


def add_proxy_to_config(config_content: str, proxy_config: Dict[str, Any]) -> str:
    """向配置内容中添加代理配置
    
    Args:
        config_content: 当前FRP配置内容
        proxy_config: 要添加的代理配置
        
    Returns:
        str: 添加后的配置内容
    """
    from services.frp.utils import validate_and_fix_config
    config_content = validate_and_fix_config(config_content)
    proxy_section = generate_proxy_section(proxy_config)
    
    if not config_content.strip() or '[[proxies]]' not in config_content:
        if not config_content.endswith('\n\n'):
            config_content = config_content.rstrip() + '\n\n'
        return config_content + proxy_section
    
    name = proxy_config.get('name')
    if name and find_proxy_section(config_content, name)[0]:
        config_content = remove_proxy_from_config(config_content, name)
    
    if not config_content.endswith('\n\n'):
        config_content = config_content.rstrip() + '\n\n'
    
    return config_content + proxy_section


def add_proxy_config(proxy_config: Dict[str, Any]) -> Tuple[bool, str]:
    """添加新的代理配置（线程安全）
    
    Args:
        proxy_config: 代理配置字典
        
    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    try:
        if not proxy_config.get('name') or not proxy_config.get('localPort'):
            return False, "代理配置缺少必要字段: name 和 localPort"
        
        proxy_name = proxy_config.get('name')
        
        # 使用锁保护配置更新操作
        with _config_update_lock:
            try:
                current_config = get_frp_config()
            except FRPConfigError as e:
                logger.warning("无法获取当前FRP配置: %s，将生成新配置", e.message)
                current_config = get_common_config()
            
            new_config = add_proxy_to_config(current_config, proxy_config)
            
            if proxy_name not in new_config:
                logger.error("代理配置 %s 未添加到新配置中", proxy_name)
                return False, f"代理配置添加失败: {proxy_name} 未找到"
            
            success, msg = update_frp_config(new_config)
            
            if success:
                logger.info("成功添加代理配置: %s", proxy_name)
            else:
                logger.error("添加代理配置失败: %s, 错误: %s", proxy_name, msg)
            return success, msg
    except Exception as e:
        logger.exception("添加代理配置失败: %s", e)
        return False, f"添加代理配置失败: {str(e)}"


def update_proxy_config(name: str, proxy_config: Dict[str, Any]) -> Tuple[bool, str]:
    """更新指定代理的配置（线程安全）
    
    Args:
        name: 代理名称
        proxy_config: 代理配置字典
        
    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    try:
        if not name:
            return False, "代理名称不能为空"
        
        proxy_config['name'] = name
        
        # 使用锁保护配置更新操作
        with _config_update_lock:
            current_config = get_frp_config()
            
            if not find_proxy_section(current_config, name)[0]:
                return False, f"未找到名为 '{name}' 的代理配置"
            
            new_config = remove_proxy_from_config(current_config, name)
            new_config = add_proxy_to_config(new_config, proxy_config)
            
            success, msg = update_frp_config(new_config)
            if success:
                logger.info("成功更新代理配置: %s", name)
            return success, msg
    except Exception as e:
        logger.exception("更新代理配置失败")
        return False, f"更新代理配置失败: {str(e)}"


def delete_proxy_config(name: str) -> Tuple[bool, str]:
    """删除指定代理的配置（线程安全）
    
    Args:
        name: 代理名称
        
    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    try:
        if not name:
            return False, "代理名称不能为空"
        
        # 使用锁保护配置更新操作
        with _config_update_lock:
            current_config = get_frp_config()
            
            if not find_proxy_section(current_config, name)[0]:
                return False, f"未找到名为 '{name}' 的代理配置"
            
            new_config = remove_proxy_from_config(current_config, name)
            if not new_config.strip() or 'serverAddr' not in new_config:
                new_config = get_common_config()
            
            success, msg = update_frp_config(new_config)
            if success:
                logger.info("成功删除代理配置: %s", name)
            return success, msg
    except Exception as e:
        logger.exception("删除代理配置失败")
        return False, f"删除代理配置失败: {str(e)}"


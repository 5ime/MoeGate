"""FRP API客户端"""
import requests
import logging
from typing import Optional, Tuple
from config import config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)


def _get_auth() -> Optional[requests.auth.HTTPBasicAuth]:
    """获取HTTP Basic Auth认证对象"""
    if config.FRP_ADMIN_USER and config.FRP_ADMIN_PASSWORD:
        from requests.auth import HTTPBasicAuth
        return HTTPBasicAuth(config.FRP_ADMIN_USER, config.FRP_ADMIN_PASSWORD)
    return None


def _make_request(method: str, url: str, data: Optional[bytes] = None, timeout: Optional[int] = None) -> requests.Response:
    """发送HTTP请求到FRP管理API
    
    Args:
        method: HTTP方法 (GET, PUT, DELETE)
        url: 请求URL
        data: 请求体数据
        timeout: 超时时间（秒），默认使用 REQUEST_TIMEOUT
        
    Returns:
        requests.Response: HTTP响应对象
        
    Raises:
        FRPConfigError: 请求失败时抛出
    """
    if not config.FRP_SERVER_ADDR:
        raise FRPConfigError("FRP服务器地址未配置", 500)
    
    if timeout is None:
        timeout = config.REQUEST_TIMEOUT

    headers = {"Content-Type": "text/plain; charset=utf-8"}
    auth = _get_auth()
    
    try:
        method_map = {
            'GET': requests.get,
            'PUT': requests.put,
            'DELETE': requests.delete
        }
        if method.upper() not in method_map:
            raise FRPConfigError(f"不支持的HTTP方法: {method}", 400)
        
        response = method_map[method.upper()](url, data=data, auth=auth, headers=headers, timeout=timeout)
        return response
    except requests.Timeout:
        raise FRPConfigError(f"FRP API请求超时（>{timeout}秒）", 504)
    except requests.ConnectionError as e:
        raise FRPConfigError(f"无法连接到FRP管理API: {str(e)}", 503)
    except requests.RequestException as e:
        raise FRPConfigError(f"请求失败: {str(e)}", 500)


def get_frp_config() -> str:
    """从FRP管理API获取当前完整配置
    
    Returns:
        str: FRP配置内容
        
    Raises:
        FRPConfigError: 获取配置失败时抛出
    """
    api_url = config.FRP_ADMIN_ADDR
    get_url = f"{api_url}/api/config"
    
    response = _make_request('GET', get_url)
    if response.status_code == 200:
        response.encoding = 'utf-8'
        return response.text
    else:
        error_msg = f"获取FRP配置失败: HTTP {response.status_code}, {response.text[:200]}"
        logger.error(error_msg)
        raise FRPConfigError(error_msg, response.status_code)


def reload_frp_config(timeout: int = 5) -> Tuple[bool, str]:
    """重载FRP配置
    
    Args:
        timeout: 超时时间（秒）
        
    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    api_url = config.FRP_ADMIN_ADDR
    reload_url = f"{api_url}/api/reload"
    
    try:
        response = _make_request('GET', reload_url, timeout=timeout)
        if response.status_code == 200:
            logger.info("FRP配置重载成功")
            return True, "配置重载成功"
        else:
            error_msg = f"配置重载失败: HTTP {response.status_code}"
            logger.error(error_msg)
            return False, error_msg
    except FRPConfigError as e:
        logger.error("FRP配置重载异常: %s", e.message)
        return False, e.message


def update_frp_config(frp_config: str, timeout: int = 5) -> Tuple[bool, str]:
    """更新FRP配置并重载
    
    Args:
        frp_config: FRP配置内容
        timeout: 超时时间（秒）
        
    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    if not frp_config or not isinstance(frp_config, str):
        return False, "FRP配置内容无效"
    
    # 验证并修复配置中的无效HTTP代理
    from services.frp.utils import validate_and_fix_config
    frp_config = validate_and_fix_config(frp_config)
    
    api_url = config.FRP_ADMIN_ADDR
    upload_url = f"{api_url}/api/config"
    
    try:
        config_bytes = frp_config.encode('utf-8')
        response = _make_request('PUT', upload_url, data=config_bytes, timeout=timeout)
        
        if response.status_code != 200:
            error_msg = f"配置文件更新失败: HTTP {response.status_code}"
            logger.error(error_msg)
            return False, error_msg
        
        success, msg = reload_frp_config(timeout)
        if success:
            logger.info("FRP配置更新和热重载成功")
            return True, "配置文件更新和热重载成功"
        else:
            return False, f"配置已更新，但重载失败: {msg}"
    except FRPConfigError as e:
        logger.error("FRP配置更新失败: %s", e.message)
        return False, e.message
    except Exception as e:
        logger.exception("FRP配置更新时发生未知错误: %s", e)
        return False, f"未知错误: {str(e)}"


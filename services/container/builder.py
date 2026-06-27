"""容器构建和创建（路由入口，具体实现见 compose / single_container）。"""
import os
import logging
from typing import Dict, Any

from config.settings import config as default_config, AppConfig
from services.container.compose import (
    start_from_compose,
    _start_from_compose_streaming,
)
from services.container.single_container import (
    start_from_dockerfile,
    _start_from_dockerfile_streaming,
)

logger = logging.getLogger(__name__)

def start_container_from_source(file_path: str, app_config: AppConfig = None, **params) -> Dict[str, Any]:
    """根据文件类型选择相应的启动方式
    
    Args:
        file_path: Docker配置文件路径
        app_config: 应用配置对象，默认使用全局配置
        **params: 容器启动参数
        
    Returns:
        Dict[str, Any]: 容器信息字典
    """
    if app_config is None:
        app_config = default_config
    
    if file_path.endswith(('.yaml', '.yml')):
        return start_from_compose(
            file_path,
            params['uid'],
            params['max_time'],
            params['env'],
            resource_limits=params.get('resource_limits'),
            app_config=app_config,
            meta=params.get('meta'),
            min_port=params.get('min_port'),
            max_port=params.get('max_port'),
            port_mappings=params.get('port_mappings'),
        )
    
    if 'path' in params:
        dockerfile_dir = params['path']
    else:
        dockerfile_dir = os.path.dirname(file_path) if os.path.dirname(file_path) else '.'
    
    dockerfile_params = {
        'path': dockerfile_dir,
        'uid': params['uid'],
        'cmd': params.get('cmd'),
        'min_port': params['min_port'],
        'max_port': params['max_port'],
        'max_time': params['max_time'],
        'env': params.get('env', {}),
        'tag': params.get('tag'),
        'port_mappings': params.get('port_mappings'),
        'resource_limits': params.get('resource_limits'),
        'meta': params.get('meta'),
        'network': params.get('network'),
    }
    return start_from_dockerfile(app_config=app_config, **dockerfile_params)


def start_container_from_source_streaming(file_path: str, app_config: AppConfig = None, **params):
    """与 start_container_from_source 相同，但以生成器形式逐行返回构建日志。

    Yields:
        str: 日志行（普通文本）。最后一条 yield 的值为最终的容器信息字典。
    """
    if app_config is None:
        app_config = default_config

    if file_path.endswith(('.yaml', '.yml')):
        yield from _start_from_compose_streaming(
            file_path,
            params['uid'],
            params['max_time'],
            params['env'],
            resource_limits=params.get('resource_limits'),
            app_config=app_config,
            meta=params.get('meta'),
            min_port=params.get('min_port'),
            max_port=params.get('max_port'),
            port_mappings=params.get('port_mappings'),
        )
        return

    if 'path' in params:
        dockerfile_dir = params['path']
    else:
        dockerfile_dir = os.path.dirname(file_path) if os.path.dirname(file_path) else '.'

    dockerfile_params = {
        'path': dockerfile_dir,
        'uid': params['uid'],
        'cmd': params.get('cmd'),
        'min_port': params['min_port'],
        'max_port': params['max_port'],
        'max_time': params['max_time'],
        'env': params.get('env', {}),
        'tag': params.get('tag'),
        'port_mappings': params.get('port_mappings'),
        'resource_limits': params.get('resource_limits'),
        'meta': params.get('meta'),
        'network': params.get('network'),
    }
    yield from _start_from_dockerfile_streaming(app_config=app_config, **dockerfile_params)

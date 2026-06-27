"""容器服务模块

职责分层：
- lifecycle：启动入口、参数校验、FRP 后处理
- operations：重启、停止、续期、销毁
- builder：按来源类型分发到 compose / single_container 链
- compose：Compose 项目全链路（CLI、环境变量、准备、启动）
- single_container：单容器全链路（镜像拉取/构建、镜像直启、Dockerfile）
- container_create / port_manager / network_pool / info：可复用底层工具
"""
from services.container.lifecycle import start_container, start_container_streaming
from services.container.operations import (
    restart_container,
    restart_compose_project,
    restart_any,
    stop_container,
    stop_compose_project,
    stop_any,
    get_destroy_status,
    get_compose_project_destroy_status,
    renew_task,
    renew_compose_project,
    renew_any,
)
from services.container.info import list_containers, get_container_info, get_container_detail, get_compose_project_detail

__all__ = [
    'start_container',
    'start_container_streaming',
    'restart_container',
    'restart_compose_project',
    'restart_any',
    'stop_container',
    'stop_compose_project',
    'stop_any',
    'get_destroy_status',
    'get_compose_project_destroy_status',
    'renew_task',
    'renew_compose_project',
    'renew_any',
    'list_containers',
    'get_container_info',
    'get_container_detail',
    'get_compose_project_detail',
]

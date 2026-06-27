"""容器信息查询"""
import logging
from typing import Dict, Any
from docker.errors import NotFound
from config.settings import config as default_config
from services.container.port_manager import get_port_info
from infra.docker import ensure_client
from core.exceptions import ContainerNotFoundError

logger = logging.getLogger(__name__)


def _parse_docker_env(env_list) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for item in env_list or []:
        text = str(item)
        if "=" in text:
            key, value = text.split("=", 1)
            parsed[key] = value
        else:
            parsed[text] = ""
    return parsed


def sort_compose_container_details(items):
    return sorted(
        items,
        key=lambda item: (
            str(item.get("compose_service") or ""),
            str(item.get("container_name") or ""),
        ),
    )


def _add_frp_mapping_info(container_info: Dict[str, Any], app_config):
    """在容器信息中添加FRP映射地址信息
    
    根据容器名称反查FRP配置中的代理配置，获取映射地址。
    
    Args:
        container_info: 容器信息字典
        app_config: 应用配置对象
    """
    if not app_config.ENABLE_FRP:
        return
    
    container_name = container_info.get('container_name')
    if not container_name:
        return
    
    try:
        from services.frp.client import get_frp_config
        from services.frp.parser import list_proxies_for_container
        from services.frp.utils import proxy_config_to_api

        config_content = get_frp_config()
        proxy_configs = list_proxies_for_container(container_name, config_content)
        if not proxy_configs:
            logger.debug("容器 %s 的FRP代理配置未找到", container_name)
            return

        api_entries = [
            proxy_config_to_api(
                item,
                compose_service=container_info.get("compose_service"),
                compose_project_id=container_info.get("compose_project_id"),
            )
            for item in proxy_configs
        ]
        container_info['frp_proxy_configs'] = api_entries
        logger.info(
            "成功为容器 %s 添加 %d 条 FRP 映射信息",
            container_name,
            len(api_entries),
        )
    except Exception as e:
        logger.debug("获取容器 %s 的FRP映射信息失败: %s", container_name, e)


def get_container_info(container, *, include_environment: bool = True) -> Dict[str, Any]:
    """获取单个容器信息
    
    Args:
        container: Docker容器对象
        include_environment: 是否返回完整 environment；False 时仅返回 environment_keys
        
    Returns:
        Dict[str, Any]: 容器信息字典
    """
    try:
        if not hasattr(container, '_attrs') or not container._attrs:
            container.reload()
        container_name = container.name
        
        started_at = (
            container.attrs.get('State', {}).get('StartedAt')
            or container.attrs.get('Created')
            or ''
        )

        labels = container.attrs.get("Config", {}).get("Labels") or {}
        env_list = container.attrs.get("Config", {}).get("Env") or []
        parsed_env = _parse_docker_env(env_list)

        container_data = {
            "container_id": container.id,
            "container_name": container_name,
            "container_uuid": container_name,  # UUID格式的容器名称
            "status": getattr(container, 'status', 'unknown'),
            "ports": get_port_info(container),
            "start_time": started_at,
            "compose_project_id": labels.get("moegate.compose_project_id"),
            "compose_service": labels.get("moegate.compose_service"),
        }
        if include_environment:
            container_data["environment"] = parsed_env
        else:
            container_data["environment_keys"] = sorted(parsed_env.keys())
        _add_frp_mapping_info(container_data, default_config)
        return container_data
    except Exception:
        logger.exception("获取容器信息失败: %s", getattr(container, 'id', 'unknown'))
        raise


def list_containers() -> Dict[str, Any]:
    """获取容器列表
    
    Returns:
        Dict[str, Any]: 包含容器列表的字典，格式为 {"total": int, "containers": List[Dict]}
    """
    client = ensure_client()
    if not client:
        return {"total": 0, "containers": []}

    managed_containers = client.containers.list(all=True, filters={"label": "moegate.managed=true"})
    containers = managed_containers

    info = []
    running_count = 0
    compose_count = 0
    for container in containers:
        try:
            if not hasattr(container, '_attrs') or not container._attrs:
                container.reload()
            labels = container.attrs.get('Config', {}).get('Labels') or {}
            compose_project_id = labels.get('moegate.compose_project_id')
            started_at = (
                container.attrs.get('State', {}).get('StartedAt')
                or container.attrs.get('Created')
                or ''
            )
            status = getattr(container, 'status', 'unknown')
            if str(status).lower() == 'running':
                running_count += 1
            if compose_project_id:
                compose_count += 1

            container_info = {
                "id": container.id,
                "name": container.name,
                "status": status,
                "start_time": started_at,
                "ports": get_port_info(container),
                "managed": labels.get('moegate.managed') == 'true',
            }
            if compose_project_id:
                container_info['compose_project_id'] = compose_project_id
            info.append(container_info)
        except Exception as e:
            logger.warning("获取容器 %s 信息失败: %s", getattr(container, 'id', 'unknown'), e)

    return {
        "total": len(info),
        "running": running_count,
        "standalone": max(0, len(info) - compose_count),
        "compose": compose_count,
        "fallback_all": False,
        "containers": info,
    }


def get_container_detail(container_id: str, *, verbose: bool = False) -> Dict[str, Any]:
    """根据容器ID获取容器详情（直接查询Docker）。"""
    client = ensure_client()
    if not client:
        raise ContainerNotFoundError(container_id)

    try:
        container = client.containers.get(container_id)
        labels = container.attrs.get('Config', {}).get('Labels') or {}
        if labels.get('moegate.managed') != 'true':
            raise ContainerNotFoundError(container_id)
        return get_container_info(container, include_environment=verbose)
    except NotFound:
        raise ContainerNotFoundError(container_id)


def get_compose_project_detail(compose_project_id: str, *, verbose: bool = False) -> Dict[str, Any]:
    """根据 compose 项目 ID 获取项目详情。"""
    client = ensure_client()
    if not client:
        raise ContainerNotFoundError(compose_project_id)

    containers = client.containers.list(
        all=True,
        filters={
            "label": [
                "moegate.managed=true",
                f"moegate.compose_project_id={compose_project_id}",
            ]
        },
    )
    if not containers:
        raise ContainerNotFoundError(compose_project_id)

    container_details = [
        get_container_info(container, include_environment=verbose) for container in containers
    ]
    status_summary: Dict[str, int] = {}
    for item in container_details:
        status = str(item.get("status") or "unknown")
        status_summary[status] = status_summary.get(status, 0) + 1

    return {
        "compose_project_id": compose_project_id,
        "total": len(container_details),
        "status_summary": status_summary,
        "containers": container_details,
    }


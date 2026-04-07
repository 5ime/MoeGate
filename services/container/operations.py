"""容器操作（重启、停止、续期）"""
import logging
from typing import Dict, Any
from datetime import datetime
from config.settings import config as default_config, AppConfig
from core.exceptions import (
    ValidationError,
    ContainerNotFoundError,
    ManagedEntityNotFoundError,
    MaxRenewTimesExceededError,
)
from utils.destroy import (
    submit_destroy_task,
    get_destroy_task_status,
    get_compose_project_cleanup_task_status,
    submit_compose_project_cleanup_task,
)
from utils.container_manager import get_container_manager
from infra.docker import ensure_client

logger = logging.getLogger(__name__)


def _task_status(task: Dict[str, Any]) -> str:
    return str((task or {}).get("status") or "").strip().lower()


def _build_absent_container_destroy_result(container_id: str) -> Dict[str, Any]:
    finished_at = datetime.now().isoformat()
    return {
        "container_id": container_id,
        "destroy_task": {
            "container_id": container_id,
            "status": "success",
            "submitted_at": finished_at,
            "started_at": finished_at,
            "finished_at": finished_at,
            "error": None,
        },
        "stop_time": finished_at,
        "already_absent": True,
    }


def _build_absent_compose_project_destroy_result(compose_project_id: str) -> Dict[str, Any]:
    finished_at = datetime.now().isoformat()
    cleanup_task = {
        "compose_project_id": compose_project_id,
        "status": "success",
        "submitted_at": finished_at,
        "started_at": finished_at,
        "finished_at": finished_at,
        "error": None,
        "container_ids": [],
        "network_names": [],
        "removed_networks": [],
    }
    return {
        "compose_project_id": compose_project_id,
        "container_ids": [],
        "destroy_tasks": [],
        "stopped_count": 0,
        "network_names": [],
        "network_cleanup_task": cleanup_task,
        "stop_time": finished_at,
        "already_absent": True,
    }


def _build_existing_compose_project_destroy_result(compose_project_id: str, cleanup_task: Dict[str, Any]) -> Dict[str, Any]:
    container_ids = list(cleanup_task.get("container_ids") or [])
    return {
        "compose_project_id": compose_project_id,
        "container_ids": container_ids,
        "destroy_tasks": [get_destroy_task_status(container_id) for container_id in container_ids],
        "stopped_count": len(container_ids),
        "network_names": list(cleanup_task.get("network_names") or []),
        "network_cleanup_task": cleanup_task,
        "stop_time": datetime.now().isoformat(),
        "already_absent": _task_status(cleanup_task) == "success",
    }


def _find_compose_project_containers(compose_project_id: str):
    """按 compose 项目标识获取受管容器列表，未命中时返回空列表。"""
    client = ensure_client()
    if not client:
        return []

    containers = client.containers.list(
        all=True,
        filters={
            "label": [
                "moegate.managed=true",
                f"moegate.compose_project_id={compose_project_id}",
            ]
        },
    )
    return containers


def _list_compose_project_containers(compose_project_id: str):
    """按 compose 项目标识获取受管容器列表。"""
    containers = _find_compose_project_containers(compose_project_id)
    if not containers:
        raise ContainerNotFoundError(compose_project_id)
    return containers


def _resolve_managed_container(container_id: str):
    """解析受管容器，不允许操作非本系统管理的容器。"""
    manager = get_container_manager()
    container = manager.get_container(container_id)

    if container is None:
        client = ensure_client()
        if client:
            try:
                container = client.containers.get(container_id)
                labels = container.attrs.get('Config', {}).get('Labels') or {}
                if labels.get('moegate.managed') != 'true':
                    return None
                manager.add_container(container.id, container)
            except Exception:
                container = None

    return container


def restart_container(data: Dict[str, Any]) -> Dict[str, Any]:
    """重启容器
    
    Args:
        data: 包含container_id的字典
        
    Returns:
        Dict[str, Any]: 包含容器重启信息的字典
        
    Raises:
        ValidationError: 缺少container_id时抛出
        ContainerNotFoundError: 容器不存在时抛出
    """
    container_id = data.get("container_id")
    
    if not container_id:
        raise ValidationError("缺少 container_id 参数")

    container = _resolve_managed_container(container_id)

    if container:
        container.restart()
        return {
            "container_id": container.id,
            "restart_time": datetime.now().isoformat(),
        }
    else:
        raise ContainerNotFoundError(container_id)


def stop_container(data: Dict[str, Any]) -> Dict[str, Any]:
    """停止容器
    
    Args:
        data: 包含container_id的字典
        
    Returns:
        Dict[str, Any]: 包含容器停止信息的字典
        
    Raises:
        ValidationError: 缺少container_id时抛出
    """
    container_id = data.get("container_id")

    if not container_id:
        raise ValidationError("缺少 container_id 参数")

    container = _resolve_managed_container(container_id)
    if container is None:
        existing_task = get_destroy_task_status(container_id)
        if _task_status(existing_task) in {"pending", "running", "success", "failed"}:
            logger.debug("容器 %s 删除任务已存在，直接返回当前状态: %s", container_id, _task_status(existing_task))
            return {
                "container_id": container_id,
                "destroy_task": existing_task,
                "stop_time": datetime.now().isoformat(),
                "already_absent": _task_status(existing_task) == "success",
            }
        logger.debug("容器 %s 已不存在，删除请求按成功处理", container_id)
        return _build_absent_container_destroy_result(container_id)

    task = submit_destroy_task(container_id)
    logger.info("容器 %s 删除任务已提交", container_id)
    return {
        "container_id": container_id,
        "destroy_task": task,
        "stop_time": datetime.now().isoformat(),
    }


def stop_compose_project(data: Dict[str, Any]) -> Dict[str, Any]:
    """按 compose 项目 ID 停止并删除所有受管容器。"""
    compose_project_id = data.get("compose_project_id")
    if not compose_project_id:
        raise ValidationError("缺少 compose_project_id 参数")

    cleanup_task = get_compose_project_cleanup_task_status(compose_project_id)
    if _task_status(cleanup_task) in {"pending", "running", "success", "failed"}:
        logger.debug("Compose 项目 %s 删除任务已存在，直接返回当前状态: %s", compose_project_id, _task_status(cleanup_task))
        return _build_existing_compose_project_destroy_result(compose_project_id, cleanup_task)

    containers = _find_compose_project_containers(compose_project_id)
    if not containers:
        logger.debug("Compose 项目 %s 已不存在，删除请求按成功处理", compose_project_id)
        return _build_absent_compose_project_destroy_result(compose_project_id)

    client = ensure_client()

    stopped_ids = []
    destroy_tasks = []
    for container in containers:
        task = submit_destroy_task(container.id)
        destroy_tasks.append(task)
        stopped_ids.append(container.id)

    network_names = []
    try:
        networks = client.networks.list(
            filters={
                "label": [
                    "moegate.managed=true",
                    f"moegate.compose_project_id={compose_project_id}",
                ]
            }
        )
        for network in networks:
            network_name = getattr(network, "name", None)
            if network_name:
                network_names.append(network_name)
    except Exception as list_network_err:
        logger.warning("查询 Compose 网络失败: %s", list_network_err)

    cleanup_task = submit_compose_project_cleanup_task(compose_project_id, stopped_ids, network_names)
    logger.info(
        "Compose 项目 %s 删除任务已提交，容器数: %d，网络数: %d",
        compose_project_id,
        len(stopped_ids),
        len(network_names),
    )

    return {
        "compose_project_id": compose_project_id,
        "container_ids": stopped_ids,
        "destroy_tasks": destroy_tasks,
        "stopped_count": len(stopped_ids),
        "network_names": network_names,
        "network_cleanup_task": cleanup_task,
        "stop_time": datetime.now().isoformat(),
    }


def stop_any(data: Dict[str, Any]) -> Dict[str, Any]:
    """统一删除入口：自动识别 Compose 项目或单容器。

    识别逻辑：
    - 优先尝试按 compose_project_id 删除（若该项目下存在受管容器则视为项目）
    - 若项目不存在，再按 container_id 删除单容器
    """
    entity_id = data.get("id") or data.get("entity_id") or data.get("container_id") or data.get("compose_project_id")
    if not entity_id:
        raise ValidationError("缺少 id 参数")

    compose_containers = _find_compose_project_containers(entity_id)
    if compose_containers:
        result = stop_compose_project({"compose_project_id": entity_id})
        return {"kind": "compose_project", **result}

    compose_cleanup_task = get_compose_project_cleanup_task_status(entity_id)
    if _task_status(compose_cleanup_task) in {"pending", "running", "success", "failed"}:
        result = stop_compose_project({"compose_project_id": entity_id})
        return {"kind": "compose_project", **result}

    container = _resolve_managed_container(entity_id)
    if container is not None:
        result = stop_container({"container_id": entity_id})
        return {"kind": "container", **result}

    destroy_task = get_destroy_task_status(entity_id)
    if _task_status(destroy_task) in {"pending", "running", "success", "failed"}:
        result = stop_container({"container_id": entity_id})
        return {"kind": "container", **result}

    result = _build_absent_compose_project_destroy_result(entity_id)
    return {"kind": "compose_project", **result}


def restart_any(data: Dict[str, Any]) -> Dict[str, Any]:
    """统一重启入口：自动识别 Compose 项目或单容器。"""
    entity_id = data.get("id") or data.get("entity_id") or data.get("container_id") or data.get("compose_project_id")
    if not entity_id:
        raise ValidationError("缺少 id 参数")

    compose_containers = _find_compose_project_containers(entity_id)
    if compose_containers:
        result = restart_compose_project({"compose_project_id": entity_id})
        return {"kind": "compose_project", **result}

    container = _resolve_managed_container(entity_id)
    if container is not None:
        result = restart_container({"container_id": entity_id})
        return {"kind": "container", **result}

    raise ManagedEntityNotFoundError(entity_id)


def renew_any(data: Dict[str, Any], app_config: AppConfig = None) -> Dict[str, Any]:
    """统一续期入口：自动识别 Compose 项目或单容器。"""
    entity_id = data.get("id") or data.get("entity_id") or data.get("container_id") or data.get("compose_project_id")
    if not entity_id:
        raise ValidationError("缺少 id 参数")

    compose_containers = _find_compose_project_containers(entity_id)
    if compose_containers:
        result = renew_compose_project({"compose_project_id": entity_id}, app_config=app_config)
        return {"kind": "compose_project", **result}

    container = _resolve_managed_container(entity_id)
    if container is not None:
        result = renew_task({"container_id": entity_id}, app_config=app_config)
        return {"kind": "container", **result}

    raise ManagedEntityNotFoundError(entity_id)


def get_destroy_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """获取容器异步销毁任务状态。"""
    container_id = data.get("container_id")
    if not container_id:
        raise ValidationError("缺少 container_id 参数")
    task = get_destroy_task_status(container_id)
    if _task_status(task) != "not_found":
        return task

    if _resolve_managed_container(container_id) is None:
        return {
            "container_id": container_id,
            "status": "success",
            "phase": "finished",
            "already_absent": True,
        }
    return task


def get_compose_project_destroy_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """获取 Compose 项目异步删除任务状态。"""
    compose_project_id = data.get("compose_project_id")
    if not compose_project_id:
        raise ValidationError("缺少 compose_project_id 参数")

    cleanup_task = get_compose_project_cleanup_task_status(compose_project_id)
    if _task_status(cleanup_task) == "not_found":
        if not _find_compose_project_containers(compose_project_id):
            return {
                "compose_project_id": compose_project_id,
                "status": "success",
                "phase": "finished",
                "container_ids": [],
                "destroy_tasks": [],
                "network_cleanup_task": cleanup_task,
                "already_absent": True,
            }

    container_ids = list(cleanup_task.get("container_ids") or [])
    destroy_tasks = [get_destroy_task_status(container_id) for container_id in container_ids]

    cleanup_status = _task_status(cleanup_task)
    if cleanup_status == "success":
        status = "success"
        phase = "finished"
    elif cleanup_status == "failed":
        status = "failed"
        phase = "failed"
    elif cleanup_status in {"pending", "running"}:
        if destroy_tasks and all(
            str(task.get("status") or "").lower() in {"success", "not_found"}
            for task in destroy_tasks
        ):
            status = cleanup_status
            phase = "cleaning_networks"
        else:
            status = cleanup_status
            phase = "destroying_containers"
    else:
        status = "not_found"
        phase = "not_found"

    return {
        "compose_project_id": compose_project_id,
        "status": status,
        "phase": phase,
        "container_ids": container_ids,
        "destroy_tasks": destroy_tasks,
        "network_cleanup_task": cleanup_task,
    }


def restart_compose_project(data: Dict[str, Any]) -> Dict[str, Any]:
    """按 compose 项目 ID 重启项目下所有受管容器。"""
    compose_project_id = data.get("compose_project_id")
    if not compose_project_id:
        raise ValidationError("缺少 compose_project_id 参数")

    containers = _list_compose_project_containers(compose_project_id)

    restarted_ids = []
    manager = get_container_manager()
    for container in containers:
        container.restart()
        manager.add_container(container.id, container)
        restarted_ids.append(container.id)

    return {
        "compose_project_id": compose_project_id,
        "container_ids": restarted_ids,
        "restarted_count": len(restarted_ids),
        "restart_time": datetime.now().isoformat(),
    }


def renew_compose_project(data: Dict[str, Any], app_config: AppConfig = None) -> Dict[str, Any]:
    """按 compose 项目 ID 续期项目下所有受管容器。"""
    if app_config is None:
        app_config = default_config

    compose_project_id = data.get("compose_project_id")
    if not compose_project_id:
        raise ValidationError("缺少 compose_project_id 参数")

    max_time = app_config.MAX_TIME
    max_renew_times = app_config.MAX_RENEW_TIMES
    containers = _list_compose_project_containers(compose_project_id)

    manager = get_container_manager()
    pending_counts = {}
    for container in containers:
        manager.add_container(container.id, container)
        current_count = manager.get_renew_count(container.id)
        if current_count + 1 > max_renew_times:
            raise MaxRenewTimesExceededError(container.id, current_count, max_renew_times)
        pending_counts[container.id] = current_count + 1

    results = []
    for container in containers:
        manager.renew(container.id, max_time, max_renew_times)
        results.append(
            {
                "container_id": container.id,
                "renew_count": pending_counts[container.id],
            }
        )

    return {
        "compose_project_id": compose_project_id,
        "renewed_time": max_time,
        "renew_time": datetime.now().isoformat(),
        "containers": results,
        "renewed_count": len(results),
    }


def renew_task(data: Dict[str, Any], app_config: AppConfig = None) -> Dict[str, Any]:
    """容器续期
    
    Args:
        data: 包含container_id的字典
        app_config: 应用配置对象，默认使用全局配置
        
    Returns:
        Dict[str, Any]: 包含容器续期信息的字典
        
    Raises:
        ValidationError: 缺少container_id时抛出
        ContainerNotFoundError: 容器不存在时抛出
        MaxRenewTimesExceededError: 续期次数超过上限时抛出
    """
    if app_config is None:
        app_config = default_config
    
    container_id = data.get("container_id")
    max_time = app_config.MAX_TIME
    max_renew_times = app_config.MAX_RENEW_TIMES

    if not container_id:
        raise ValidationError("缺少 container_id 参数")

    container = _resolve_managed_container(container_id)
    if container is None:
        raise ContainerNotFoundError(container_id)

    # 调用续期方法，如果超过上限会抛出 MaxRenewTimesExceededError
    manager = get_container_manager()
    manager.renew(container_id, max_time, max_renew_times)
    
    # 获取续期计数用于返回
    current_count = manager.get_renew_count(container_id)
    
    logger.info("容器 %s 续期成功，将在 %s 秒后销毁，续期次数: %s/%s", container_id, max_time, current_count, max_renew_times)
    
    return {
        "container_id": container_id,
        "renewed_time": max_time,
        "renew_time": datetime.now().isoformat(),
        "renew_count": current_count
    }


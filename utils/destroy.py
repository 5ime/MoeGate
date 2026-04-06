"""容器销毁辅助函数"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from docker.errors import NotFound, APIError
from config import config
from utils.container_manager import get_container_manager
from utils.port_utils import release_port
from infra.docker import ensure_client

logger = logging.getLogger(__name__)

_destroy_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="moegate-destroy")
_cleanup_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="moegate-cleanup")
_destroy_task_lock = threading.Lock()
_destroy_task_state = {}
_compose_cleanup_task_state = {}

_TASK_STATE_TTL = 3600  # 已完成任务保留 1 小时
_TASK_STATE_MAX_SIZE = 5000  # 最多保留条目数


def _is_removal_in_progress_error(exc: Exception) -> bool:
    return "already in progress" in str(exc).lower()


def _gc_task_state(state_dict: dict) -> None:
    """清理已完成且超过 TTL 的任务条目（需在 _destroy_task_lock 内调用）。"""
    if len(state_dict) <= _TASK_STATE_MAX_SIZE:
        return
    now = datetime.now()
    stale_keys = []
    for key, task in state_dict.items():
        status = str(task.get("status") or "").lower()
        if status not in {"success", "failed", "not_found"}:
            continue
        finished_at = task.get("finished_at")
        if not finished_at:
            stale_keys.append(key)
            continue
        try:
            finished_time = datetime.fromisoformat(finished_at)
            if (now - finished_time).total_seconds() > _TASK_STATE_TTL:
                stale_keys.append(key)
        except (ValueError, TypeError):
            stale_keys.append(key)
    for key in stale_keys:
        state_dict.pop(key, None)


def _now_iso() -> str:
    return datetime.now().isoformat()


def submit_destroy_task(container_id: str) -> dict:
    """提交异步销毁任务。

    若同一容器已有进行中的销毁任务，则复用现有任务状态。
    """
    cid = str(container_id or "").strip()
    if not cid:
        raise ValueError("container_id 不能为空")

    with _destroy_task_lock:
        _gc_task_state(_destroy_task_state)
        existing = _destroy_task_state.get(cid)
        if existing and existing.get("status") in {"pending", "running"}:
            return dict(existing)

        task = {
            "container_id": cid,
            "status": "pending",
            "submitted_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "error": None,
        }
        _destroy_task_state[cid] = task

    def _run():
        with _destroy_task_lock:
            current = _destroy_task_state.get(cid)
            if current is not None:
                current["status"] = "running"
                current["started_at"] = _now_iso()

        try:
            destroy_container(cid)
            with _destroy_task_lock:
                current = _destroy_task_state.get(cid)
                if current is not None:
                    current["status"] = "success"
                    current["finished_at"] = _now_iso()
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.exception("后台销毁容器失败: %s", cid)
            with _destroy_task_lock:
                current = _destroy_task_state.get(cid)
                if current is not None:
                    current["status"] = "failed"
                    current["error"] = str(exc)
                    current["finished_at"] = _now_iso()

    _destroy_executor.submit(_run)

    with _destroy_task_lock:
        return dict(_destroy_task_state.get(cid) or task)


def get_destroy_task_status(container_id: str) -> dict:
    """获取异步销毁任务状态。"""
    cid = str(container_id or "").strip()
    if not cid:
        raise ValueError("container_id 不能为空")

    with _destroy_task_lock:
        task = _destroy_task_state.get(cid)
        if task:
            return dict(task)

    return {
        "container_id": cid,
        "status": "not_found",
    }


def get_compose_project_cleanup_task_status(compose_project_id: str) -> dict:
    """获取 Compose 项目后台清理任务状态。"""
    pid = str(compose_project_id or "").strip()
    if not pid:
        raise ValueError("compose_project_id 不能为空")

    with _destroy_task_lock:
        task = _compose_cleanup_task_state.get(pid)
        if task:
            return dict(task)

    return {
        "compose_project_id": pid,
        "status": "not_found",
    }


def submit_compose_project_cleanup_task(compose_project_id: str, container_ids, network_names=None) -> dict:
    """提交 Compose 项目网络清理后台任务。

    该任务会等待项目下容器销毁任务结束后，再尝试删除项目网络，
    避免 DELETE 请求同步阻塞在 Docker network.remove 上。
    """
    pid = str(compose_project_id or "").strip()
    if not pid:
        raise ValueError("compose_project_id 不能为空")

    normalized_container_ids = [str(item).strip() for item in (container_ids or []) if str(item).strip()]
    normalized_network_names = [str(item).strip() for item in (network_names or []) if str(item).strip()]

    with _destroy_task_lock:
        _gc_task_state(_compose_cleanup_task_state)
        existing = _compose_cleanup_task_state.get(pid)
        if existing and existing.get("status") in {"pending", "running"}:
            return dict(existing)

        task = {
            "compose_project_id": pid,
            "status": "pending",
            "submitted_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "error": None,
            "container_ids": normalized_container_ids,
            "network_names": normalized_network_names,
            "removed_networks": [],
        }
        _compose_cleanup_task_state[pid] = task

    def _run():
        with _destroy_task_lock:
            current = _compose_cleanup_task_state.get(pid)
            if current is not None:
                current["status"] = "running"
                current["started_at"] = _now_iso()

        try:
            _wait_for_destroy_tasks(normalized_container_ids)
            removed_networks = _remove_compose_networks(pid, normalized_network_names)
            with _destroy_task_lock:
                current = _compose_cleanup_task_state.get(pid)
                if current is not None:
                    current["status"] = "success"
                    current["removed_networks"] = removed_networks
                    current["finished_at"] = _now_iso()
            logger.info(
                "Compose 项目 %s 清理完成，容器数: %d，移除网络数: %d",
                pid,
                len(normalized_container_ids),
                len(removed_networks),
            )
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.exception("后台清理 Compose 项目失败: %s", pid)
            with _destroy_task_lock:
                current = _compose_cleanup_task_state.get(pid)
                if current is not None:
                    current["status"] = "failed"
                    current["error"] = str(exc)
                    current["finished_at"] = _now_iso()

    _cleanup_executor.submit(_run)

    with _destroy_task_lock:
        return dict(_compose_cleanup_task_state.get(pid) or task)


def _wait_for_destroy_tasks(container_ids, timeout_seconds: int = 120, poll_interval_seconds: float = 0.5):
    """等待一组容器销毁任务进入终态。"""
    if not container_ids:
        return

    deadline = time.monotonic() + max(timeout_seconds, 1)
    pending = set(container_ids)

    while pending and time.monotonic() < deadline:
        completed = set()
        failed = {}

        for container_id in pending:
            status = get_destroy_task_status(container_id)
            state = str(status.get("status") or "").lower()

            if state == "success":
                completed.add(container_id)
            elif state == "failed":
                failed[container_id] = status.get("error") or "后台销毁失败"
            elif state == "not_found":
                completed.add(container_id)

        if failed:
            first_container_id = next(iter(failed))
            raise RuntimeError(f"容器 {first_container_id} 销毁失败: {failed[first_container_id]}")

        pending -= completed
        if pending:
            time.sleep(poll_interval_seconds)

    if pending:
        pending_list = ", ".join(sorted(pending))
        raise TimeoutError(f"等待容器销毁超时: {pending_list}")


def _remove_compose_networks(compose_project_id: str, network_names=None):
    """删除 Compose 项目网络。"""
    client = ensure_client()
    if not client:
        return []

    target_names = [str(item).strip() for item in (network_names or []) if str(item).strip()]
    removed_networks = []

    try:
        if target_names:
            networks = []
            for network_name in target_names:
                matches = client.networks.list(names=[network_name])
                if matches:
                    networks.extend(matches)
        else:
            networks = client.networks.list(
                filters={
                    "label": [
                        "moegate.managed=true",
                        f"moegate.compose_project_id={compose_project_id}",
                    ]
                }
            )

        seen_ids = set()
        for network in networks:
            network_id = getattr(network, "id", None)
            if network_id and network_id in seen_ids:
                continue
            if network_id:
                seen_ids.add(network_id)

            network_name = getattr(network, "name", None)
            try:
                network.remove()
                if network_name:
                    removed_networks.append(network_name)
            except NotFound:
                if network_name:
                    removed_networks.append(network_name)
            except Exception as network_err:
                logger.warning("删除 Compose 网络失败: %s, err=%s", network_name, network_err)
    except Exception as list_network_err:
        logger.warning("查询 Compose 网络失败: %s", list_network_err)

    return removed_networks


def destroy_container(container_id: str):
    """销毁指定容器并清理相关资源。"""
    log_func = logger.debug
    log_func("正在销毁容器 %s...", container_id)
    container_name = None
    compose_project_id = None
    manager = get_container_manager()
    container = None
    had_error = False

    try:
        container = manager.remove_container(container_id)

        if container is None:
            client = ensure_client()
            if client:
                try:
                    container = client.containers.get(container_id)
                    labels = container.attrs.get('Config', {}).get('Labels') or {}
                    if labels.get('moegate.managed') != 'true':
                        logger.warning("容器 %s 非本系统管理，拒绝销毁", container_id)
                        container = None
                except NotFound:
                    container = None

        if container:
            try:
                container_name = container.name
            except Exception:
                pass

            try:
                labels = container.attrs.get('Config', {}).get('Labels') or {}
                compose_project_id = labels.get('moegate.compose_project_id') or None
            except Exception:
                compose_project_id = None

            if config.ENABLE_FRP and container_name:
                try:
                    from services.frp import delete_proxy_config
                    ok, msg = delete_proxy_config(container_name)
                    if ok:
                        log_func("已删除容器 %s 的FRP代理配置", container_name)
                    else:
                        logger.debug("删除容器 %s 的FRP代理配置失败: %s", container_name, msg)
                except Exception as e:
                    logger.debug("删除FRP代理配置时发生错误: %s", e)

            try:
                container.stop(timeout=10)
            except NotFound:
                log_func("容器 %s 已不存在，跳过停止操作", container_id)
            except APIError as e:
                logger.warning("停止容器时发生 API 错误: %s", e)

            try:
                container.remove(force=True)
                log_func("容器 %s 已被删除", container_id)
            except NotFound:
                log_func("容器 %s 已不存在，无需删除", container_id)
            except APIError as e:
                if _is_removal_in_progress_error(e):
                    logger.debug("容器 %s 正在被删除，跳过重复 remove", container_id)
                else:
                    logger.warning("删除容器时发生 API 错误: %s", e)

            try:
                if hasattr(container, 'attrs'):
                    ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
                    for port_str, mappings in ports.items():
                        if mappings:
                            for mapping in mappings:
                                if isinstance(mapping, dict):
                                    host_port = mapping.get("HostPort")
                                    if host_port:
                                        try:
                                            release_port(int(host_port))
                                        except (ValueError, TypeError):
                                            pass
            except Exception as e:
                logger.debug("释放端口时发生错误: %s", e)

    except NotFound:
        log_func("容器 %s 已不存在，无需销毁", container_id)
    except APIError as e:
        had_error = True
        logger.error("销毁容器时发生 API 错误: %s", e)
    except Exception as e:
        had_error = True
        logger.error("销毁容器时发生错误: %s", e)
    finally:
        try:
            manager.cancel_timer(container_id)
            manager.remove_count(container_id)
            log_func("容器 %s 的资源已清理", container_id)
        except Exception as e:
            had_error = True
            logger.warning("清理容器资源时发生错误: %s", e)

    if not had_error and not compose_project_id:
        logger.info("容器 %s 销毁完成", container_id)

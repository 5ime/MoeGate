"""Docker客户端管理"""
import logging
import threading
import time
from typing import List, Optional, Tuple
import docker

logger = logging.getLogger(__name__)

_client = None
_client_lock = threading.RLock()
_last_ping_time = 0
_ping_interval = 30

# 被替换掉的客户端延迟关闭：并发请求可能仍持有旧引用，
# 立即 close() 会让这些请求中途报 "client is closed"。
_RETIRE_GRACE_SEC = 60.0
_retired: List[Tuple[float, docker.DockerClient]] = []


def _reap_retired(now: Optional[float] = None) -> None:
    """关闭已过宽限期的退役客户端（调用方需持有 _client_lock）。"""
    now = time.time() if now is None else now
    while _retired:
        retired_at, client = _retired[0]
        if now - retired_at < _RETIRE_GRACE_SEC:
            return
        _retired.pop(0)
        try:
            client.close()
        except Exception:
            pass


def _retire(client) -> None:
    if client is None:
        return
    _retired.append((time.time(), client))


def get_docker_client() -> Optional[docker.DockerClient]:
    client = None
    try:
        client = docker.from_env()
        client.ping()
        return client
    except docker.errors.DockerException as e:
        logger.error("Docker连接失败: %s", e)
    except Exception as e:
        logger.error("Docker初始化失败: %s", e)
    if client is not None:
        try:
            client.close()
        except Exception:
            pass
    return None


def _check_client_health(client: docker.DockerClient) -> bool:
    try:
        client.ping()
        return True
    except Exception:
        return False


def ensure_client() -> Optional[docker.DockerClient]:
    """确保Docker客户端可用（线程安全，带自动重连）。

    整个取值过程在锁内完成，避免在检查与返回之间客户端被其他线程替换。
    替换下来的客户端进入退役队列延迟关闭，不会破坏并发请求持有的引用。
    """
    global _client, _last_ping_time

    with _client_lock:
        current_time = time.time()
        _reap_retired(current_time)

        if _client is None:
            logger.info("创建新的Docker客户端...")
            _client = get_docker_client()
            if _client:
                _last_ping_time = current_time
                logger.info("Docker客户端创建成功")
            else:
                logger.error("Docker客户端创建失败")
            return _client

        if (current_time - _last_ping_time) > _ping_interval:
            if _check_client_health(_client):
                _last_ping_time = current_time
            else:
                logger.warning("Docker客户端连接失效，尝试重新连接...")
                _retire(_client)
                _client = get_docker_client()
                if _client:
                    _last_ping_time = current_time
                    logger.info("Docker客户端重连成功")
                else:
                    logger.error("Docker客户端重连失败")

        return _client


def reset_client() -> None:
    """重置Docker客户端（用于强制重连）。"""
    global _client, _last_ping_time
    with _client_lock:
        _retire(_client)
        _client = None
        _last_ping_time = 0
        logger.info("Docker客户端已重置")

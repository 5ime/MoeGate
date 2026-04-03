"""Docker客户端管理"""
import logging
import threading
import time
from typing import Optional
import docker

logger = logging.getLogger(__name__)

_client = None
_client_lock = threading.Lock()
_last_ping_time = 0
_ping_interval = 30


def get_docker_client() -> Optional[docker.DockerClient]:
    try:
        client = docker.from_env()
        client.ping()
        return client
    except docker.errors.DockerException as e:
        logger.error("Docker连接失败: %s", e)
        return None
    except Exception as e:
        logger.error("Docker初始化失败: %s", e)
        return None


def _check_client_health(client: docker.DockerClient) -> bool:
    try:
        client.ping()
        return True
    except Exception:
        return False


def ensure_client() -> Optional[docker.DockerClient]:
    """确保Docker客户端可用（线程安全，带自动重连）"""
    global _client, _last_ping_time

    with _client_lock:
        current_time = time.time()
        need_check = (current_time - _last_ping_time) > _ping_interval

        if _client is None:
            logger.info("创建新的Docker客户端...")
            _client = get_docker_client()
            if _client:
                _last_ping_time = current_time
                logger.info("Docker客户端创建成功")
            else:
                logger.error("Docker客户端创建失败")
            return _client

        if need_check:
            if not _check_client_health(_client):
                logger.warning("Docker客户端连接失效，尝试重新连接...")
                try:
                    _client.close()
                except Exception:
                    pass
                _client = get_docker_client()
                if _client:
                    _last_ping_time = current_time
                    logger.info("Docker客户端重连成功")
                else:
                    logger.error("Docker客户端重连失败")
            else:
                _last_ping_time = current_time

    return _client


def reset_client() -> None:
    """重置Docker客户端（用于强制重连）"""
    global _client, _last_ping_time
    with _client_lock:
        if _client:
            try:
                _client.close()
            except Exception:
                pass
            _client = None
            _last_ping_time = 0
            logger.info("Docker客户端已重置")

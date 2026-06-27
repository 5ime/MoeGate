"""FRP事件处理器"""
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple, Set

from config import config
from services.frp.parser import list_proxies
from services.frp.proxy_manager import add_proxy_config, add_proxy_configs_batch
from services.frp.utils import build_proxy_config, build_proxy_name
from services.frp.exceptions import FRPPortUnavailableError

logger = logging.getLogger(__name__)

FRP_CONFIG_MAX_RETRIES = 3


@dataclass
class _ProxyBuildRequest:
    proxy_name: str
    container_name: str
    container_uuid: str
    local_port: int
    user_type: Optional[str]
    compose_service: Optional[str]
    compose_project_id: Optional[str]


def _find_available_remote_port(
    preferred_port: int,
    proxy_name: str,
    min_port: int = None,
    max_port: int = None,
    *,
    reserved_remote_ports: Optional[Set[int]] = None,
) -> int:
    """查找可用的远程端口。"""
    existing_proxies = list_proxies()
    used_ports = {
        proxy.get('remotePort')
        for proxy in existing_proxies
        if proxy.get('remotePort') and proxy.get('name') != proxy_name
    }
    if reserved_remote_ports:
        used_ports.update(reserved_remote_ports)

    if preferred_port not in used_ports:
        if reserved_remote_ports is not None:
            reserved_remote_ports.add(preferred_port)
        return preferred_port

    logger.warning(
        "端口 %s 已被其他代理使用，尝试为代理 %s 查找其他可用端口",
        preferred_port,
        proxy_name,
    )

    if min_port is not None and max_port is not None:
        for port in range(min_port, max_port + 1):
            if port not in used_ports and port != preferred_port:
                logger.info("为代理 %s 选择备用端口: %s", proxy_name, port)
                if reserved_remote_ports is not None:
                    reserved_remote_ports.add(port)
                return port
        raise FRPPortUnavailableError(proxy_name, min_port, max_port)

    raise FRPPortUnavailableError(proxy_name, preferred_port, preferred_port)


def _normalize_port_items(ports: Dict[str, Any]) -> List[Tuple[str, Any]]:
    if not ports:
        return []
    return list(ports.items())


def _resolve_user_type_for_port(user_type: Optional[str], *, primary: bool) -> Optional[str]:
    """多端口时仅首个代理可保留 HTTP/域名模式，其余强制 TCP。"""
    if primary or not user_type:
        return user_type
    normalized = str(user_type).strip().lower()
    if normalized == "http":
        return "tcp"
    return user_type


def _collect_proxy_requests(info: Dict[str, Any]) -> List[_ProxyBuildRequest]:
    """从 container.created 事件载荷收集待创建的代理请求。"""
    container_name = info.get("container_name")
    if not container_name:
        return []

    port_items = _normalize_port_items(info.get("ports") or {})
    if not port_items:
        compose_service = info.get("compose_service")
        if compose_service:
            logger.debug(
                "Compose 服务 %s/%s 无端口映射，跳过 FRP",
                info.get("compose_project_id"),
                compose_service,
            )
        else:
            logger.debug("容器 %s 无端口映射，跳过 FRP", container_name)
        return []

    user_type = info.get("type")
    container_uuid = info.get("container_uuid") or container_name
    compose_service = info.get("compose_service")
    compose_project_id = info.get("compose_project_id")
    requests: List[_ProxyBuildRequest] = []

    for index, (port_key, local_port) in enumerate(port_items):
        try:
            local_port_int = int(local_port)
        except (ValueError, TypeError):
            logger.error("容器 %s 端口 %s 无效: %s，跳过该映射", container_name, port_key, local_port)
            continue

        requests.append(
            _ProxyBuildRequest(
                proxy_name=build_proxy_name(container_name, port_key, primary=(index == 0)),
                container_name=container_name,
                container_uuid=container_uuid,
                local_port=local_port_int,
                user_type=_resolve_user_type_for_port(user_type, primary=(index == 0)),
                compose_service=compose_service,
                compose_project_id=compose_project_id,
            )
        )
    return requests


def _build_proxy_configs(
    requests: List[_ProxyBuildRequest],
    *,
    reserved_remote_ports: Optional[Set[int]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """构建代理配置列表，返回 (configs, failed_count)。"""
    min_port = config.MIN_PORT if hasattr(config, 'MIN_PORT') else None
    max_port = config.MAX_PORT if hasattr(config, 'MAX_PORT') else None
    proxy_configs: List[Dict[str, Any]] = []
    failed = 0

    for req in requests:
        try:
            remote_port = _find_available_remote_port(
                req.local_port,
                req.proxy_name,
                min_port=min_port,
                max_port=max_port,
                reserved_remote_ports=reserved_remote_ports,
            )
            proxy_config, _type_source = build_proxy_config(
                req.container_name,
                req.local_port,
                remote_port,
                req.user_type,
                req.container_uuid,
                proxy_name=req.proxy_name,
                compose_service=req.compose_service,
                compose_project_id=req.compose_project_id,
            )
            proxy_configs.append(proxy_config)
        except FRPPortUnavailableError as exc:
            failed += 1
            logger.error("%s，跳过代理 %s", exc.message, req.proxy_name)
        except Exception as exc:
            failed += 1
            logger.error("构建代理 %s 失败: %s", req.proxy_name, exc)

    return proxy_configs, failed


def create_configs_batch(infos: List[Dict[str, Any]]) -> None:
    """为多个容器批量创建 FRP 代理（Compose 多 service 场景）。"""
    valid_infos = [info for info in (infos or []) if isinstance(info, dict)]
    if not valid_infos:
        return

    all_requests: List[_ProxyBuildRequest] = []
    for info in valid_infos:
        all_requests.extend(_collect_proxy_requests(info))

    if not all_requests:
        logger.debug("批量 FRP 注册：无有效端口映射")
        return

    reserved_remote_ports: Set[int] = set()
    proxy_configs, build_failed = _build_proxy_configs(
        all_requests,
        reserved_remote_ports=reserved_remote_ports,
    )

    if not proxy_configs:
        logger.error("批量 FRP 注册失败：未能构建任何代理配置")
        return

    use_batch = len(valid_infos) > 1 or len(proxy_configs) > 1
    if use_batch:
        added, msg = add_proxy_configs_batch(proxy_configs)
        if added <= 0:
            logger.error("批量 FRP 注册失败: %s", msg)
            return
        if added < len(proxy_configs):
            logger.warning("批量 FRP 注册部分成功 (%d/%d): %s", added, len(proxy_configs), msg)
        else:
            logger.info(
                "Compose/多端口 FRP 批量注册完成: %d 个代理（%d 个容器）",
                added,
                len(valid_infos),
            )
        if build_failed:
            logger.warning("批量 FRP 注册另有 %d 个代理构建失败", build_failed)
        return

    # 单容器单代理：沿用带重试的单条写入
    _persist_single_proxy_with_retry(proxy_configs[0])


def _persist_single_proxy_with_retry(proxy_config: Dict[str, Any]) -> bool:
    import time
    from services.frp.exceptions import FRPConfigError

    proxy_name = proxy_config.get("name")
    last_error = None
    for attempt in range(1, FRP_CONFIG_MAX_RETRIES + 1):
        try:
            success, msg = add_proxy_config(proxy_config)
            if success:
                _log_proxy_success(proxy_config)
                return True
            last_error = msg
            logger.warning(
                "创建代理 %s 的 FRP 配置失败 (尝试 %s/%s): %s",
                proxy_name, attempt, FRP_CONFIG_MAX_RETRIES, msg,
            )
        except FRPConfigError as exc:
            last_error = exc.message
            logger.warning(
                "创建代理 %s 时发生 FRP 配置错误 (尝试 %s/%s): %s",
                proxy_name, attempt, FRP_CONFIG_MAX_RETRIES, exc.message,
            )
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "创建代理 %s 时发生未知错误 (尝试 %s/%s): %s",
                proxy_name, attempt, FRP_CONFIG_MAX_RETRIES, exc,
            )
        if attempt < FRP_CONFIG_MAX_RETRIES:
            time.sleep(1.0 * attempt)

    logger.error(
        "为代理 %s 创建 FRP 配置失败，已重试 %s 次。最后错误: %s",
        proxy_name, FRP_CONFIG_MAX_RETRIES, last_error,
    )
    return False


def _log_proxy_success(proxy_config: Dict[str, Any]) -> None:
    proxy_name = proxy_config.get("name")
    proxy_type = str(proxy_config.get("type") or "tcp").upper()
    local_port = proxy_config.get("localPort")
    remote_port = proxy_config.get("remotePort")
    if proxy_config.get("customDomains"):
        domain = proxy_config["customDomains"][0]
        access_url = f"http://{domain}"
        if config.FRP_VHOST_HTTP_PORT and config.FRP_VHOST_HTTP_PORT != 80:
            access_url += f":{config.FRP_VHOST_HTTP_PORT}"
        logger.info(
            "成功为代理 %s 创建 FRP 配置 (%s, 域名: %s, 访问地址: %s)",
            proxy_name, proxy_type, domain, access_url,
        )
    else:
        access_url = f"{config.FRP_SERVER_ADDR}:{remote_port}"
        logger.info(
            "成功为代理 %s 创建 FRP 配置 (%s, 端口: %s -> %s, 访问地址: %s)",
            proxy_name, proxy_type, local_port, remote_port, access_url,
        )


def handle_container_created(info: Dict[str, Any]) -> None:
    """container.created 事件处理。"""
    if not isinstance(info, dict):
        return
    create_configs_batch([info])

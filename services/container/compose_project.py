"""Compose 项目端口处理（简化编排路径）。"""
from typing import Any, Dict, List, Optional, Tuple

from config.settings import AppConfig, config as default_config
from utils.port_utils import find_available_port


def _normalize_container_port(port_text: str) -> str:
    text = str(port_text or "").strip()
    if not text:
        return text
    if "/" not in text:
        return f"{text}/tcp"
    return text


def process_service_ports(
    service: Dict[str, Any],
    app_config: AppConfig = None,
    *,
    port_mappings: Optional[List[Tuple[str, int]]] = None,
    min_port: Optional[int] = None,
    max_port: Optional[int] = None,
    containers: Optional[dict] = None,
) -> List[str]:
    """为 Compose service 生成端口映射。"""
    if app_config is None:
        app_config = default_config

    containers = containers or {}
    allowed_min = int(app_config.MIN_PORT)
    allowed_max = int(app_config.MAX_PORT)
    min_port = int(min_port if min_port is not None else allowed_min)
    max_port = int(max_port if max_port is not None else allowed_max)
    if min_port < allowed_min:
        min_port = allowed_min
    if max_port > allowed_max:
        max_port = allowed_max

    fixed_by_container: Dict[str, int] = {}
    for container_port, host_port in port_mappings or []:
        fixed_by_container[_normalize_container_port(str(container_port))] = int(host_port)
        fixed_by_container[str(container_port).split("/")[0]] = int(host_port)

    new_ports: List[str] = []
    for port in service.get("ports", []) or []:
        if isinstance(port, dict):
            container_port = str(port.get("target") or port.get("container_port") or "").strip()
            if not container_port:
                continue
            normalized = _normalize_container_port(container_port)
            if normalized in fixed_by_container or container_port in fixed_by_container:
                host_port = fixed_by_container.get(normalized) or fixed_by_container[container_port]
                new_ports.append(f"{host_port}:{container_port}")
                continue
            available = find_available_port(min_port, max_port, containers)
            if available is None:
                from core.exceptions import PortUnavailableError

                raise PortUnavailableError()
            new_ports.append(f"{available}:{container_port}")
            continue

        port_text = str(port)
        if ":" in port_text:
            _, container_port = port_text.split(":", 1)
        else:
            container_port = port_text
        normalized = _normalize_container_port(container_port)
        if normalized in fixed_by_container or container_port in fixed_by_container:
            host_port = fixed_by_container.get(normalized) or fixed_by_container[container_port]
            new_ports.append(f"{host_port}:{container_port}")
            continue

        available = find_available_port(min_port, max_port, containers)
        if available is None:
            from core.exceptions import PortUnavailableError

            raise PortUnavailableError()
        new_ports.append(f"{available}:{container_port}")

    if not new_ports and fixed_by_container:
        for container_port, host_port in port_mappings or []:
            cp = str(container_port).split("/")[0]
            new_ports.append(f"{host_port}:{cp}")

    return new_ports

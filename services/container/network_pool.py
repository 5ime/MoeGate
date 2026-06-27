"""Compose 受管网络地址池与网络创建"""
import hashlib
import ipaddress
import logging
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.types import IPAMConfig, IPAMPool

from config.settings import config as default_config, AppConfig
from core.exceptions import DockerConnectionError, NetworkProvisionError
from utils.docker_image import extract_docker_error_message

logger = logging.getLogger(__name__)

DEFAULT_COMPOSE_MANAGED_SUBNET_POOL = "172.30.0.0/16"
DEFAULT_COMPOSE_MANAGED_SUBNET_PREFIX = 24


def is_network_pool_exhausted_error(exc: Exception) -> bool:
    message = extract_docker_error_message(exc).lower()
    return (
        "all predefined address pools have been fully subnetted" in message
        or "could not find an available, non-overlapping ipv4 address pool" in message
    )


def is_network_pool_overlap_error(exc: Exception) -> bool:
    message = extract_docker_error_message(exc).lower()
    return "pool overlaps with other one on this address space" in message


def network_attrs(network) -> Dict[str, Any]:
    attrs = getattr(network, "attrs", None) or {}
    if not attrs and hasattr(network, "reload"):
        try:
            network.reload()
        except Exception:
            logger.debug(
                "刷新网络 attrs 失败: %s",
                getattr(network, "name", getattr(network, "id", "unknown")),
                exc_info=True,
            )
        attrs = getattr(network, "attrs", None) or attrs
    return attrs


def get_compose_managed_subnet_config(app_config: AppConfig = None) -> Tuple[ipaddress.IPv4Network, int]:
    effective_config = app_config or default_config
    pool_raw = getattr(effective_config, "COMPOSE_MANAGED_SUBNET_POOL", DEFAULT_COMPOSE_MANAGED_SUBNET_POOL)
    prefix_raw = getattr(effective_config, "COMPOSE_MANAGED_SUBNET_PREFIX", DEFAULT_COMPOSE_MANAGED_SUBNET_PREFIX)

    pool = ipaddress.ip_network(str(pool_raw), strict=False)
    if pool.version != 4:
        raise NetworkProvisionError("Compose 受管网络地址池目前仅支持 IPv4")

    try:
        prefix = int(prefix_raw)
    except (TypeError, ValueError) as exc:
        raise NetworkProvisionError("Compose 受管网络子网前缀配置非法") from exc

    if prefix < pool.prefixlen or prefix > 30:
        raise NetworkProvisionError("Compose 受管网络子网前缀超出允许范围")

    return pool, prefix


def build_ipam_config(subnet: Optional[str], gateway: Optional[str] = None):
    if not subnet and not gateway:
        return None
    pool = IPAMPool(subnet=subnet, gateway=gateway)
    return IPAMConfig(pool_configs=[pool])


def normalize_ipam_subnet(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return str(ipaddress.ip_network(text, strict=False))
    except ValueError as exc:
        raise NetworkProvisionError(f"Compose 网络 subnet 非法: {text}") from exc


def normalize_ipam_gateway(value: Any, subnet: Optional[str]) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        gateway = ipaddress.ip_address(text)
    except ValueError as exc:
        raise NetworkProvisionError(f"Compose 网络 gateway 非法: {text}") from exc

    if subnet:
        network = ipaddress.ip_network(subnet, strict=False)
        if gateway.version != network.version:
            raise NetworkProvisionError("Compose 网络 gateway 与 subnet 的 IP 版本不一致")
        if gateway not in network:
            raise NetworkProvisionError(f"Compose 网络 gateway 必须位于子网 {network} 内")

    return str(gateway)


def extract_compose_network_ipam(cfg: Dict[str, Any]):
    raw_ipam = cfg.get("ipam")
    if not isinstance(raw_ipam, dict):
        return None

    configs = raw_ipam.get("config") or []
    if not isinstance(configs, list):
        return None

    for item in configs:
        if not isinstance(item, dict):
            continue
        subnet = normalize_ipam_subnet(item.get("subnet"))
        gateway = normalize_ipam_gateway(item.get("gateway"), subnet)
        ipam = build_ipam_config(subnet, gateway)
        if ipam is not None:
            return ipam

    return None


def extract_network_subnets(network) -> List[ipaddress._BaseNetwork]:
    def _parse_subnets(attrs: Dict[str, Any]) -> List[ipaddress._BaseNetwork]:
        configs = ((attrs.get("IPAM") or {}).get("Config") or [])
        parsed: List[ipaddress._BaseNetwork] = []
        for item in configs:
            if not isinstance(item, dict):
                continue
            subnet = str(item.get("Subnet") or "").strip()
            if not subnet:
                continue
            try:
                parsed.append(ipaddress.ip_network(subnet, strict=False))
            except ValueError:
                logger.debug("忽略非法网络子网配置: %s", subnet)
        return parsed

    attrs = network_attrs(network)
    subnets = _parse_subnets(attrs)

    if not subnets and hasattr(network, "reload"):
        try:
            network.reload()
            attrs = getattr(network, "attrs", None) or attrs
            subnets = _parse_subnets(attrs)
        except Exception:
            logger.debug(
                "刷新网络 IPAM 信息失败: %s",
                getattr(network, "name", getattr(network, "id", "unknown")),
                exc_info=True,
            )

    return subnets


def find_available_compose_subnet(
    client,
    compose_project_id: str,
    network_key: str,
    app_config: AppConfig = None,
    excluded_subnets: Optional[set] = None,
) -> ipaddress.IPv4Network:
    managed_pool, managed_prefix = get_compose_managed_subnet_config(app_config)
    candidates = tuple(managed_pool.subnets(new_prefix=managed_prefix))
    if not candidates:
        raise NetworkProvisionError("未配置可用的 Compose 网络地址池")

    excluded = {str(item) for item in (excluded_subnets or set())}

    occupied: List[ipaddress._BaseNetwork] = []
    for network in client.networks.list():
        occupied.extend(extract_network_subnets(network))

    seed = f"{compose_project_id}:{network_key}".encode("utf-8", errors="ignore")
    start_index = int.from_bytes(hashlib.sha256(seed).digest()[:8], "big") % len(candidates)

    for offset in range(len(candidates)):
        candidate = candidates[(start_index + offset) % len(candidates)]
        if str(candidate) in excluded:
            continue
        if any(candidate.overlaps(existing) for existing in occupied):
            continue
        return candidate

    raise NetworkProvisionError(
        f"MoeGate Compose 受管网络地址池 {managed_pool} 已耗尽，请删除未使用的 Compose 项目后重试。"
    )


def build_managed_compose_network_ipam(
    client,
    compose_project_id: str,
    network_key: str,
    cfg: Dict[str, Any],
    app_config: AppConfig = None,
):
    explicit_ipam = extract_compose_network_ipam(cfg)
    if explicit_ipam is not None:
        return explicit_ipam

    driver = str(cfg.get("driver") or "bridge").strip().lower()
    if driver and driver != "bridge":
        return None

    subnet = find_available_compose_subnet(client, compose_project_id, network_key, app_config=app_config)
    gateway = str(next(subnet.hosts(), subnet.network_address))
    return build_ipam_config(str(subnet), gateway)


def prune_unused_managed_networks(client, exclude_names: Optional[List[str]] = None) -> List[str]:
    """清理未被容器占用的 MoeGate 受管网络。"""
    if client is None:
        return []

    excluded = {str(name).strip() for name in (exclude_names or []) if str(name).strip()}
    removed_networks: List[str] = []

    try:
        networks = client.networks.list(filters={"label": ["moegate.managed=true"]})
    except Exception as exc:
        logger.warning("列出受管网络失败，跳过自动清理: %s", exc)
        return removed_networks

    for network in networks:
        network_name = str(getattr(network, "name", "") or "").strip()
        if not network_name or network_name in excluded:
            continue

        try:
            attrs = network_attrs(network)
            labels = attrs.get("Labels") or {}
            if labels.get("moegate.managed") != "true":
                continue

            attached_containers = attrs.get("Containers") or {}
            if attached_containers:
                continue

            network.remove()
            removed_networks.append(network_name)
        except Exception as exc:
            logger.warning("清理受管网络失败: %s, err=%s", network_name, exc)

    return removed_networks


def create_compose_network(
    client,
    resolved_name: str,
    cfg: Dict[str, Any],
    compose_project_id: str,
    network_key: str,
    app_config: AppConfig = None,
):
    """创建 Compose 网络，支持在子网冲突时自动换段重试。"""
    driver = str(cfg.get("driver") or "bridge")
    base_create_kwargs = {
        "driver": driver,
        "attachable": bool(cfg.get("attachable", False)),
        "labels": {
            "moegate.managed": "true",
            "moegate.compose_project_id": compose_project_id,
        },
    }

    explicit_ipam = extract_compose_network_ipam(cfg)
    if explicit_ipam is not None:
        logger.warning(
            "Compose 网络检测到显式 IPAM 配置，已忽略并强制使用受管地址池: network=%s project=%s",
            resolved_name,
            compose_project_id,
        )

    if driver.strip().lower() != "bridge":
        try:
            client.networks.create(resolved_name, **base_create_kwargs)
            return
        except docker.errors.APIError as exc:
            raise NetworkProvisionError(f"创建 Compose 网络失败: {extract_docker_error_message(exc)}")

    overlap_candidates: set = set()
    prune_attempted = False
    while True:
        subnet = find_available_compose_subnet(
            client,
            compose_project_id,
            network_key,
            app_config=app_config,
            excluded_subnets=overlap_candidates,
        )
        gateway = str(next(subnet.hosts(), subnet.network_address))

        create_kwargs = dict(base_create_kwargs)
        create_kwargs["ipam"] = build_ipam_config(str(subnet), gateway)

        try:
            client.networks.create(resolved_name, **create_kwargs)
            return
        except docker.errors.APIError as exc:
            if is_network_pool_overlap_error(exc):
                overlap_candidates.add(str(subnet))
                logger.warning(
                    "Compose 网络子网冲突，自动切换下一个子网重试: network=%s subnet=%s",
                    resolved_name,
                    subnet,
                )
                continue

            if is_network_pool_exhausted_error(exc):
                if prune_attempted:
                    raise NetworkProvisionError(
                        "Docker 网络地址池已耗尽，已尝试清理未使用的 MoeGate 网络但仍无法分配子网。"
                        "请删除未使用的 Compose 项目，或执行 docker network prune 后重试。"
                    )

                removed_networks = prune_unused_managed_networks(client, exclude_names=[resolved_name])
                prune_attempted = True
                if removed_networks:
                    logger.warning(
                        "Docker 网络地址池耗尽，已清理 %d 个未使用的 MoeGate 网络后重试: %s",
                        len(removed_networks),
                        ", ".join(removed_networks),
                    )
                    continue
                raise NetworkProvisionError(
                    "Docker 网络地址池已耗尽，无法为 Compose 项目创建网络。"
                    "请删除未使用的 Compose 项目，或执行 docker network prune 后重试。"
                )

            raise NetworkProvisionError(f"创建 Compose 网络失败: {extract_docker_error_message(exc)}")


def ensure_compose_networks(
    client,
    compose_content: Dict[str, Any],
    compose_project_id: str,
    app_config: AppConfig = None,
) -> Tuple[Dict[str, str], List[str]]:
    """确保 compose 中定义的网络存在，并返回逻辑名到实际 Docker 网络名的映射。"""
    if client is None:
        raise DockerConnectionError("Docker客户端不可用")

    networks = compose_content.get("networks") or {}
    if not isinstance(networks, dict):
        return {}, []

    mapping: Dict[str, str] = {}
    created_networks: List[str] = []
    for network_key, network_cfg in networks.items():
        cfg = network_cfg if isinstance(network_cfg, dict) else {}
        external_cfg = cfg.get("external")

        if external_cfg:
            if isinstance(external_cfg, dict):
                resolved_name = external_cfg.get("name") or cfg.get("name") or str(network_key)
            else:
                resolved_name = cfg.get("name") or str(network_key)
            mapping[str(network_key)] = str(resolved_name)
            continue

        resolved_name = str(cfg.get("name") or f"{compose_project_id}_{network_key}")
        mapping[str(network_key)] = resolved_name

        existing = client.networks.list(names=[resolved_name])
        if existing:
            continue

        create_compose_network(client, resolved_name, cfg, compose_project_id, str(network_key), app_config=app_config)
        created_networks.append(resolved_name)

    return mapping, created_networks

"""受管网络服务。"""
import ipaddress
import logging
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.types import IPAMConfig, IPAMPool

from core.exceptions import ContainerNotFoundError, ValidationError
from infra.docker import ensure_client

logger = logging.getLogger(__name__)

MANAGED_NETWORK_LABEL = "moegate.managed"
MANAGED_NETWORK_LABEL_VALUE = "true"
COMPOSE_PROJECT_LABEL = "moegate.compose_project_id"


def _normalize_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValidationError(f"字段 {field_name} 必须为布尔值")


def _normalize_optional_str(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"字段 {field_name} 必须为字符串")
    text = value.strip()
    return text or None


def _normalize_labels(raw_labels: Any) -> Dict[str, str]:
    if raw_labels is None:
        return {}
    if not isinstance(raw_labels, dict):
        raise ValidationError("字段 labels 必须为对象")

    labels: Dict[str, str] = {}
    for key, value in raw_labels.items():
        key_text = _normalize_optional_str(key, "labels 键")
        if not key_text:
            raise ValidationError("labels 键不能为空")
        if value is None:
            labels[key_text] = ""
            continue
        labels[key_text] = str(value)
    return labels


def _normalize_subnet(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise ValidationError("字段 subnet 必须是合法的 CIDR 网段，例如 172.33.0.0/24")
    return str(network)


def _normalize_gateway(value: Optional[str], subnet: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        gateway = ipaddress.ip_address(value)
    except ValueError:
        raise ValidationError("字段 gateway 必须是合法的 IP 地址")

    if subnet:
        network = ipaddress.ip_network(subnet, strict=False)
        if gateway.version != network.version:
            raise ValidationError("字段 gateway 与 subnet 的 IP 版本不一致")
        if gateway not in network:
            raise ValidationError(f"字段 gateway 必须位于子网 {network} 内")
        if gateway == network.network_address:
            raise ValidationError(f"字段 gateway 不能使用网络地址 {gateway}")
        if network.num_addresses > 1 and gateway == network.broadcast_address:
            raise ValidationError(f"字段 gateway 不能使用广播地址 {gateway}")

    return str(gateway)


def _network_attrs(network) -> Dict[str, Any]:
    attrs = getattr(network, "attrs", None) or {}
    if (not attrs or "Containers" not in attrs) and hasattr(network, "reload"):
        try:
            network.reload()
        except Exception:
            logger.debug("刷新网络 attrs 失败: %s", getattr(network, "id", getattr(network, "name", "unknown")), exc_info=True)
        attrs = getattr(network, "attrs", None) or attrs
    return attrs


def _attached_container_ids(attrs: Dict[str, Any]) -> List[str]:
    containers = attrs.get("Containers") or {}
    if isinstance(containers, dict):
        return [str(container_id) for container_id in containers.keys() if container_id]
    return []


def _build_ipam_config(subnet: Optional[str], gateway: Optional[str]):
    if not subnet and not gateway:
        return None
    pool = IPAMPool(subnet=subnet, gateway=gateway)
    return IPAMConfig(pool_configs=[pool])


def _build_network_summary(network) -> Dict[str, Any]:
    attrs = _network_attrs(network)
    labels = attrs.get("Labels") or {}
    ipam_cfg = ((attrs.get("IPAM") or {}).get("Config") or [{}])[0] or {}
    attached_ids = _attached_container_ids(attrs)
    options = attrs.get("Options") or {}

    return {
        "id": str(attrs.get("Id") or getattr(network, "id", "") or ""),
        "name": str(getattr(network, "name", "") or attrs.get("Name") or ""),
        "driver": str(attrs.get("Driver") or ""),
        "scope": str(attrs.get("Scope") or ""),
        "created": attrs.get("Created"),
        "internal": bool(attrs.get("Internal", False)),
        "attachable": bool(attrs.get("Attachable", False)),
        "enable_ipv6": bool(attrs.get("EnableIPv6", False)),
        "subnet": ipam_cfg.get("Subnet"),
        "gateway": ipam_cfg.get("Gateway"),
        "labels": labels,
        "options": options,
        "compose_project_id": labels.get(COMPOSE_PROJECT_LABEL),
        "attached_container_ids": attached_ids,
        "attached_container_count": len(attached_ids),
        "is_in_use": len(attached_ids) > 0,
    }


def _get_managed_network(identifier: str):
    client = ensure_client()
    if not client:
        raise ContainerNotFoundError(identifier)

    try:
        network = client.networks.get(identifier)
        labels = _network_attrs(network).get("Labels") or {}
        if labels.get(MANAGED_NETWORK_LABEL) == MANAGED_NETWORK_LABEL_VALUE:
            return network
    except docker.errors.NotFound:
        network = None
    except Exception:
        network = None

    matches = client.networks.list(names=[identifier])
    for network in matches:
        labels = _network_attrs(network).get("Labels") or {}
        if labels.get(MANAGED_NETWORK_LABEL) == MANAGED_NETWORK_LABEL_VALUE:
            return network

    raise ContainerNotFoundError(identifier)


def _validate_create_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    name = _normalize_optional_str(data.get("name"), "name")
    if not name:
        raise ValidationError("字段 name 不能为空")

    driver = _normalize_optional_str(data.get("driver"), "driver") or "bridge"
    internal = _normalize_bool(data.get("internal", False), "internal")
    attachable = _normalize_bool(data.get("attachable", False), "attachable")
    enable_ipv6 = _normalize_bool(data.get("enable_ipv6", False), "enable_ipv6")
    subnet = _normalize_subnet(_normalize_optional_str(data.get("subnet"), "subnet"))
    gateway = _normalize_gateway(_normalize_optional_str(data.get("gateway"), "gateway"), subnet)
    compose_project_id = _normalize_optional_str(data.get("compose_project_id"), "compose_project_id")
    labels = _normalize_labels(data.get("labels"))

    return {
        "name": name,
        "driver": driver,
        "internal": internal,
        "attachable": attachable,
        "enable_ipv6": enable_ipv6,
        "subnet": subnet,
        "gateway": gateway,
        "compose_project_id": compose_project_id,
        "labels": labels,
    }


def _build_create_kwargs(payload: Dict[str, Any]) -> Dict[str, Any]:
    labels = dict(payload.get("labels") or {})
    labels[MANAGED_NETWORK_LABEL] = MANAGED_NETWORK_LABEL_VALUE
    if payload.get("compose_project_id"):
        labels[COMPOSE_PROJECT_LABEL] = payload["compose_project_id"]

    create_kwargs = {
        "driver": payload["driver"],
        "internal": payload["internal"],
        "attachable": payload["attachable"],
        "enable_ipv6": payload["enable_ipv6"],
        "labels": labels,
    }
    ipam = _build_ipam_config(payload.get("subnet"), payload.get("gateway"))
    if ipam is not None:
        create_kwargs["ipam"] = ipam
    return create_kwargs


def list_managed_networks() -> Dict[str, Any]:
    client = ensure_client()
    if not client:
        return {"networks": [], "total": 0}

    networks = client.networks.list(filters={"label": [f"{MANAGED_NETWORK_LABEL}={MANAGED_NETWORK_LABEL_VALUE}"]})
    items = sorted((_build_network_summary(network) for network in networks), key=lambda item: item["name"])
    return {
        "networks": items,
        "total": len(items),
        "in_use": sum(1 for item in items if item["is_in_use"]),
        "idle": sum(1 for item in items if not item["is_in_use"]),
    }


def get_managed_network_detail(network_id: str) -> Dict[str, Any]:
    network = _get_managed_network(network_id)
    detail = _build_network_summary(network)
    detail["attrs"] = _network_attrs(network)
    return detail


def create_managed_network(data: Dict[str, Any]) -> Dict[str, Any]:
    payload = _validate_create_payload(data)
    client = ensure_client()
    if not client:
        raise ValidationError("Docker 客户端不可用")

    if client.networks.list(names=[payload["name"]]):
        raise ValidationError(f"网络已存在: {payload['name']}")

    try:
        network = client.networks.create(payload["name"], **_build_create_kwargs(payload))
    except docker.errors.APIError as exc:
        raise ValidationError(f"创建网络失败: {getattr(exc, 'explanation', exc)}")

    return _build_network_summary(network)


def update_managed_network(network_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    network = _get_managed_network(network_id)
    current = _build_network_summary(network)
    if current["is_in_use"]:
        raise ValidationError("当前网络正在被容器占用，无法修改；请先断开或删除相关容器")

    payload = _validate_create_payload({
        "name": data.get("name", current["name"]),
        "driver": data.get("driver", current["driver"]),
        "internal": data.get("internal", current["internal"]),
        "attachable": data.get("attachable", current["attachable"]),
        "enable_ipv6": data.get("enable_ipv6", current["enable_ipv6"]),
        "subnet": data.get("subnet", current.get("subnet")),
        "gateway": data.get("gateway", current.get("gateway")),
        "compose_project_id": data.get("compose_project_id", current.get("compose_project_id")),
        "labels": data.get("labels", current.get("labels") or {}),
    })

    target_name = payload["name"]
    if target_name != current["name"] and ensure_client().networks.list(names=[target_name]):
        raise ValidationError(f"目标网络名已存在: {target_name}")

    client = ensure_client()
    try:
        network.remove()
        recreated = client.networks.create(target_name, **_build_create_kwargs(payload))
    except docker.errors.APIError as exc:
        raise ValidationError(f"更新网络失败: {getattr(exc, 'explanation', exc)}")

    summary = _build_network_summary(recreated)
    summary["updated_from"] = current["name"]
    return summary


def delete_managed_network(network_id: str) -> Dict[str, Any]:
    network = _get_managed_network(network_id)
    summary = _build_network_summary(network)
    if summary["is_in_use"]:
        raise ValidationError("当前网络正在被容器占用，无法删除")

    try:
        network.remove()
    except docker.errors.APIError as exc:
        raise ValidationError(f"删除网络失败: {getattr(exc, 'explanation', exc)}")

    return {
        "id": summary["id"],
        "name": summary["name"],
        "deleted": True,
    }

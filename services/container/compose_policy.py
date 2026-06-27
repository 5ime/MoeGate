"""Compose 启动前策略校验（可选 strict 模式）。"""
from typing import Any, Dict, List, Optional, Tuple

from config import config

_BLOCKED_HOST_MODES = frozenset({"host"})
_BLOCKED_IPC = frozenset({"host"})
_BLOCKED_PID = frozenset({"host"})
_BLOCKED_VOLUME_PREFIXES = (
    "/var/run/docker.sock",
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/root",
    "/boot",
)
_DANGEROUS_CAPS = frozenset({
    "SYS_ADMIN",
    "SYS_PTRACE",
    "NET_ADMIN",
    "DAC_READ_SEARCH",
    "SYS_MODULE",
    "SYS_RAWIO",
})

# 永久不通过 SDK 实现的字段（与受控网络 / 随机端口模型冲突或未实现）
_UNSUPPORTED_COMPOSE_FIELDS = (
    "network_mode",
    "healthcheck",
    "deploy",
    "ipc",
    "pid",
)


def compose_policy_mode() -> str:
    return str(getattr(config, "COMPOSE_POLICY", "ctf") or "ctf").strip().lower()


def compose_policy_strict() -> bool:
    return compose_policy_mode() == "strict"


def compose_unsupported_mode() -> str:
    return str(getattr(config, "COMPOSE_UNSUPPORTED", "warn") or "warn").strip().lower()


def compose_unsupported_error() -> bool:
    return compose_unsupported_mode() == "error"


def _normalize_volume_target(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if ":" in text:
        text = text.split(":", 1)[0].strip()
    return text.rstrip("/")


def _collect_service_volumes(service: Dict[str, Any]) -> List[str]:
    volumes: List[str] = []
    for item in service.get("volumes") or []:
        if isinstance(item, str):
            volumes.append(item)
        elif isinstance(item, dict):
            source = item.get("source")
            if source:
                volumes.append(str(source))
    return volumes


def blocked_volume_reason(volume_spec: str) -> Optional[str]:
    target = _normalize_volume_target(volume_spec)
    if not target:
        return None
    lowered = target.lower()
    if lowered == "/":
        return "禁止挂载宿主机根目录 /"
    for prefix in _BLOCKED_VOLUME_PREFIXES:
        if lowered == prefix.rstrip("/") or lowered.startswith(prefix.rstrip("/") + "/"):
            return f"禁止挂载敏感路径: {prefix}"
    if "docker.sock" in lowered:
        return "禁止挂载 Docker Socket"
    return None


def collect_unsupported_compose_fields(services: Dict[str, Any]) -> List[str]:
    """收集 YAML 中存在但 MoeGate SDK 编排不会执行的字段。"""
    warnings: List[str] = []
    if not isinstance(services, dict):
        return warnings
    for service_name, service in services.items():
        if not isinstance(service, dict):
            continue
        for field_name in _UNSUPPORTED_COMPOSE_FIELDS:
            value = service.get(field_name)
            if value is None:
                continue
            if isinstance(value, (list, dict, tuple, set)) and not value:
                continue
            if field_name == "network_mode":
                mode = str(value or "").strip().lower()
                if mode not in _BLOCKED_HOST_MODES:
                    continue
            warnings.append(
                f"服务 {service_name}: {field_name} 不受 MoeGate SDK 编排支持"
            )
    return warnings


def validate_compose_policy(services: Dict[str, Any]) -> Optional[str]:
    """strict 模式下校验 Compose services；通过返回 None，否则返回错误说明。"""
    if not compose_policy_strict():
        return None
    if not isinstance(services, dict):
        return "Compose services 格式无效"

    for service_name, service in services.items():
        if not isinstance(service, dict):
            continue
        if service.get("privileged") is True:
            return f"服务 {service_name}: strict 模式禁止 privileged=true"

        network_mode = str(service.get("network_mode") or "").strip().lower()
        if network_mode in _BLOCKED_HOST_MODES:
            return f"服务 {service_name}: strict 模式禁止 network_mode=host"

        ipc_mode = str(service.get("ipc") or "").strip().lower()
        if ipc_mode in _BLOCKED_IPC:
            return f"服务 {service_name}: strict 模式禁止 ipc=host"

        pid_mode = str(service.get("pid") or "").strip().lower()
        if pid_mode in _BLOCKED_PID:
            return f"服务 {service_name}: strict 模式禁止 pid=host"

        cap_add = service.get("cap_add") or []
        if isinstance(cap_add, (list, tuple, set)):
            for cap in cap_add:
                cap_name = str(cap or "").strip().upper()
                if cap_name in _DANGEROUS_CAPS:
                    return f"服务 {service_name}: strict 模式禁止 cap_add={cap_name}"

        for volume_spec in _collect_service_volumes(service):
            reason = blocked_volume_reason(volume_spec)
            if reason:
                return f"服务 {service_name}: {reason}"

    return None


def prepare_compose_services_policy(
    services: Dict[str, Any],
) -> Tuple[List[str], Optional[str]]:
    """执行 strict 策略与 unsupported 字段检查，返回 (warnings, error)。"""
    policy_error = validate_compose_policy(services)
    if policy_error:
        return [], policy_error

    warnings = collect_unsupported_compose_fields(services)
    if warnings and compose_unsupported_error():
        return warnings, "; ".join(warnings)
    return warnings, None


def _extract_depends_on(service: Dict[str, Any]) -> List[str]:
    raw = service.get("depends_on")
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [str(name) for name in raw.keys() if name]
    if isinstance(raw, (list, tuple, set)):
        return [str(name) for name in raw if name]
    return []


def order_compose_services(services: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """按 depends_on 拓扑排序 service；仅决定启动顺序，不等待 healthcheck。"""
    if not isinstance(services, dict):
        raise ValueError("Compose services 格式无效")

    deps: Dict[str, List[str]] = {}
    for name, service in services.items():
        dep_names = _extract_depends_on(service if isinstance(service, dict) else {})
        deps[name] = [dep for dep in dep_names if dep in services]

    ordered: List[Tuple[str, Dict[str, Any]]] = []
    visited: set = set()
    visiting: set = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"Compose depends_on 存在循环依赖: {name}")
        visiting.add(name)
        for dep in deps.get(name, []):
            visit(dep)
        visiting.remove(name)
        visited.add(name)
        service = services.get(name)
        if isinstance(service, dict):
            ordered.append((name, service))

    for name in services:
        if name not in visited:
            visit(name)

    return ordered

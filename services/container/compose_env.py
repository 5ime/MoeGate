"""Compose 环境变量解析与 ${VAR} 替换。"""
import re
import uuid
from typing import Any, Dict, Optional, Set

from core.exceptions import ValidationError


_COMPOSE_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def parse_service_environment(service_env: Any) -> Dict[str, str]:
    """将 compose service.environment 规范化为字符串字典。"""
    if isinstance(service_env, list):
        merged_env: Dict[str, str] = {}
        for item in service_env:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                merged_env[key] = value
        return merged_env
    if isinstance(service_env, dict):
        return {str(key): "" if value is None else str(value) for key, value in service_env.items()}
    return {}


def substitute_compose_vars(value: str, context: Dict[str, str]) -> str:
    """替换 compose 中的 ${VAR} 占位符。"""

    def replacer(match: re.Match) -> str:
        var_name = match.group(1).strip()
        if var_name in context:
            return context[var_name]
        return match.group(0)

    return _COMPOSE_VAR_PATTERN.sub(replacer, value)


def substitute_compose_value(value: Any, context: Dict[str, str]) -> Any:
    """递归替换字符串或 command 列表中的 ${VAR} 占位符。"""
    if isinstance(value, str):
        return substitute_compose_vars(value, context)
    if isinstance(value, list):
        return [substitute_compose_value(item, context) for item in value]
    return value


def collect_compose_var_references(value: Any) -> Set[str]:
    """收集字符串或 command 列表中的 ${VAR} 占位符名称。"""
    refs: Set[str] = set()
    if isinstance(value, str):
        for match in _COMPOSE_VAR_PATTERN.finditer(value):
            name = match.group(1).strip()
            if name:
                refs.add(name)
    elif isinstance(value, list):
        for item in value:
            refs.update(collect_compose_var_references(item))
    return refs


def collect_service_var_references(service: Dict[str, Any]) -> Set[str]:
    """收集 compose service 在 environment / command 中引用的 ${VAR} 名称。"""
    refs: Set[str] = set()
    compose_env = parse_service_environment(service.get("environment"))
    for value in compose_env.values():
        refs.update(collect_compose_var_references(value))
    refs.update(collect_compose_var_references(service.get("command")))
    return refs


def generate_service_flag() -> str:
    """为 compose service 生成唯一 FLAG。"""
    return f"flag{{{uuid.uuid4()}}}"


def resolve_compose_service_env(
    service: Dict[str, Any],
    global_env: Optional[Dict[str, Any]] = None,
    multi_service: bool = False,
) -> Dict[str, str]:
    """合并 compose / 全局环境变量，并解析 ${VAR}。"""
    merged_env = parse_service_environment(service.get("environment"))
    referenced_vars = collect_service_var_references(service)

    filtered_global = dict(global_env or {})
    if multi_service and "FLAG" in filtered_global and "FLAG" in referenced_vars:
        filtered_global.pop("FLAG", None)
    if filtered_global:
        merged_env.update({str(key): "" if value is None else str(value) for key, value in filtered_global.items()})

    for var_name in referenced_vars:
        current = merged_env.get(var_name, "")
        if var_name == "FLAG" and (not current or f"${{{var_name}}}" in current):
            merged_env[var_name] = generate_service_flag()

    context = {str(key): str(value) for key, value in merged_env.items()}
    for _ in range(10):
        changed = False
        resolved: Dict[str, str] = {}
        for key, value in context.items():
            new_value = substitute_compose_vars(value, context)
            resolved[key] = new_value
            if new_value != value:
                changed = True
        context = resolved
        if not changed:
            break
    return context


def apply_compose_service_env(
    service: Dict[str, Any],
    global_env: Optional[Dict[str, Any]] = None,
    multi_service: bool = False,
    service_name: Optional[str] = None,
) -> None:
    """为 compose service 注入环境变量，并替换 command 中的 ${VAR}。"""
    resolved_env = resolve_compose_service_env(
        service=service,
        global_env=global_env,
        multi_service=multi_service,
    )
    if service_name is not None:
        for key, value in resolved_env.items():
            if "${" in str(value):
                raise ValidationError(
                    f"Compose 服务 {service_name} 的环境变量 {key} 未能解析: {value}"
                )
    service["environment"] = resolved_env
    if "command" in service:
        service["command"] = substitute_compose_value(service.get("command"), resolved_env)

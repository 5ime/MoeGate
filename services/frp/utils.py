"""FRP工具函数"""
import ipaddress
import re
import logging
from typing import Optional, Tuple, Dict, Any
from config import config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)

PROXY_PORT_SUFFIX = "-p-"
_PROXY_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
_PROXY_TYPES = frozenset({"tcp", "http"})
_DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


def escape_toml_string(value: str) -> str:
    """转义 TOML 双引号字符串中的特殊字符，防止配置注入。"""
    text = str(value or "")
    return text.replace("\\", "\\\\").replace('"', '\\"')


def validate_proxy_name(name: str) -> str:
    text = str(name or "").strip()
    if not text or not _PROXY_NAME_RE.match(text):
        raise FRPConfigError("代理名称仅允许字母、数字、点、下划线与连字符", 400)
    return text


def validate_proxy_type(proxy_type: Optional[str]) -> str:
    normalized = str(proxy_type or "tcp").lower().strip()
    if normalized not in _PROXY_TYPES:
        raise FRPConfigError("代理类型必须为 tcp 或 http", 400)
    return normalized


_DOCKER_HOST_ALIASES = frozenset({"host.docker.internal", "host.containers.internal"})


def validate_proxy_local_ip(local_ip: Optional[str]) -> str:
    """手动代理 localIP 允许环回地址；Docker 部署时可使用 host.docker.internal。"""
    text = str(local_ip or "127.0.0.1").strip()
    if text.lower() == "localhost":
        return "127.0.0.1"
    if text.lower() in _DOCKER_HOST_ALIASES:
        return text.lower()
    try:
        addr = ipaddress.ip_address(text)
    except ValueError as exc:
        raise FRPConfigError("localIP 必须是合法的 IP 地址", 400) from exc
    if not addr.is_loopback:
        raise FRPConfigError("localIP 仅允许环回地址（127.0.0.1 或 ::1）", 400)
    return text


def validate_proxy_domain(domain: str) -> str:
    text = str(domain or "").strip().lower().rstrip(".")
    if not text or len(text) > 253 or not _DOMAIN_RE.match(text):
        raise FRPConfigError("customDomains 包含无效域名", 400)
    return text


def normalize_proxy_config(proxy_config: Dict[str, Any]) -> Dict[str, Any]:
    """校验并规范化手动提交的代理配置。"""
    if not isinstance(proxy_config, dict):
        raise FRPConfigError("代理配置必须为对象", 400)

    normalized = dict(proxy_config)
    normalized["name"] = validate_proxy_name(normalized.get("name"))
    normalized["type"] = validate_proxy_type(normalized.get("type"))
    normalized["localIP"] = validate_proxy_local_ip(normalized.get("localIP"))

    try:
        local_port = int(normalized.get("localPort"))
    except (TypeError, ValueError) as exc:
        raise FRPConfigError("localPort 必须为整数", 400) from exc
    if local_port <= 0 or local_port > 65535:
        raise FRPConfigError("localPort 必须在 1-65535 之间", 400)
    normalized["localPort"] = local_port

    if "remotePort" in normalized and normalized["remotePort"] is not None:
        try:
            remote_port = int(normalized["remotePort"])
        except (TypeError, ValueError) as exc:
            raise FRPConfigError("remotePort 必须为整数", 400) from exc
        if remote_port <= 0 or remote_port > 65535:
            raise FRPConfigError("remotePort 必须在 1-65535 之间", 400)
        normalized["remotePort"] = remote_port

    domains = normalized.get("customDomains") or []
    if domains and not isinstance(domains, list):
        raise FRPConfigError("customDomains 必须为字符串数组", 400)
    normalized["customDomains"] = [validate_proxy_domain(item) for item in domains]

    return normalized


def build_proxy_name(container_name: str, port_key: str, *, primary: bool) -> str:
    """生成 FRP 代理名称。首个端口沿用容器名，其余端口追加后缀。"""
    if primary:
        return container_name
    safe_key = re.sub(r"[^a-zA-Z0-9._-]", "-", str(port_key or "").strip()) or "port"
    return f"{container_name}{PROXY_PORT_SUFFIX}{safe_key}"


def proxy_belongs_to_container(proxy_name: Optional[str], container_name: str) -> bool:
    """判断代理是否属于指定容器（含多端口附加代理）。"""
    if not proxy_name or not container_name:
        return False
    if proxy_name == container_name:
        return True
    return proxy_name.startswith(f"{container_name}{PROXY_PORT_SUFFIX}")


def proxy_config_to_api(
    proxy_config: Dict[str, Any],
    *,
    compose_service: Optional[str] = None,
    compose_project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """将解析后的代理配置转为 API 响应字段。"""
    entry = {
        "name": proxy_config.get("name"),
        "type": proxy_config.get("type"),
        "remotePort": proxy_config.get("remotePort"),
        "localPort": proxy_config.get("localPort"),
        "localIP": proxy_config.get("localIP"),
        "customDomains": proxy_config.get("customDomains", []),
    }
    if compose_service:
        entry["compose_service"] = compose_service
    if compose_project_id:
        entry["compose_project_id"] = compose_project_id
    return entry


def _sanitize_dns_label(value: str, *, max_len: int = 32) -> str:
    label = re.sub(r"[^a-zA-Z0-9-]", "-", str(value or "").strip().lower())
    label = re.sub(r"-+", "-", label).strip("-")
    return (label or "svc")[:max_len]


def generate_domain(
    container_name: str,
    container_uuid: Optional[str] = None,
    *,
    compose_service: Optional[str] = None,
    compose_project_id: Optional[str] = None,
) -> str:
    """生成 FRP HTTP 代理域名。

    Compose 多 service 时使用 ``{service}-{project_tag}``，便于区分 web/db 等服务。
    """
    domain_suffix = (config.FRP_DOMAIN_SUFFIX or "").lstrip(".")
    if compose_service and compose_project_id:
        service_label = _sanitize_dns_label(compose_service)
        project_tag = re.sub(r"[^a-zA-Z0-9]", "", str(compose_project_id))[:8] or "proj"
        subdomain = f"{service_label}-{project_tag}"
    elif container_uuid:
        subdomain = str(container_uuid)
    else:
        subdomain = container_name
    return f"{subdomain}.{domain_suffix}"


def generate_proxy_section(proxy_config: Dict[str, Any]) -> str:
    """生成代理配置段（TOML格式）
    
    Args:
        proxy_config: 代理配置字典
        
    Returns:
        str: TOML格式的代理配置段
        
    Raises:
        FRPConfigError: 配置缺少必要字段时抛出
    """
    normalized = normalize_proxy_config(proxy_config)
    name = normalized["name"]
    proxy_type = normalized["type"]
    local_ip = normalized["localIP"]
    local_port = normalized["localPort"]
    custom_domains = normalized.get("customDomains", [])

    if proxy_type == "http" and not custom_domains:
        logger.warning("HTTP类型代理 '%s' 缺少域名配置，自动转换为TCP类型", name)
        proxy_type = "tcp"
        normalized["type"] = "tcp"

    section = (
        f'[[proxies]]\n'
        f'name = "{escape_toml_string(name)}"\n'
        f'type = "{proxy_type}"\n'
        f'localIP = "{escape_toml_string(local_ip)}"\n'
        f'localPort = {local_port}\n'
    )

    if proxy_type == "http":
        if custom_domains:
            domains_str = ", ".join([f'"{escape_toml_string(d)}"' for d in custom_domains])
            section += f"customDomains = [{domains_str}]\n"
            if "remotePort" in normalized:
                section += f'remotePort = {normalized["remotePort"]}\n'
    else:
        remote_port = normalized.get("remotePort")
        if remote_port:
            section += f"remotePort = {remote_port}\n"

    section += "\n"
    return section


def validate_and_fix_config(config_content: str) -> str:
    """验证并修复配置中的无效HTTP代理。"""
    from services.frp.config_document import (
        load_config_document,
        serialize_config_document,
        validate_and_fix_document,
    )

    data = load_config_document(config_content)
    if not data and config_content.strip():
        return config_content
    return serialize_config_document(validate_and_fix_document(data))


def get_common_config() -> str:
    """获取FRP通用配置段（TOML格式）"""
    server_addr = escape_toml_string(config.FRP_SERVER_ADDR or "")
    common_config = f'serverAddr = "{server_addr}"\nserverPort = {config.FRP_SERVER_PORT}\n'

    auth_token = getattr(config, 'FRP_AUTH_TOKEN', None)
    if auth_token:
        common_config += (
            f'\n[auth]\nmethod = "token"\n'
            f'token = "{escape_toml_string(auth_token)}"\n'
        )

    admin_ip = escape_toml_string(config.FRP_ADMIN_IP or "127.0.0.1")
    admin_port = config.FRP_ADMIN_PORT
    common_config += f'\n[webServer]\naddr = "{admin_ip}"\nport = {admin_port}\n'
    if config.FRP_ADMIN_USER:
        common_config += f'user = "{escape_toml_string(config.FRP_ADMIN_USER)}"\n'
    if config.FRP_ADMIN_PASSWORD:
        common_config += f'password = "{escape_toml_string(config.FRP_ADMIN_PASSWORD)}"\n'

    return common_config + '\n'


def determine_proxy_type(user_type: Optional[str], container_name: str, local_port: int) -> Tuple[bool, str]:
    """确定代理类型和来源
    
    Args:
        user_type: 用户指定的代理类型
        container_name: 容器名称
        local_port: 本地端口
        
    Returns:
        Tuple[bool, str]: (是否为HTTP类型, 类型来源说明)
    """
    if not config.FRP_USE_DOMAIN:
        return False, "TCP类型(FRP_USE_DOMAIN=false)"
    
    if user_type:
        user_type = user_type.lower().strip()
        if user_type == 'http':
            if config.FRP_DOMAIN_SUFFIX:
                return True, "用户指定(http)"
            else:
                logger.warning("用户指定HTTP类型但未配置域名后缀，已回退到TCP类型")
                return False, "用户指定(http)但回退到TCP(缺少域名后缀)"
        elif user_type == 'tcp':
            return False, "用户指定(tcp)"
        else:
            logger.warning("无效的代理类型 '%s'，默认使用TCP类型", user_type)
    
    if config.FRP_DOMAIN_SUFFIX:
        return True, "域名配置"
    
    return False, "默认(TCP)"


def build_proxy_config(
    container_name: str,
    local_port: int,
    remote_port: int,
    user_type: Optional[str] = None,
    container_uuid: Optional[str] = None,
    proxy_name: Optional[str] = None,
    compose_service: Optional[str] = None,
    compose_project_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """构建代理配置字典。"""
    proxy_config = {
        'name': proxy_name or container_name,
        'localIP': getattr(config, 'FRP_LOCAL_IP', None) or '127.0.0.1',
        'localPort': int(local_port),
    }

    is_http, type_source = determine_proxy_type(user_type, container_name, local_port)

    if is_http:
        proxy_config['type'] = 'http'
        proxy_config['customDomains'] = [
            generate_domain(
                container_name,
                container_uuid,
                compose_service=compose_service,
                compose_project_id=compose_project_id,
            )
        ]
        if not config.FRP_VHOST_HTTP_PORT:
            proxy_config['remotePort'] = remote_port
    else:
        proxy_config['type'] = 'tcp'
        proxy_config['remotePort'] = remote_port
    
    return proxy_config, type_source


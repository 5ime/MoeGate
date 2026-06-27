"""客户端IP解析"""
import ipaddress
from flask import request
from config import config


def _normalize_ip(ip_raw: str) -> str:
    if not ip_raw:
        return ""
    candidate = ip_raw.strip().strip('"')
    if not candidate:
        return ""
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return ""


def _remote_addr() -> str:
    return _normalize_ip(request.remote_addr or "")


def _is_trusted_proxy(ip_str: str) -> bool:
    if not ip_str or not config.TRUST_PROXY_HEADERS:
        return False
    networks = getattr(config, "TRUSTED_PROXY_NETWORKS", None) or []
    if not networks:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in network for network in networks)


def get_client_ip() -> str:
    """获取客户端 IP。

    仅当 TRUST_PROXY_HEADERS 启用且 request.remote_addr 属于 TRUSTED_PROXY_IPS 时，
    才读取 X-Forwarded-For / X-Real-IP，防止客户端直接伪造代理头。
    """
    remote_ip = _remote_addr()
    if config.TRUST_PROXY_HEADERS and remote_ip and _is_trusted_proxy(remote_ip):
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            first_ip = _normalize_ip(forwarded_for.split(",")[0])
            if first_ip:
                return first_ip
        real_ip = _normalize_ip(request.headers.get("X-Real-IP", ""))
        if real_ip:
            return real_ip
    return remote_ip or "unknown"

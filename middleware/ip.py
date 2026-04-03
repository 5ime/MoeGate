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


def get_client_ip() -> str:
    """获取客户端IP，支持在可信代理后读取真实来源IP。"""
    if config.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            first_ip = _normalize_ip(forwarded_for.split(',')[0])
            if first_ip:
                return first_ip
        real_ip = _normalize_ip(request.headers.get('X-Real-IP', ''))
        if real_ip:
            return real_ip
    remote_ip = _normalize_ip(request.remote_addr or '')
    return remote_ip or 'unknown'

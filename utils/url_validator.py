"""Webhook URL 校验与脱敏（防 SSRF）。"""

import ipaddress
import json as json_lib
import socket
from typing import List, Tuple
from urllib.parse import urlparse

import urllib3

_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "metadata",
    "metadata.google.internal",
})


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_webhook_url(url: str) -> Tuple[bool, str]:
    """校验 webhook URL，禁止指向内网/本地/元数据等地址。"""
    text = (url or "").strip()
    if not text:
        return True, ""

    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https"):
        return False, "webhook_url 仅支持 http/https 协议"
    if not parsed.hostname:
        return False, "webhook_url 缺少有效主机名"
    if parsed.username or parsed.password:
        return False, "webhook_url 不允许包含用户名或密码"

    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES:
        return False, "webhook_url 不允许指向本地或元数据服务"

    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(str(ip)):
            return False, "webhook_url 不允许指向内网、本地或保留地址"
        return True, ""
    except ValueError:
        pass

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        results = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror:
        return False, "webhook_url 主机名无法解析"

    if not results:
        return False, "webhook_url 主机名无法解析"

    for item in results:
        resolved_ip = item[4][0]
        if _is_blocked_ip(resolved_ip):
            return False, "webhook_url 解析到不允许的地址"

    return True, ""


def resolve_webhook_ips(url: str) -> Tuple[bool, str, List[str]]:
    """解析 webhook 主机名对应的 IP 列表（需先通过 validate_webhook_url 同等规则）。"""
    ok, reason = validate_webhook_url(url)
    if not ok:
        return False, reason, []

    parsed = urlparse((url or "").strip())
    host = parsed.hostname.lower().rstrip(".")
    try:
        return True, "", [str(ipaddress.ip_address(host))]
    except ValueError:
        pass

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        results = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror:
        return False, "webhook_url 主机名无法解析", []

    ips: List[str] = []
    for item in results:
        resolved_ip = item[4][0]
        if resolved_ip not in ips:
            ips.append(resolved_ip)
    if not ips:
        return False, "webhook_url 主机名无法解析", []
    return True, "", ips


def post_webhook_json(url: str, json_body: dict, timeout: float) -> urllib3.HTTPResponse:
    """向 webhook 发送 JSON，使用 DNS 解析 IP 直连以防 rebinding。"""
    ok, reason, ips = resolve_webhook_ips(url)
    if not ok or not ips:
        raise ValueError(reason or "webhook_url 无效")

    ok_repeat, reason_repeat, ips_repeat = resolve_webhook_ips(url)
    if not ok_repeat or set(ips) != set(ips_repeat):
        raise ValueError(reason_repeat or "webhook DNS 解析结果不一致")

    parsed = urlparse((url or "").strip())
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    pinned_ip = ips[0]
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    body = json_lib.dumps(json_body).encode("utf-8")
    headers = {
        "Host": hostname,
        "Content-Type": "application/json",
    }

    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            pinned_ip,
            port,
            timeout=timeout,
            assert_hostname=hostname,
            server_hostname=hostname,
        )
    else:
        pool = urllib3.HTTPConnectionPool(pinned_ip, port, timeout=timeout)

    return pool.request("POST", path, body=body, headers=headers)


def mask_webhook_url(url: str) -> str:
    """脱敏 webhook URL，仅保留 host 与路径末段。"""
    text = (url or "").strip()
    if not text:
        return ""

    parsed = urlparse(text)
    if not parsed.hostname:
        return ""

    segments = [part for part in (parsed.path or "").split("/") if part]
    tail = segments[-1] if segments else ""
    if tail and len(tail) > 12:
        tail = f"{tail[:4]}...{tail[-4:]}"

    port = f":{parsed.port}" if parsed.port else ""
    path = f"/.../{tail}" if tail else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}{path}"

"""pcap 取证摘要（纯标准库实现）。

把 tcpdump 抓到的 pcap 聚合成"谁、用什么工具、以什么节奏访问了靶机"的可读摘要，
用于在平台上快速筛查异常访问，完整取证仍建议下载 pcap 用 Wireshark 复核。

输出结构：
- 总量/时间范围
- 五元组流统计（Top N）
- HTTP 明文字段（方法、路径、Host、User-Agent）
- 客户端画像与自动化特征信号

只做尽力而为的解析：IPv4/IPv6 + TCP/UDP，链路层支持 Ethernet / Linux SLL / SLL2 / NULL。
超出 max_packets 时会被截断，并在结果里标记 truncated。
"""
import re
import struct
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

_PCAP_MAGIC = {
    b"\xd4\xc3\xb2\xa1": ("<", 1e-6),
    b"\xa1\xb2\xc3\xd4": (">", 1e-6),
    b"\x4d\x3c\xb2\xa1": ("<", 1e-9),
    b"\xa1\xb2\x3c\x4d": (">", 1e-9),
}

_LINKTYPE_NULL = 0
_LINKTYPE_ETHERNET = 1
_LINKTYPE_LINUX_SLL = 113
_LINKTYPE_LINUX_SLL2 = 276

_ETH_IPV4 = 0x0800
_ETH_IPV6 = 0x86DD
_VLAN_ETHERTYPES = frozenset({0x8100, 0x88A8, 0x9100})

_PROTO_TCP = 6
_PROTO_UDP = 17

_HTTP_PREFIXES = (
    b"GET ", b"POST ", b"PUT ", b"HEAD ", b"DELETE ",
    b"OPTIONS ", b"PATCH ", b"CONNECT ",
)

_AUTOMATION_UA = re.compile(
    r"(python-requests|python-urllib|curl/|\bwget\b|go-http-client|okhttp|aiohttp|httpx|"
    r"axios|node-fetch|undici|headlesschrome|phantomjs|selenium|puppeteer|playwright|"
    r"libwww-perl|masscan|sqlmap|nikto|nuclei|dirsearch|gobuster|ffuf|feroxbuster|"
    r"zgrab|nmap|hydra|wpscan|joomscan|whatweb)",
    re.IGNORECASE,
)

# IPv6 扩展头（RFC 8200）：不带选项的逐跳/路由/目的选项，以及分片头。
# 不跳过它们，带扩展头的 IPv6 TCP 会被误判为「非 TCP」而完全不出现在摘要里。
_IPV6_EXT_OPTIONS = frozenset({0, 43, 60})
_IPV6_FRAGMENT = 44
_IPV6_AUTH = 51
_IPV6_MAX_EXT_HEADERS = 8


class PcapFormatError(ValueError):
    """pcap 文件格式非法。"""


def _read_records(handle, max_packets: int) -> Tuple[List[Tuple[float, int, bytes]], bool]:
    """读取 pcap 记录，返回 ([(ts, linktype, frame)], truncated)。"""
    header = handle.read(24)
    if len(header) < 24:
        raise PcapFormatError("pcap 头不完整")
    magic = header[:4]
    if magic not in _PCAP_MAGIC:
        raise PcapFormatError("不是合法的 pcap 文件")
    endian, ts_scale = _PCAP_MAGIC[magic]
    linktype = struct.unpack(endian + "I", header[20:24])[0]

    records: List[Tuple[float, int, bytes]] = []
    truncated = False
    while True:
        if len(records) >= max_packets:
            truncated = True
            break
        block = handle.read(16)
        if len(block) < 16:
            break
        ts_sec, ts_frac, incl_len, _orig_len = struct.unpack(endian + "IIII", block)
        if incl_len <= 0 or incl_len > 262144:
            # tcpdump 正在写最后一条时可能读到半截记录，直接结束
            break
        frame = handle.read(incl_len)
        if len(frame) < incl_len:
            break
        records.append((ts_sec + ts_frac * ts_scale, linktype, frame))
    return records, truncated


def _link_layer(linktype: int, frame: bytes) -> Optional[Tuple[int, int]]:
    """返回 (ethertype, L3 偏移)。"""
    if linktype == _LINKTYPE_ETHERNET:
        if len(frame) < 14:
            return None
        ethertype = struct.unpack("!H", frame[12:14])[0]
        offset = 14
        while ethertype in _VLAN_ETHERTYPES and len(frame) >= offset + 4:
            ethertype = struct.unpack("!H", frame[offset + 2:offset + 4])[0]
            offset += 4
        return ethertype, offset
    if linktype == _LINKTYPE_LINUX_SLL:
        if len(frame) < 16:
            return None
        return struct.unpack("!H", frame[14:16])[0], 16
    if linktype == _LINKTYPE_LINUX_SLL2:
        if len(frame) < 20:
            return None
        return struct.unpack("!H", frame[0:2])[0], 20
    if linktype == _LINKTYPE_NULL:
        if len(frame) < 4:
            return None
        family = struct.unpack("<I", frame[0:4])[0]
        if family == 2:
            return _ETH_IPV4, 4
        if family in (10, 24, 28, 30):
            return _ETH_IPV6, 4
        return None
    return None


def _walk_ipv6_extensions(next_header: int, frame: bytes, offset: int):
    """跳过 IPv6 扩展头，返回 (最终 next_header, L4 偏移)。"""
    for _ in range(_IPV6_MAX_EXT_HEADERS):
        if next_header in _IPV6_EXT_OPTIONS:
            if len(frame) < offset + 2:
                return None
            header_len = (frame[offset + 1] + 1) * 8
            if header_len < 8 or len(frame) < offset + header_len:
                return None
            next_header = frame[offset]
            offset += header_len
        elif next_header == _IPV6_FRAGMENT:
            if len(frame) < offset + 8:
                return None
            next_header = frame[offset]
            offset += 8
        elif next_header == _IPV6_AUTH:
            if len(frame) < offset + 2:
                return None
            header_len = (frame[offset + 1] + 2) * 4
            if len(frame) < offset + header_len:
                return None
            next_header = frame[offset]
            offset += header_len
        else:
            return next_header, offset
    return None


def _ip_layer(ethertype: int, frame: bytes, offset: int) -> Optional[Dict[str, Any]]:
    """解析 IP 头，返回 {proto, src, dst, l4_offset, total_len}。"""
    if ethertype == _ETH_IPV4:
        if len(frame) < offset + 20:
            return None
        header_len = (frame[offset] & 0x0F) * 4
        if header_len < 20 or len(frame) < offset + header_len:
            return None
        proto = frame[offset + 9]
        total_len = struct.unpack("!H", frame[offset + 2:offset + 4])[0]
        src = ".".join(str(b) for b in frame[offset + 12:offset + 16])
        dst = ".".join(str(b) for b in frame[offset + 16:offset + 20])
        return {
            "proto": proto,
            "src": src,
            "dst": dst,
            "l4_offset": offset + header_len,
            "total_len": total_len or (len(frame) - offset),
        }

    if ethertype == _ETH_IPV6:
        if len(frame) < offset + 40:
            return None
        next_header = frame[offset + 6]
        payload_len = struct.unpack("!H", frame[offset + 4:offset + 6])[0]
        src = _format_ipv6(frame[offset + 8:offset + 24])
        dst = _format_ipv6(frame[offset + 24:offset + 40])
        walked = _walk_ipv6_extensions(next_header, frame, offset + 40)
        if walked is None:
            return None
        proto, l4_offset = walked
        return {
            "proto": proto,
            "src": src,
            "dst": dst,
            "l4_offset": l4_offset,
            "total_len": payload_len + 40,
        }

    return None


def _format_ipv6(raw: bytes) -> str:
    try:
        parts = struct.unpack("!8H", raw)
    except struct.error:
        return "::"
    if all(part == 0 for part in parts):
        return "::"
    return ":".join(f"{part:x}" for part in parts)


def _parse_http(payload: bytes) -> Optional[Dict[str, Any]]:
    """从 TCP 负载中尽力解析一条 HTTP 请求。"""
    if len(payload) < 16 or not payload.startswith(_HTTP_PREFIXES):
        return None
    head = payload.split(b"\r\n\r\n", 1)[0]
    lines = head.split(b"\r\n")
    if not lines:
        return None
    request_line = lines[0].decode("latin-1", "replace").split(" ")
    if len(request_line) < 2:
        return None
    result: Dict[str, Any] = {
        "method": request_line[0].upper(),
        "path": request_line[1][:512],
        "host": "",
        "user_agent": "",
        "content_length": 0,
    }
    for line in lines[1:32]:
        text = line.decode("latin-1", "replace")
        if ":" not in text:
            continue
        key, _, value = text.partition(":")
        key_lower = key.strip().lower()
        if key_lower == "host" and not result["host"]:
            result["host"] = value.strip()[:255]
        elif key_lower == "user-agent" and not result["user_agent"]:
            result["user_agent"] = value.strip()[:255]
        elif key_lower == "content-length" and not result["content_length"]:
            try:
                result["content_length"] = max(0, int(value.strip()))
            except (TypeError, ValueError):
                result["content_length"] = 0
    return result


_REASSEMBLY_MAX_FLOWS = 2048
_REASSEMBLY_MAX_BUFFER = 32 * 1024


def _find_http_start(buf: bytes) -> int:
    best = -1
    for prefix in _HTTP_PREFIXES:
        index = buf.find(prefix)
        if index >= 0 and (best < 0 or index < best):
            best = index
    return best


class _HttpAssembler:
    """按 TCP 流重组 HTTP 请求。

    抓包按报文到达，请求行/请求头可能跨段；只按单包解析会漏掉这类请求。
    这里维护每个方向的有界缓冲，按序号去重/对齐，凑齐 `\\r\\n\\r\\n` 后再解析，
    并顺带跳过 Content-Length 声明的主体，避免把 POST body 误当成下一条请求。
    """

    __slots__ = ("buffer", "expected_seq", "body_remaining")

    def __init__(self):
        self.buffer = bytearray()
        self.expected_seq: Optional[int] = None
        self.body_remaining = 0

    def feed(self, seq: int, payload: bytes, ts: float) -> List[Tuple[Dict[str, Any], float]]:
        if not payload:
            return []

        if self.expected_seq is not None:
            if seq < self.expected_seq:
                overlap = self.expected_seq - seq
                if overlap >= len(payload):
                    return []  # 纯重传
                payload = payload[overlap:]
                seq = self.expected_seq
            elif seq > self.expected_seq:
                # 中间有丢包/乱序：已缓冲的半条请求不可信，丢弃后重新开始
                self.buffer.clear()
                self.body_remaining = 0
        self.expected_seq = seq + len(payload)

        if self.body_remaining > 0:
            skip = min(self.body_remaining, len(payload))
            payload = payload[skip:]
            self.body_remaining -= skip
            if not payload:
                return []

        if not self.buffer and not payload.startswith(_HTTP_PREFIXES):
            return []

        self.buffer.extend(payload)
        if len(self.buffer) > _REASSEMBLY_MAX_BUFFER:
            self.buffer.clear()
            self.body_remaining = 0
            return []

        results: List[Tuple[Dict[str, Any], float]] = []
        while self.buffer:
            if not bytes(self.buffer).startswith(_HTTP_PREFIXES):
                index = _find_http_start(bytes(self.buffer))
                if index < 0:
                    # 只保留可能是半个方法名的尾部，其余丢弃，避免缓冲被噪声占满
                    if len(self.buffer) > 8:
                        del self.buffer[:-8]
                    break
                del self.buffer[:index]

            header_end = self.buffer.find(b"\r\n\r\n")
            if header_end < 0:
                break
            head = bytes(self.buffer[:header_end + 4])
            request = _parse_http(head)
            del self.buffer[:header_end + 4]
            if request is None:
                continue
            results.append((request, ts))

            content_length = int(request.get("content_length") or 0)
            if content_length:
                if len(self.buffer) >= content_length:
                    del self.buffer[:content_length]
                else:
                    self.body_remaining = content_length - len(self.buffer)
                    self.buffer.clear()
                    break
        return results


def _peak_per_minute(timestamps: List[float]) -> int:
    """滑动窗口统计一分钟内最大请求数。"""
    if not timestamps:
        return 0
    ordered = sorted(timestamps)
    peak = 1
    left = 0
    for right, value in enumerate(ordered):
        while value - ordered[left] > 60.0:
            left += 1
        peak = max(peak, right - left + 1)
    return peak


def _median_gap_ms(timestamps: List[float]) -> Optional[float]:
    if len(timestamps) < 3:
        return None
    ordered = sorted(timestamps)
    gaps = sorted((b - a) * 1000.0 for a, b in zip(ordered, ordered[1:]))
    middle = len(gaps) // 2
    if len(gaps) % 2:
        return round(gaps[middle], 1)
    return round((gaps[middle - 1] + gaps[middle]) / 2, 1)


def _iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return None


def summarize_files(
    paths: Iterable[str],
    *,
    max_packets: int = 50000,
    max_http: int = 200,
    max_flows: int = 100,
) -> Dict[str, Any]:
    """聚合多个 pcap 文件，返回取证摘要。"""
    max_packets = max(1, int(max_packets))
    total_packets = 0
    total_bytes = 0
    first_ts: Optional[float] = None
    last_ts: Optional[float] = None
    truncated = False
    parse_errors: List[str] = []

    flows: Dict[Tuple[str, int, str, int, int], Dict[str, Any]] = {}
    http_requests: List[Dict[str, Any]] = []
    clients: Dict[str, Dict[str, Any]] = {}
    reassembly: Dict[Tuple[str, int, str, int], _HttpAssembler] = {}

    remaining = max_packets
    for path in paths:
        if remaining <= 0:
            truncated = True
            break
        try:
            with open(path, "rb") as handle:
                records, clipped = _read_records(handle, remaining)
        except (OSError, PcapFormatError) as exc:
            parse_errors.append(f"{path}: {exc}")
            continue

        remaining -= len(records)
        if clipped:
            truncated = True

        for ts, linktype, frame in records:
            total_packets += 1
            total_bytes += len(frame)
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts

            link = _link_layer(linktype, frame)
            if link is None:
                continue
            ip = _ip_layer(link[0], frame, link[1])
            if ip is None:
                continue

            l4_offset = ip["l4_offset"]
            if ip["proto"] == _PROTO_TCP:
                if len(frame) < l4_offset + 20:
                    continue
                sport, dport = struct.unpack("!HH", frame[l4_offset:l4_offset + 4])
                data_offset = (frame[l4_offset + 12] >> 4) * 4
                payload_offset = l4_offset + data_offset
            elif ip["proto"] == _PROTO_UDP:
                if len(frame) < l4_offset + 8:
                    continue
                sport, dport = struct.unpack("!HH", frame[l4_offset:l4_offset + 4])
                payload_offset = l4_offset + 8
            else:
                continue

            flow_key = (ip["src"], sport, ip["dst"], dport, ip["proto"])
            flow = flows.get(flow_key)
            if flow is None:
                if len(flows) < max_flows * 20:
                    flow = {
                        "src": ip["src"],
                        "sport": sport,
                        "dst": ip["dst"],
                        "dport": dport,
                        "proto": "tcp" if ip["proto"] == _PROTO_TCP else "udp",
                        "packets": 0,
                        "bytes": 0,
                        "first_seen": _iso(ts),
                        "last_seen": _iso(ts),
                    }
                    flows[flow_key] = flow
                else:
                    flow = None
            if flow is not None:
                flow["packets"] += 1
                flow["bytes"] += ip["total_len"]
                flow["last_seen"] = _iso(ts)

            if ip["proto"] != _PROTO_TCP:
                continue
            if data_offset < 20 or payload_offset <= l4_offset:
                continue
            stream_key = (ip["src"], sport, ip["dst"], dport)
            # 同一四元组可能被新连接复用（TIME_WAIT 后 ISN 重新随机）：
            # 看到 SYN 就丢弃旧的半条请求，避免把新连接的数据当成旧序号重传。
            if frame[l4_offset + 13] & 0x02:
                reassembly.pop(stream_key, None)
                continue
            if payload_offset >= len(frame):
                continue

            payload = frame[payload_offset:]
            assembler = reassembly.get(stream_key)
            if assembler is None:
                # 只在首个负载看起来像 HTTP 请求时建流，避免给 TLS/扫描器
                # 等所有 TCP 流都分配缓冲。
                if not payload.startswith(_HTTP_PREFIXES):
                    continue
                if len(reassembly) >= _REASSEMBLY_MAX_FLOWS:
                    continue
                assembler = _HttpAssembler()
                reassembly[stream_key] = assembler

            seq = struct.unpack("!I", frame[l4_offset + 4:l4_offset + 8])[0]
            for request, request_ts in assembler.feed(seq, payload, ts):
                client = clients.get(ip["src"])
                if client is None:
                    client = {"ip": ip["src"], "requests": 0, "timestamps": [], "user_agents": set(), "paths": []}
                    clients[ip["src"]] = client
                client["requests"] += 1
                client["timestamps"].append(request_ts)
                if request["user_agent"]:
                    client["user_agents"].add(request["user_agent"])
                if len(client["paths"]) < 50:
                    client["paths"].append(request["path"])

                if len(http_requests) < max_http:
                    http_requests.append({
                        "time": _iso(request_ts),
                        "client": ip["src"],
                        "client_port": sport,
                        "method": request["method"],
                        "host": request["host"],
                        "path": request["path"],
                        "user_agent": request["user_agent"],
                    })

    client_list: List[Dict[str, Any]] = []
    automation_agents: List[str] = []
    headless_clients: List[str] = []
    min_median: Optional[float] = None
    peak_rpm = 0

    for ip, client in clients.items():
        agents = sorted(client["user_agents"])
        automation = [ua for ua in agents if _AUTOMATION_UA.search(ua)]
        if automation:
            headless_clients.append(ip)
            for ua in automation:
                if ua not in automation_agents and len(automation_agents) < 10:
                    automation_agents.append(ua)
        median_gap = _median_gap_ms(client["timestamps"])
        if median_gap is not None and (min_median is None or median_gap < min_median):
            min_median = median_gap
        peak = _peak_per_minute(client["timestamps"])
        peak_rpm = max(peak_rpm, peak)
        client_list.append({
            "ip": ip,
            "requests": client["requests"],
            "first_seen": _iso(min(client["timestamps"])) if client["timestamps"] else None,
            "last_seen": _iso(max(client["timestamps"])) if client["timestamps"] else None,
            "median_interval_ms": median_gap,
            "peak_requests_per_minute": peak,
            "user_agents": agents[:5],
            "sample_paths": client["paths"][:10],
        })

    client_list.sort(key=lambda item: item["requests"], reverse=True)
    flow_list = sorted(flows.values(), key=lambda item: item["bytes"], reverse=True)[:max_flows]

    return {
        "packets": total_packets,
        "bytes": total_bytes,
        "first_seen": _iso(first_ts),
        "last_seen": _iso(last_ts),
        "duration_sec": round(last_ts - first_ts, 1) if first_ts is not None and last_ts is not None else None,
        "truncated": truncated,
        "parse_errors": parse_errors,
        "clients": client_list[:20],
        "flows": flow_list,
        "http_requests": http_requests,
        "signals": {
            "total_http_requests": sum(client["requests"] for client in clients.values()),
            "automation_user_agents": automation_agents,
            "automation_clients": headless_clients[:20],
            "min_median_request_interval_ms": min_median,
            "peak_requests_per_minute": peak_rpm,
        },
    }

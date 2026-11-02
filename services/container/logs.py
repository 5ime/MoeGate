"""容器日志读取与跟随（SSE）。

只服务 MoeGate 受管容器（标签 `moegate.managed=true`），避免通过本接口读取宿主上任意容器。
docker logs 在非 TTY 容器上返回的是带 8 字节帧头的多路复用流，必须先解帧再展示，
否则页面上会出现 `\x01\x00\x00\x00` 之类的二进制噪声。
"""
import logging
import queue
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from docker.errors import NotFound

from core.exceptions import ContainerNotFoundError, ValidationError
from infra.docker import ensure_client

logger = logging.getLogger(__name__)

DEFAULT_TAIL = 200
MAX_TAIL = 5000
# 单次返回的最大字节数，超出保留尾部并标记 truncated，避免超大日志打爆响应与前端
MAX_BYTES = 512 * 1024
# docker tail 可能切坏首帧，多取几行让被切坏的部分落在缓冲行里，
# 保证最终返回给调用方的行都是完整的
TAIL_BUFFER_LINES = 10

# 跟随（follow）相关上限：避免一个 SSE 连接无限占用 worker
FOLLOW_WINDOW_SECONDS = 5      # 单个 follow 窗口，到点由 docker 侧关闭流
DEFAULT_FOLLOW_SECONDS = 300   # 默认最长跟随 5 分钟
MAX_FOLLOW_SECONDS = 3600
DEFAULT_FOLLOW_LINES = 5000
MAX_FOLLOW_LINES = 20000

_FRAME_HEADER_SIZE = 8
# docker 的 tail 是按字节偏移 seek，起点常常落在某个帧的 payload 中间，
# 因此首帧可能是一个"半帧"。向前扫描寻找第一个合法帧头的最大范围。
_MAX_RESYNC_SCAN = 64 * 1024


def _is_frame_header(raw: bytes, pos: int, total: int) -> bool:
    """校验 docker 多路复用帧头：类型 0/1/2 + 3 字节补零 + 长度不越界。"""
    if pos + _FRAME_HEADER_SIZE > total:
        return False
    if raw[pos] not in (0, 1, 2):
        return False
    if raw[pos + 1:pos + 4] != b"\x00\x00\x00":
        return False
    size = int.from_bytes(raw[pos + 4:pos + _FRAME_HEADER_SIZE], "big")
    return pos + _FRAME_HEADER_SIZE + size <= total


def _demux_stream(raw: bytes) -> bytes:
    """剥离 docker 多路复用帧头：[stream_type(1) + padding(3) + size(4)] + payload。"""
    total = len(raw)
    start = 0
    # 首帧可能因 tail 的字节截断而错位：跳到第一个合法帧头，避免把日志内容当帧头吃掉
    if not _is_frame_header(raw, 0, total):
        scan_limit = min(total, _MAX_RESYNC_SCAN)
        for offset in range(1, scan_limit):
            if _is_frame_header(raw, offset, total):
                start = offset
                break
        else:
            # 整段都不像多路复用流（例如已经解过的日志），原样返回，绝不丢内容
            return raw

    payload = bytearray()
    pos = start
    while pos + _FRAME_HEADER_SIZE <= total:
        if not _is_frame_header(raw, pos, total):
            # 中途出现非帧头：剩下的按原样保留，避免吞掉半行日志
            payload.extend(raw[pos:])
            break
        size = int.from_bytes(raw[pos + 4:pos + _FRAME_HEADER_SIZE], "big")
        frame_end = pos + _FRAME_HEADER_SIZE + size
        payload.extend(raw[pos + _FRAME_HEADER_SIZE:frame_end])
        pos = frame_end
    return bytes(payload)


def decode_log_bytes(raw: bytes, *, tty: bool = False) -> str:
    """把 docker logs 原始字节解成文本。"""
    payload = raw if tty else _demux_stream(raw)
    return payload.decode("utf-8", errors="replace")


def _find_frame_start(buf: bytes, total: Optional[int] = None) -> int:
    """在缓冲区中找第一个合法帧头的偏移，找不到返回 -1。"""
    total = len(buf) if total is None else total
    limit = min(total, _MAX_RESYNC_SCAN)
    for offset in range(0, limit):
        if _is_frame_header(buf, offset, total):
            return offset
    return -1


def _looks_like_frame_prefix(raw: bytes) -> bool:
    """是否像 docker 多路复用帧的开头。

    真实 `stream=True` 的 docker SDK 已经帮我们解过帧，chunk 是纯文本；
    旧实现会把这些文本误当"半帧"一直攒到 64KB 才吐，导致跟随延迟数秒。
    帧流（含被 tail 从中间切开的半帧）首字节只会是 0/1/2；
    文本日志首字节是时间戳或字母，因此按首字节分流即可。
    """
    return bool(raw) and raw[0] in (0, 1, 2)


def iter_log_payloads(chunks: Any, *, tty: bool = False):
    """从 docker 流式日志中逐帧产出 payload。

    兼容两种输入：
    - docker SDK `stream=True` 已解帧后的纯文本 chunk（真实路径）；
    - 带 8 字节帧头的原始多路复用流（手工构造/旧调用方）。
    一次 chunk 可能只拿到半个帧，也可能一次拿到多个帧；流开头还可能是被 tail 切坏的半帧。
    """
    buf = bytearray()
    passthrough = tty

    for chunk in chunks:
        data = chunk.encode("utf-8") if isinstance(chunk, str) else (chunk or b"")
        if passthrough:
            yield data
            continue

        if not buf and data and not _looks_like_frame_prefix(data):
            # 不是帧头：docker SDK 已经解过帧，直接按文本输出，不能攒
            passthrough = True
            yield data
            continue

        buf.extend(data)
        while True:
            idx = _find_frame_start(bytes(buf))
            if idx < 0:
                # 攒了足够多仍找不到帧头：这不是多路复用流，按纯文本直通，避免无限攒缓冲
                if len(buf) > _MAX_RESYNC_SCAN:
                    passthrough = True
                    yield bytes(buf)
                    buf.clear()
                break
            if idx > 0:
                # 丢掉半帧残留/噪声，对齐到帧头
                del buf[:idx]
            size = int.from_bytes(buf[4:8], "big")
            frame_end = _FRAME_HEADER_SIZE + size
            if len(buf) < frame_end:
                break  # 帧还没收全，等下一个 chunk
            yield bytes(buf[_FRAME_HEADER_SIZE:frame_end])
            del buf[:frame_end]

    if buf and not passthrough:
        tail = bytes(buf)
        if _find_frame_start(tail) == 0:
            # 没凑齐的半帧：丢掉帧头，保住内容
            yield tail[_FRAME_HEADER_SIZE:]
        else:
            # 流结束了仍找不到帧头：这不是多路复用流，原样输出，绝不吞日志
            yield tail


_LOG_TIMESTAMP_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z) (.*)$",
    re.DOTALL,
)


def _split_log_timestamp(line: str):
    """拆分 docker `timestamps=true` 注入的 RFC3339 前缀。

    返回 (datetime|None, 正文)。没有前缀时原样返回，兼容 TTY 日志与测试桩。
    """
    match = _LOG_TIMESTAMP_RE.match(line)
    if not match:
        return None, line
    try:
        parsed = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
    except ValueError:
        return None, line
    return parsed, match.group(2)


def _close_stream(stream) -> None:
    """尽力关闭 docker 流，唤醒阻塞在迭代里的读取线程。"""
    close = getattr(stream, "close", None)
    if callable(close):
        try:
            close()
        except Exception as exc:  # pragma: no cover - 关闭失败只能放弃该连接
            logger.debug("关闭容器日志流失败: %s", exc)


def _stream_chunks(stream, deadline: float):
    """在独立线程里读取 docker 流，主线程按 deadline 取数据。

    只用 `docker logs --until` 是不够的：当容器没有新日志时，Docker 不会主动
    检查 until 到点，`for chunk in stream` 会无限阻塞（已用 docker CLI 复现）。
    这里加一层队列 + 超时，到点主动 close()，保证 max_seconds 真正生效，
    避免一个空闲容器把 gunicorn 线程永久占住。
    """
    chunks: "queue.Queue" = queue.Queue()

    def reader():
        try:
            for chunk in stream:
                chunks.put(("data", chunk))
        except Exception as exc:  # 连接被主动关闭时这里会抛异常
            chunks.put(("error", exc))
        finally:
            chunks.put(("end", None))

    thread = threading.Thread(
        target=reader, daemon=True, name="ContainerLogFollowReader"
    )
    thread.start()
    try:
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return
            try:
                kind, value = chunks.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                continue
            if kind == "end":
                return
            if kind == "error":
                raise value
            yield value
    finally:
        _close_stream(stream)


def iter_container_logs(
    container_id: str,
    *,
    tail: Any = None,
    since: Any = None,
    timestamps: Any = False,
    max_seconds: Any = None,
    max_lines: Any = None,
):
    """跟随容器日志：先吐存量 tail 行，再按窗口持续输出新行。

    两层边界：
    - 每次 docker 调用仍带 `until` 切窗口，减少长连接；
    - 读取放在 `_stream_chunks` 的带超时队列里，**即使 Docker 不因 until 返回**，
      到点也会关闭流，所以空闲容器不会把连接挂死。
    """
    tail_value = _normalize_tail(tail)
    since_value = _normalize_since(since)
    timestamps_value = _normalize_timestamps(timestamps)
    seconds_value = _normalize_max_seconds(max_seconds)
    lines_value = normalize_max_lines(max_lines)

    client = ensure_client()
    if not client:
        raise ContainerNotFoundError(container_id)

    try:
        container = client.containers.get(container_id)
    except NotFound:
        raise ContainerNotFoundError(container_id)

    labels = ((container.attrs or {}).get("Config") or {}).get("Labels") or {}
    if labels.get("moegate.managed") != "true":
        raise ContainerNotFoundError(container_id)

    tty = bool(((container.attrs or {}).get("Config") or {}).get("Tty"))

    # 存量日志：内部始终带时间戳，用于与后续 follow 去重；
    # 调用方不需要时间戳时再把前缀剥掉，输出格式保持不变。
    snapshot = get_container_logs(
        container_id,
        tail=tail_value,
        since=since_value,
        timestamps=True,
    )
    emitted = 0
    last_timestamp = None
    for raw_line in snapshot["lines"]:
        parsed, text = _split_log_timestamp(raw_line)
        if parsed is not None and (last_timestamp is None or parsed > last_timestamp):
            last_timestamp = parsed
        yield raw_line if timestamps_value else text
        emitted += 1
        if emitted >= lines_value:
            return

    # 关键：不要从调用方的 since 重新开始——快照已经读过这段，重放会造成整段重复。
    # 有快照时间戳时从最后一行的秒开始（同一秒内靠时间戳去重），否则从当前时刻开始。
    if last_timestamp is not None:
        cursor = int(last_timestamp.timestamp())
    elif since_value is not None:
        cursor = since_value
    else:
        cursor = int(time.time())

    deadline = time.time() + seconds_value

    while emitted < lines_value:
        now = time.time()
        if now >= deadline:
            break
        # 窗口必须以“现在”为基准：如果快照最后一条日志已经很旧（空闲容器），
        # cursor + 5 会落在过去，窗口会立即过期，既读不到新日志又会在截止前疯狂空转。
        now_int = int(now)
        window_end = min(now_int + FOLLOW_WINDOW_SECONDS, int(deadline))
        if window_end <= now_int:
            # 剩余不足 1 秒时 int() 会截断到当前秒；给一个最小窗口，
            # 真正的截止时间由 deadline 控制，不会超时。
            window_end = now_int + 1

        stream = container.logs(
            stdout=True,
            stderr=True,
            stream=True,
            follow=True,
            since=cursor,
            until=window_end,
            timestamps=True,
        )
        window_deadline = min(deadline, max(float(window_end), time.time() + 0.2))
        for payload in iter_log_payloads(_stream_chunks(stream, window_deadline), tty=tty):
            for line in payload.decode("utf-8", errors="replace").splitlines():
                parsed, text = _split_log_timestamp(line)
                if parsed is not None:
                    if last_timestamp is not None and parsed <= last_timestamp:
                        continue
                    last_timestamp = parsed
                yield line if timestamps_value else text
                emitted += 1
                if emitted >= lines_value:
                    return
        # 流可能提前结束（容器停止/连接被关闭）；不要直接把 cursor 推到窗口末尾，
        # 否则会跳过这段时间内新产生的日志。
        cursor = max(cursor, int(time.time()))


def _normalize_tail(tail: Any) -> int:
    if tail is None or tail == "":
        return DEFAULT_TAIL
    try:
        value = int(tail)
    except (TypeError, ValueError):
        raise ValidationError("tail 必须是整数")
    if value < 1:
        raise ValidationError("tail 必须大于 0")
    if value > MAX_TAIL:
        raise ValidationError(f"tail 不能超过 {MAX_TAIL}")
    return value


def _normalize_since(since: Any) -> Optional[int]:
    if since is None or since == "":
        return None
    try:
        value = int(since)
    except (TypeError, ValueError):
        raise ValidationError("since 必须是 Unix 秒级时间戳")
    if value < 0:
        raise ValidationError("since 不能为负数")
    return value


def _normalize_timestamps(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _normalize_max_seconds(value: Any) -> int:
    if value is None or value == "":
        return DEFAULT_FOLLOW_SECONDS
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        raise ValidationError("max_seconds 必须是整数")
    if seconds < 1:
        raise ValidationError("max_seconds 必须大于 0")
    return min(seconds, MAX_FOLLOW_SECONDS)


def normalize_max_lines(value: Any) -> int:
    """归一化 max_lines；路由层复用以便与 SSE 事件上限对齐。"""
    if value is None or value == "":
        return DEFAULT_FOLLOW_LINES
    try:
        lines = int(value)
    except (TypeError, ValueError):
        raise ValidationError("max_lines 必须是整数")
    if lines < 1:
        raise ValidationError("max_lines 必须大于 0")
    return min(lines, MAX_FOLLOW_LINES)


def get_container_logs(
    container_id: str,
    *,
    tail: Any = None,
    since: Any = None,
    timestamps: Any = False,
) -> Dict[str, Any]:
    """读取受管容器的标准输出/错误日志。

    Args:
        container_id: 容器 UUID / ID / 名称
        tail: 从末尾取多少行（1..MAX_TAIL，默认 DEFAULT_TAIL）
        since: 只返回该 Unix 秒级时间戳之后的日志
        timestamps: 是否保留 docker 时间戳前缀
    """
    tail_value = _normalize_tail(tail)
    since_value = _normalize_since(since)
    timestamps_value = _normalize_timestamps(timestamps)

    client = ensure_client()
    if not client:
        raise ContainerNotFoundError(container_id)

    try:
        container = client.containers.get(container_id)
    except NotFound:
        raise ContainerNotFoundError(container_id)

    labels = ((container.attrs or {}).get("Config") or {}).get("Labels") or {}
    if labels.get("moegate.managed") != "true":
        # 与 get_container_detail 保持一致：非受管容器一律当作不存在
        raise ContainerNotFoundError(container_id)

    tty = bool(((container.attrs or {}).get("Config") or {}).get("Tty"))
    # TTY 容器没有帧头，也就不会有半帧问题，无需缓冲
    fetch_tail = tail_value if tty else tail_value + TAIL_BUFFER_LINES

    raw = container.logs(
        stdout=True,
        stderr=True,
        stream=False,
        tail=fetch_tail,
        since=since_value,
        timestamps=timestamps_value,
    )
    if isinstance(raw, str):
        raw = raw.encode("utf-8")

    text = decode_log_bytes(raw or b"", tty=tty)

    lines: List[str] = text.splitlines()
    if len(lines) > tail_value:
        lines = lines[-tail_value:]

    truncated = False
    encoded = "\n".join(lines).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        truncated = True
        lines = encoded[-MAX_BYTES:].decode("utf-8", errors="replace").splitlines()

    return {
        "container_id": container.id,
        "container_name": container.name,
        "tail": tail_value,
        "since": since_value,
        "timestamps": timestamps_value,
        "truncated": truncated,
        "line_count": len(lines),
        "lines": lines,
    }

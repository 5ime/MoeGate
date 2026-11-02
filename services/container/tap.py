"""容器流量镜像取证（Traffic Tap）。

为每个受管靶机拉起一个 **共享其网络命名空间** 的 sidecar 容器（`network_mode=container:<id>`），
在其中运行 tcpdump 把流量落盘成 pcap，供事后取证下载与分析。

为什么用 netns 共享而不是网桥镜像：
- 不需要宿主机 NET_ADMIN / iptables TEE，纯净 docker.sock 权限即可；
- 能看到靶机 eth0 与 lo 上的全部报文，未改动的靶机镜像也能抓。

设计约束：
- sidecar **不写** `moegate.managed=true`，因此不占学生容器配额、不会出现在容器列表、
  也不会被 reconcile 当成受管容器恢复销毁定时器；
- 所有异常都被吞掉并打 warning：取证是旁路能力，绝不能影响靶机创建/销毁主流程；
- pcap 按会话命名（`traffic-<epoch>.pcap0..N`），容器重启不会覆盖上一轮证据。
"""
import logging
import os
import re
import shlex
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docker.errors import ImageNotFound, NotFound

from config import config
from core.exceptions import ContainerNotFoundError, DockerConnectionError, ValidationError
from infra.docker import ensure_client
from infra.docker_retry import docker_call
from utils.capture_store import get_capture_store
from utils.pcap_summary import PcapFormatError, summarize_files

logger = logging.getLogger(__name__)

TAP_LABEL = "moegate.tap"
TAP_TARGET_LABEL = "moegate.tap_for"
TAP_KEY_LABEL = "moegate.tap_key"
# 靶机侧标签：创建时由请求参数写入，决定这台靶机要不要抓包（on/off）
TAP_DECISION_LABEL = "moegate.traffic_capture"
TAP_NAME_PREFIX = "moegate-tap-"
CAPTURE_MOUNT = "/capture"
CAPTURE_BASENAME = "traffic"
POLICY_ON = "on"
POLICY_OFF = "off"

_TRUTHY = {"1", "true", "yes", "y", "on", "enable", "enabled"}
_FALSY = {"0", "false", "no", "n", "off", "disable", "disabled"}

_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9_.-]+")
# 兼容旧版 traffic-<epoch>.pcap0 与新版 traffic-<epoch_ms>-<rand>.pcap0
_CAPTURE_FILE_RE = re.compile(r"^traffic-[0-9]+(?:-[0-9a-f]+)?\.pcap[0-9]*$")
_KEY_MAX_LEN = 64
_PRUNE_INTERVAL_SEC = 3600
_BUILD_RETRY_WINDOW_SEC = 300
_STATE: Dict[str, float] = {"build_at": 0.0, "prune_at": 0.0}
_DEFAULT_TAP_IMAGE = "moegate-tap:latest"

# sidecar 名字按靶机 id 固定，两个线程同时给同一台靶机起 tap 会撞名。
# 用一把锁把"检查残留 -> 创建"这一段串行化，避免出现孤儿容器或重复抓包。
_TAP_LOCK = threading.RLock()
_STATE_LOCK = threading.Lock()


def is_enabled() -> bool:
    """是否启用流量取证。"""
    return bool(getattr(config, "ENABLE_TRAFFIC_CAPTURE", False))


def normalize_capture_flag(value: Any) -> Optional[bool]:
    """把 `traffic_capture` 入参归一化为 True/False/None。

    None 表示"未指定，走全局默认"；无法识别的值抛 ValueError，由调用方转成 400。
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    raise ValueError(f"traffic_capture 取值非法: {value!r}（仅接受 true/false）")


def policy_label_value(enabled: bool) -> str:
    """把布尔开关转成标签值。"""
    return POLICY_ON if enabled else POLICY_OFF


def capture_policy(container) -> str:
    """解析某台靶机的取证策略：容器标签优先，缺失时回落到全局默认。"""
    raw = str(_labels_of(container).get(TAP_DECISION_LABEL) or "").strip().lower()
    if raw in (POLICY_ON,) or raw in _TRUTHY:
        return POLICY_ON
    if raw in (POLICY_OFF,) or raw in _FALSY:
        return POLICY_OFF
    default_on = bool(getattr(config, "TRAFFIC_CAPTURE_DEFAULT", False))
    return POLICY_ON if default_on else POLICY_OFF


def capture_mode() -> str:
    """取证落盘方式：`host`（宿主机目录绑定）或 `volume`（Docker 卷）。"""
    host_dir = str(getattr(config, "TRAFFIC_CAPTURE_HOST_DIR", "") or "").strip()
    return "host" if host_dir else "volume"


def capture_root() -> Path:
    """取证文件根目录（MoeGate 进程内可读路径）。

    两种部署形态：
    - 配了 `TRAFFIC_CAPTURE_HOST_DIR`：MoeGate 跑在宿主机上，直接读宿主机目录；
    - 用 Docker 卷：MoeGate 自己也挂着该卷，读 `TRAFFIC_CAPTURE_DIR`（容器内路径）。
    """
    host_dir = str(getattr(config, "TRAFFIC_CAPTURE_HOST_DIR", "") or "").strip()
    if host_dir:
        return Path(host_dir)
    return Path(str(getattr(config, "TRAFFIC_CAPTURE_DIR", "/data/captures")))


def _sanitize_key(value: Any) -> str:
    text = _SAFE_KEY_RE.sub("_", str(value or "").strip())[:_KEY_MAX_LEN].strip("._")
    return text or "unknown"


def _labels_of(container) -> Dict[str, str]:
    try:
        return (container.attrs or {}).get("Config", {}).get("Labels") or {}
    except Exception:
        return {}


def resolve_capture_key(container) -> str:
    """把容器映射为取证目录名，尽量按"学生/项目"聚合。"""
    labels = _labels_of(container)
    project = labels.get("moegate.compose_project_id") or ""
    if project:
        service = labels.get("moegate.compose_service") or ""
        return _sanitize_key(f"{project}__{service}" if service else project)
    return _sanitize_key(labels.get("moegate.container_name") or getattr(container, "name", ""))


def capture_dir(capture_key: str) -> Path:
    return capture_root() / _sanitize_key(capture_key)


def _build_tcpdump_command(basename: str, subdir: Optional[str] = None) -> List[str]:
    """构造 sidecar 命令。

    `subdir` 用于 Docker 卷模式：整卷挂在 `CAPTURE_MOUNT` 上，不给每个靶机分子目录的话，
    所有 pcap 会平铺在卷根——既无法归属到具体靶机，也和读取侧 `<root>/<capture_key>/`
    对不上，表现为"sidecar 在跑但列表永远为空"。
    宿主机目录模式下挂载点本身已经是 `<host_dir>/<capture_key>`，无需再套一层。
    """
    snaplen = max(0, int(getattr(config, "TRAFFIC_CAPTURE_SNAPLEN", 0) or 0))
    rotate_mb = max(1, int(getattr(config, "TRAFFIC_CAPTURE_ROTATE_MB", 64) or 64))
    max_files = max(1, int(getattr(config, "TRAFFIC_CAPTURE_MAX_FILES", 8) or 8))
    target_dir = CAPTURE_MOUNT
    if subdir:
        target_dir = f"{CAPTURE_MOUNT}/{_sanitize_key(subdir)}"
    command = [
        "tcpdump",
        "-i", "any",
        "-n",              # 不做 DNS 反解，避免污染取证流量
        "-U",              # 逐包落盘，进程被 kill 也不丢已抓内容
        "-s", str(snaplen),
        "-w", f"{target_dir}/{basename}.pcap",
        "-C", str(rotate_mb),
        "-W", str(max_files),
    ]
    filter_expr = str(getattr(config, "TRAFFIC_CAPTURE_FILTER", "") or "").strip()
    if filter_expr:
        command.extend(shlex.split(filter_expr))
    if not subdir:
        return command
    # tcpdump 不会自己建目录，交给 sh 先 mkdir；exec 让 tcpdump 接管 PID 1，信号与退出行为不变。
    script = "mkdir -p {directory} && exec {command}".format(
        directory=shlex.quote(target_dir),
        command=" ".join(shlex.quote(part) for part in command),
    )
    return ["sh", "-c", script]


def _resolve_volume_name(client) -> str:
    """解析 sidecar 应挂载的真实卷名。

    `docker-compose.yml` 里的 `moegate-captures` 会被 Compose 加上项目前缀
    （`moegate_moegate-captures`）。sidecar 若按配置里的字面名挂卷，就会写进另一个
    空卷，而 MoeGate 读的是自己的挂载点——表现为「sidecar 在跑，列表永远为空」。
    这里优先从 MoeGate 自身的 Mounts 里取出实际卷名，保证读写是同一份存储。
    """
    configured = str(getattr(config, "TRAFFIC_CAPTURE_VOLUME", "") or "").strip()
    mount_point = str(getattr(config, "TRAFFIC_CAPTURE_DIR", "") or "").strip()
    try:
        me = client.containers.get(socket.gethostname())
        for mount in (getattr(me, "attrs", None) or {}).get("Mounts") or []:
            if (
                str(mount.get("Type") or "") == "volume"
                and str(mount.get("Destination") or "") == mount_point
            ):
                resolved = str(mount.get("Name") or "").strip()
                if resolved:
                    if configured and resolved != configured:
                        logger.info(
                            "取证卷名已按 MoeGate 实际挂载解析: 配置=%s 实际=%s",
                            configured, resolved,
                        )
                    return resolved
    except Exception as exc:
        logger.debug("无法从 MoeGate 自身挂载解析取证卷，回退配置值: %s", exc)
    return configured


def _tap_volumes(capture_key: str, client=None) -> Dict[str, Dict[str, str]]:
    """构造 sidecar 的挂载：优先宿主机绝对路径，否则用 Docker 卷。"""
    host_dir = getattr(config, "TRAFFIC_CAPTURE_HOST_DIR", None)
    if host_dir:
        source = os.path.join(str(host_dir), _sanitize_key(capture_key))
        try:
            os.makedirs(source, exist_ok=True)
        except OSError as exc:
            logger.warning("创建取证目录失败: %s, err=%s", source, exc)
        return {source: {"bind": CAPTURE_MOUNT, "mode": "rw"}}

    volume = _resolve_volume_name(client) if client is not None else ""
    if not volume:
        volume = str(getattr(config, "TRAFFIC_CAPTURE_VOLUME", "") or "").strip()
    if not volume:
        raise RuntimeError("未配置 TRAFFIC_CAPTURE_VOLUME / TRAFFIC_CAPTURE_HOST_DIR")
    return {volume: {"bind": CAPTURE_MOUNT, "mode": "rw"}}


def _build_context_dir() -> Optional[str]:
    root = Path(__file__).resolve().parents[2]
    candidate = root / "deploy" / "tap"
    return str(candidate) if (candidate / "Dockerfile").is_file() else None


def ensure_tap_image(client) -> str:
    """确保取证镜像存在；缺失时用仓库内置 Dockerfile 构建。"""
    image = str(getattr(config, "TRAFFIC_CAPTURE_IMAGE", "") or _DEFAULT_TAP_IMAGE)
    try:
        client.images.get(image)
        return image
    except ImageNotFound:
        pass

    context = _build_context_dir()
    if not context:
        raise RuntimeError(f"取证镜像 {image} 不存在，且未找到 deploy/tap/Dockerfile")

    # 多个容器同时创建时只构建一次
    now = time.time()
    with _STATE_LOCK:
        if now - float(_STATE.get("build_at") or 0) < _BUILD_RETRY_WINDOW_SEC:
            try:
                client.images.get(image)
                return image
            except ImageNotFound:
                pass
        _STATE["build_at"] = now

    logger.info("正在构建取证镜像 %s（context=%s）", image, context)
    client.images.build(path=context, tag=image, rm=True)
    return image


def _wait_until_running(sidecar, timeout: float = 2.0) -> bool:
    """等待 sidecar 进入 running，缩小 tcpdump 初始化漏抓窗口。"""
    deadline = time.time() + max(0.1, timeout)
    while time.time() < deadline:
        try:
            sidecar.reload()
            if str(sidecar.status) == "running":
                return True
        except Exception:
            return False
        time.sleep(0.05)
    return False


def _force_remove(container) -> None:
    try:
        container.remove(force=True)
    except NotFound:
        pass
    except Exception as exc:
        logger.debug("移除取证容器失败: %s, err=%s", getattr(container, "id", "unknown"), exc)


def _list_taps(client, target_id: Optional[str] = None):
    filters = {"label": [f"{TAP_LABEL}=true"]}
    if target_id:
        filters["label"].append(f"{TAP_TARGET_LABEL}={target_id}")
    try:
        return client.containers.list(all=True, filters=filters)
    except Exception as exc:
        logger.debug("查询取证容器失败: %s", exc)
        return []


def _resolve_target_id(client, target: Any) -> Optional[str]:
    """把容器名 / UUID / 短 ID 统一解析成 Docker 全 ID。

    sidecar 的 `moegate.tap_for` 标签始终写的是 `container.id`（64 位），
    而 API 路径常传容器名（UUID）。不归一化就会出现「tap 在跑但 status 说没跑、
    stop 返回 0 个」的假象。
    """
    value = str(target or "").strip()
    if not value:
        return None
    try:
        return str(client.containers.get(value).id)
    except Exception:
        return None


def stop_tap(target_container_id: str) -> int:
    """停止并移除指定靶机的取证 sidecar（不改动已有 pcap）。"""
    client = ensure_client()
    if not client:
        return 0
    with _TAP_LOCK:
        # 与 start_tap 互斥：避免"正在起 tap"和"正在停 tap"交错留下孤儿容器
        taps = _list_taps(client, str(target_container_id))
        if not taps:
            resolved = _resolve_target_id(client, target_container_id)
            if resolved and resolved != str(target_container_id):
                taps = _list_taps(client, resolved)
        for tap in taps:
            _force_remove(tap)
    if taps:
        logger.info("已停止容器 %s 的流量取证（%d 个 tap）", str(target_container_id)[:12], len(taps))
    return len(taps)


def start_tap(container, force: bool = False) -> Optional[Dict[str, Any]]:
    """为容器启动取证 sidecar；失败返回 None（不影响主流程）。

    是否抓包由 `capture_policy()` 决定（请求参数写入的标签 + 全局默认）；
    `force=True` 供管理员手动开启使用，可绕过标签里的 off 策略。
    """
    if not is_enabled():
        return None
    client = ensure_client()
    if not client:
        return None

    target_id = getattr(container, "id", None)
    if not target_id:
        return None

    policy = capture_policy(container)
    if policy == POLICY_OFF and not force:
        logger.debug("容器 %s 的取证策略为 off，跳过抓包", str(target_id)[:12])
        return None

    capture_key = resolve_capture_key(container)
    store = get_capture_store()
    if not force and store.is_stopped(capture_key, str(target_id)):
        # 管理员显式停过录：reconcile / 重启不能偷偷把它开回来（隐私与证据完整性）
        logger.debug("容器 %s 的取证已被管理员停止，跳过自动重建", str(target_id)[:12])
        return None

    tap = None
    try:
        with _TAP_LOCK:
            # "清残留 -> 建 sidecar" 必须连成一步：sidecar 名字按靶机 id 固定，
            # 两个线程并发执行会撞名，导致其中一个失败或留下孤儿容器。
            _remove_taps_for(client, target_id)
            image = ensure_tap_image(client)

            directory = capture_dir(capture_key)
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning("创建取证目录失败: %s, err=%s", directory, exc)

            # 毫秒级 + 纳秒熵：同一秒内 stop/start 或并发创建不会复用同一个文件名，
            # 避免 tcpdump 以 -w 截断上一轮已经落盘的证据。
            basename = f"{CAPTURE_BASENAME}-{time.time_ns() // 1_000_000}-{os.urandom(3).hex()}"
            name = f"{TAP_NAME_PREFIX}{str(target_id)[:12]}"
            # 卷模式下整卷挂在 /capture，写方必须自己落到 <capture_key>/ 子目录；
            # 宿主机目录模式的挂载点已经是该子目录，命令里不需要再套一层。
            command = _build_tcpdump_command(
                basename,
                subdir=None if capture_mode() == "host" else capture_key,
            )
            # 残留同名容器会导致创建失败，先清掉
            try:
                stale = client.containers.get(name)
                _force_remove(stale)
            except NotFound:
                pass
            except Exception as exc:
                logger.debug("清理同名取证容器失败: %s", exc)

            tap = docker_call(lambda: client.containers.create(
                image=image,
                name=name,
                command=command,
                detach=True,
                network_mode=f"container:{target_id}",
                cap_add=["NET_ADMIN", "NET_RAW"],
                labels={
                    TAP_LABEL: "true",
                    TAP_TARGET_LABEL: str(target_id),
                    TAP_KEY_LABEL: capture_key,
                    "moegate.managed": "false",
                    "moegate.container_name": name,
                },
                volumes=_tap_volumes(capture_key, client),
                mem_limit=str(getattr(config, "TRAFFIC_CAPTURE_MEMORY_LIMIT", "128m") or "128m"),
                restart_policy={"Name": "no"},
            ), label="创建取证 sidecar")
            docker_call(tap.start, label="启动取证 sidecar")
        if not _wait_until_running(tap):
            # 启动失败/秒退（镜像缺 tcpdump、BPF 写错等）要在日志里可见；
            # 具体清理交给 reconcile_taps 的健康检查，避免误删正在初始化的 tap。
            logger.warning(
                "取证 sidecar 未在预期时间内进入 running: target=%s tap=%s",
                str(target_id)[:12], str(getattr(tap, "id", ""))[:12],
            )
        store.record(str(target_id), str(getattr(container, "name", "") or ""), capture_key)
        logger.info(
            "流量取证已启动: target=%s tap=%s dir=%s",
            str(target_id)[:12], str(tap.id)[:12], directory,
        )
        return {
            "target_container_id": target_id,
            "tap_container_id": tap.id,
            "capture_key": capture_key,
            "capture_dir": str(directory),
            "basename": basename,
            "policy": POLICY_ON,
            "forced": bool(force) and policy == POLICY_OFF,
        }
    except Exception as exc:
        # 失败时不能把 created/半启动的容器留在原地：它会占住固定名字，
        # 而旧版 reconcile 又会把它当成"已有 tap"，导致该靶机永久不再抓包。
        if tap is not None:
            _force_remove(tap)
        logger.warning("启动流量取证失败（靶机不受影响）: target=%s err=%s", str(target_id)[:12], exc)
        return None


def _remove_taps_for(client, target_id: str) -> None:
    for tap in _list_taps(client, target_id):
        _force_remove(tap)


def start_taps_for(container_ids) -> List[Optional[Dict[str, Any]]]:
    """批量启动取证，返回与入参等长的结果列表。"""
    ids = [str(item) for item in (container_ids or []) if item]
    if not is_enabled() or not ids:
        return [None] * len(ids)

    client = ensure_client()
    if not client:
        return [None] * len(ids)

    results: List[Optional[Dict[str, Any]]] = []
    for container_id in ids:
        try:
            container = client.containers.get(container_id)
        except Exception as exc:
            logger.debug("取证跳过程序无法解析的容器 %s: %s", container_id[:12], exc)
            results.append(None)
            continue
        results.append(start_tap(container))
    return results


def _capture_files(capture_key: str) -> List[Path]:
    directory = capture_dir(capture_key)
    if not directory.is_dir():
        return []
    files = []
    for path in directory.iterdir():
        if path.is_file() and _CAPTURE_FILE_RE.match(path.name):
            files.append(path)
    return sorted(files, key=lambda item: (len(item.name), item.name))


def capture_files(capture_key: str) -> List[Path]:
    """列出某取证目录下已落盘的 pcap（公开给告警扫描等旁路模块使用）。"""
    return _capture_files(capture_key)


def active_taps(client=None):
    """列出当前所有取证 sidecar（`moegate.tap=true`）。"""
    client = client or ensure_client()
    if not client:
        return []
    return _list_taps(client)


def get_capture_status(container_id: str) -> Dict[str, Any]:
    """查询某容器的取证状态与已落盘文件。

    容器销毁后仍会通过 captures.json 里的映射继续展示/下载留存 pcap：
    考试结束往往先销毁靶机再复盘，证据不能随容器一起消失。
    """
    result: Dict[str, Any] = {
        "container_id": container_id,
        "enabled": is_enabled(),
        "policy": POLICY_OFF,
        "requested": None,
        "running": False,
        "tap_container_id": None,
        "capture_key": None,
        "capture_dir": None,
        "storage_mode": capture_mode(),
        "capture_root": str(capture_root()),
        "readable": capture_root().is_dir(),
        "target_exists": False,
        "stopped": False,
        "hint": "",
        "files": [],
        "total_bytes": 0,
    }

    client = ensure_client()
    populated = None
    capture_key: Optional[str] = None
    if client:
        # 先把容器解析成全 ID：tap 标签写的是 container.id，而 API 路径常是 UUID/名称。
        try:
            populated = client.containers.get(container_id)
        except Exception:
            populated = None
        if populated is not None:
            labels = ((populated.attrs or {}).get("Config") or {}).get("Labels") or {}
            if str(labels.get("moegate.managed") or "").lower() != "true":
                raise ValidationError("只能对本平台下发的靶机做流量取证")
            result["target_exists"] = True
            result["policy"] = capture_policy(populated)
            raw = str(_labels_of(populated).get(TAP_DECISION_LABEL) or "").strip().lower()
            result["requested"] = raw or None
            capture_key = resolve_capture_key(populated)

        target_ids = [str(populated.id)] if populated is not None else [str(container_id)]
        taps = []
        for target_id in target_ids:
            taps = _list_taps(client, target_id)
            if taps:
                break
        for tap in taps:
            result["tap_container_id"] = tap.id
            capture_key = _labels_of(tap).get(TAP_KEY_LABEL) or capture_key
            try:
                result["running"] = str(tap.status) == "running"
            except Exception:
                result["running"] = False

    if not capture_key:
        # 容器与 sidecar 都已销毁时回落到持久化索引
        capture_key = get_capture_store().lookup(str(container_id))

    if not capture_key:
        _apply_hint(result)
        return result

    result["capture_key"] = capture_key
    result["capture_dir"] = str(capture_dir(capture_key))
    result["readable"] = capture_root().is_dir()
    if populated is not None:
        result["stopped"] = get_capture_store().is_stopped(capture_key, str(populated.id))
    files = []
    total = 0
    for path in _capture_files(capture_key):
        try:
            stat = path.stat()
        except OSError:
            continue
        total += stat.st_size
        files.append({
            "name": path.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    result["files"] = files
    result["total_bytes"] = total
    _apply_hint(result)
    return result


def _apply_hint(result: Dict[str, Any]) -> None:
    """给取证状态补一句可执行的排查提示。

    "sidecar 在跑、列表却是空的"是最难自查的故障：可能是没流量，也可能是
    MoeGate 与 sidecar 看的根本不是同一份存储。这里把原因直接讲出来。
    """
    result["hint"] = _capture_hint(
        enabled=bool(result.get("enabled")),
        policy=str(result.get("policy") or POLICY_OFF),
        running=bool(result.get("running")),
        has_files=bool(result.get("files")),
        root=capture_root(),
        mode=str(result.get("storage_mode") or capture_mode()),
        target_exists=bool(result.get("target_exists", True)),
        stopped=bool(result.get("stopped")),
    )


def _capture_hint(
    enabled: bool,
    policy: str,
    running: bool,
    has_files: bool,
    root: Path,
    mode: str,
    target_exists: bool = True,
    stopped: bool = False,
) -> str:
    # 有文件就不要再报"不会抓包"：即使策略是 off、容器已销毁，证据依然可下载。
    if has_files:
        return ""
    if not enabled:
        return "服务端未开启流量取证（ENABLE_TRAFFIC_CAPTURE=false），本容器不会抓包"
    if not target_exists:
        return "靶机已销毁，未找到留存的 pcap（可能创建时未开启取证，或已按保留时长清理）"
    if running:
        if not root.is_dir():
            if mode == "volume":
                return (
                    f"sidecar 正在录制，但 MoeGate 读不到 pcap：取证根目录 {root} 不存在。"
                    "卷模式下 MoeGate 必须与 sidecar 挂载同一个卷（docker-compose 已内置），"
                    "裸机部署请改用 TRAFFIC_CAPTURE_HOST_DIR 指向宿主机真实路径"
                )
            return f"sidecar 正在录制，但 MoeGate 读不到 pcap：取证根目录 {root} 不存在，请检查 TRAFFIC_CAPTURE_HOST_DIR"
        return "sidecar 正在录制，暂未落盘：靶机还没有流量，或 TRAFFIC_CAPTURE_FILTER 过滤过严"
    if stopped:
        return "该靶机已由管理员停止抓包（重启/reconcile 不会自动恢复），点「开始抓包」可继续"
    if policy != POLICY_ON:
        return "该靶机取证策略为 off：创建时传 traffic_capture=true，或点「开始抓包」临时补录"
    return "sidecar 未运行：靶机已停止，或需要点「开始抓包」补录"


def resolve_capture_file(container_id: str, filename: str) -> Optional[Path]:
    """校验并解析下载路径，拒绝目录穿越与非法文件名。"""
    name = str(filename or "").strip()
    if not name or not _CAPTURE_FILE_RE.match(name):
        return None

    status_key: Optional[str] = None
    client = ensure_client()
    target = None
    if client:
        # 靶机可能已销毁，此时仍允许下载留存的 pcap；
        # 但只要容器还在，就必须是本平台下发的靶机。
        try:
            target = client.containers.get(str(container_id))
        except Exception:
            target = None
        if target is not None:
            labels = ((target.attrs or {}).get("Config") or {}).get("Labels") or {}
            if str(labels.get("moegate.managed") or "").lower() != "true":
                return None
            for tap in _list_taps(client, str(target.id)):
                status_key = _labels_of(tap).get(TAP_KEY_LABEL) or status_key
            if status_key is None:
                status_key = resolve_capture_key(target)

    if not status_key:
        # 容器与 sidecar 都没了：按持久化索引解析，保证销毁后仍能下载已留存证据。
        status_key = get_capture_store().lookup(str(container_id))
    if not status_key:
        return None

    directory = capture_dir(status_key).resolve()
    candidate = (directory / name).resolve()
    if directory != candidate.parent:
        return None
    return candidate if candidate.is_file() else None


def get_capture_summary(container_id: str, max_packets: int = 50000, max_http: int = 200) -> Dict[str, Any]:
    """生成取证摘要（流量统计 + HTTP 明文字段 + 自动化特征信号）。"""
    status = get_capture_status(container_id)
    if not status.get("capture_key"):
        return {"container_id": container_id, "capture_key": None, "summary": None, "message": "该容器没有取证记录"}

    files = _capture_files(status["capture_key"])
    if not files:
        return {
            "container_id": container_id,
            "capture_key": status["capture_key"],
            "summary": None,
            "message": status.get("hint") or "取证目录为空（靶机可能还没有流量）",
        }
    # 摘要预算有限时优先看最新一轮：考试复盘关心的是刚发生的行为，
    # 而不是几天前已经轮转出去的旧会话。
    files = sorted(
        files,
        key=lambda path: _safe_mtime(path),
        reverse=True,
    )

    try:
        summary = summarize_files(
            [str(path) for path in files],
            max_packets=max_packets,
            max_http=max_http,
        )
    except PcapFormatError as exc:
        return {
            "container_id": container_id,
            "capture_key": status["capture_key"],
            "summary": None,
            "message": f"pcap 解析失败: {exc}",
        }

    summary["files"] = [path.name for path in files]
    message = "ok"
    if summary.get("parse_errors"):
        message = "部分 pcap 无法解析：" + "；".join(summary["parse_errors"][:3])
    elif summary.get("packets", 0) <= 0:
        message = "pcap 中没有可解析的报文（文件可能仍在写入或已损坏）"
    return {
        "container_id": container_id,
        "capture_key": status["capture_key"],
        "summary": summary,
        "message": message,
    }


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _require_managed_container(client, container_id: str):
    """取回容器并确认它是本平台下发的靶机。

    取证 sidecar 是 `network_mode=container:<id>` + `NET_ADMIN`，没有任何隔离可言——
    少了这层校验，就能给宿主机上任意容器（含 MoeGate 自身、其他租户）挂 tcpdump
    并下载它的全部流量。其余操作入口都有等价校验，这里不能例外。
    """
    try:
        container = client.containers.get(str(container_id))
    except NotFound as exc:
        raise ContainerNotFoundError(str(container_id)) from exc

    labels = ((container.attrs or {}).get("Config") or {}).get("Labels") or {}
    if str(labels.get("moegate.managed") or "").lower() != "true":
        raise ValidationError("只能对本平台下发的靶机做流量取证")
    return container


def start_capture(container_id: str, force: bool = True) -> Dict[str, Any]:
    """手动为指定容器开启取证（供 API 调用）。

    手动开启默认 `force=True`：即使创建时传了 `traffic_capture=false` 也能立刻抓包。
    注意容器标签不可变，因此该覆盖只在本次 sidecar 生命周期内有效；
    靶机重启后仍按创建参数/全局默认恢复。手动开启也会清除此前的「已停止」标记。
    """
    if not is_enabled():
        raise ValidationError("流量取证未启用（ENABLE_TRAFFIC_CAPTURE=false）")

    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    container = _require_managed_container(client, str(container_id))

    result = start_tap(container, force=force)
    if not result:
        raise ValidationError("取证 sidecar 启动失败，请检查取证镜像与挂载配置")
    get_capture_store().clear_stopped(result["capture_key"], str(container.id))
    return result


def stop_capture(container_id: str) -> Dict[str, Any]:
    """停止取证 sidecar；已落盘的 pcap 一律保留。

    停止状态会写入 captures.json：reconcile 看到该标记后不会在下一轮把 tap 偷偷建回来。
    """
    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")
    container = _require_managed_container(client, str(container_id))

    removed = stop_tap(str(container.id))
    capture_key = resolve_capture_key(container)
    store = get_capture_store()
    store.record(str(container.id), str(getattr(container, "name", "") or ""), capture_key)
    store.mark_stopped(capture_key, str(container.id))
    return {
        "container_id": str(container_id),
        "stopped_taps": removed,
        "files_kept": True,
    }


def prune_captures(force: bool = False) -> int:
    """按保留时长清理过期 pcap（默认 7 天，0 表示不清理）。

    即使 `ENABLE_TRAFFIC_CAPTURE=false` 也要继续清理：关掉能力不应把历史 pcap
    永久留在磁盘上（敏感数据 + 磁盘占用）。
    """
    hours = int(getattr(config, "TRAFFIC_CAPTURE_RETENTION_HOURS", 168) or 0)
    if hours <= 0:
        return 0
    now = time.time()
    with _STATE_LOCK:
        if not force and now - float(_STATE.get("prune_at") or 0) < _PRUNE_INTERVAL_SEC:
            return 0
        _STATE["prune_at"] = now

    root = capture_root()
    if not root.is_dir():
        return 0

    # 正在录制的 pcap 可能因长时间空闲而 mtime 变旧，不能直接 unlink：
    # tcpdump 仍持有该 inode，删掉后后续证据会写进不可见的文件。
    active_keys = _active_capture_keys(ensure_client())

    cutoff = now - hours * 3600
    removed = 0
    existing_keys = set()
    for path in root.rglob("*.pcap*"):
        try:
            if not path.is_file():
                continue
            existing_keys.add(path.parent.name)
            if path.parent.name in active_keys:
                continue
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError as exc:
            logger.debug("清理取证文件失败: %s, err=%s", path, exc)
    # 同步清理已经没有目录的索引条目，避免 captures.json 无限增长
    try:
        get_capture_store().prune(existing_keys)
    except Exception as exc:
        logger.debug("清理取证索引失败: %s", exc)
    if removed:
        logger.info("已清理 %d 个过期取证文件（保留 %d 小时）", removed, hours)
    return removed


def _active_capture_keys(client) -> set:
    keys = set()
    if not client:
        return keys
    try:
        for tap in _list_taps(client):
            key = _labels_of(tap).get(TAP_KEY_LABEL)
            if key:
                keys.add(key)
    except Exception as exc:
        logger.debug("查询活动取证 sidecar 失败: %s", exc)
    return keys


def enforce_capture_quota() -> int:
    """按 capture_key 限制 pcap 总量，删最旧文件直到回到配额内。

    tcpdump 的 `-C/-W` 只约束**单个进程**；靶机每重启/手动开始一次都会新开一组
    `traffic-*`，多轮会话会一直累积到保留期。默认 1GB/靶机，0 表示不限制。
    正在录制的 capture_key 会整组跳过：删除 tcpdump 正持有的 inode 会让后续证据写入
    不可见文件，比磁盘超标更糟。
    """
    quota_mb = int(getattr(config, "TRAFFIC_CAPTURE_QUOTA_MB", 0) or 0)
    if quota_mb <= 0:
        return 0
    root = capture_root()
    if not root.is_dir():
        return 0

    active_keys = _active_capture_keys(ensure_client())
    limit = quota_mb * 1024 * 1024
    removed = 0
    for directory in root.iterdir():
        try:
            if not directory.is_dir() or directory.name in active_keys:
                continue
        except OSError:
            continue
        files = []
        total = 0
        for path in _capture_files(directory.name):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            files.append((path, size))
            total += size
        if total <= limit:
            continue
        for path, size in sorted(files, key=lambda item: _safe_mtime(item[0])):
            if total <= limit:
                break
            try:
                path.unlink()
                total -= size
                removed += 1
            except OSError as exc:
                logger.debug("按配额清理取证文件失败: %s, err=%s", path, exc)
    if removed:
        logger.info("取证配额清理: 删除 %d 个最旧 pcap（上限 %dMB/靶机）", removed, quota_mb)
    return removed


def reconcile_taps() -> int:
    """对齐取证 sidecar 与靶机状态：清孤儿/死 tap、补缺失、清过期文件。"""
    # 先跑保留期清理与总量配额：只涉及本地文件，能力关闭时同样要执行。
    prune_captures()
    enforce_capture_quota()

    if not is_enabled():
        return 0

    client = ensure_client()
    if not client:
        return 0

    taps = _list_taps(client)
    live_targets = set()
    removed = 0
    for tap in taps:
        target_id = _labels_of(tap).get(TAP_TARGET_LABEL) or ""
        if not target_id:
            _force_remove(tap)
            removed += 1
            continue
        try:
            # sidecar 自己死掉（tcpdump 退出、镜像缺依赖、BPF 写错）时，
            # 旧版实现只看靶机状态，会把 exited/created 的 tap 当成"仍在录"，
            # 结果该靶机永久不再抓包。这里必须同时校验 tap 自身状态。
            try:
                tap.reload()
                tap_running = str(tap.status) == "running"
            except Exception:
                tap_running = False
            if not tap_running:
                logger.warning(
                    "取证 sidecar 未运行，移除后按策略重建: tap=%s target=%s",
                    str(getattr(tap, "id", ""))[:12], target_id[:12],
                )
                _force_remove(tap)
                removed += 1
                continue

            target = client.containers.get(target_id)
            target.reload()
            if str(target.status) != "running":
                _force_remove(tap)
                removed += 1
                continue

            # 靶机被外部重启后，旧 tap 仍挂在旧 netns 上：比对启动时间后重建。
            target_started = str(
                ((getattr(target, "attrs", None) or {}).get("State") or {}).get("StartedAt") or ""
            )
            tap_created = str((getattr(tap, "attrs", None) or {}).get("Created") or "")
            if target_started and tap_created and target_started > tap_created:
                logger.info(
                    "靶机启动时间晚于取证 sidecar，重建 tap: target=%s", target_id[:12]
                )
                _force_remove(tap)
                removed += 1
                continue
        except NotFound:
            _force_remove(tap)
            removed += 1
            continue
        except Exception as exc:
            logger.debug("校验取证目标 %s 失败: %s", target_id[:12], exc)
            continue
        live_targets.add(target_id)

    # 兜底：靶机在运行但没有 tap（MoeGate 重启前创建、或 tap 被误删）
    started = 0
    try:
        managed = client.containers.list(filters={"label": "moegate.managed=true"})
    except Exception as exc:
        logger.debug("查询受管容器失败: %s", exc)
        managed = []
    for container in managed:
        try:
            if str(container.status) != "running" or container.id in live_targets:
                continue
            if start_tap(container):
                started += 1
        except Exception as exc:
            logger.debug("补齐取证 tap 失败: %s", exc)

    if removed or started:
        logger.info("流量取证 reconcile: 清理 %d 个孤儿/失效 tap，补齐 %d 个", removed, started)
    return removed + started

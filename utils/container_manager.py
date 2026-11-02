"""容器管理器 - 封装容器生命周期和状态管理。"""

import heapq
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Callable, List, Any, Tuple
from docker.models.containers import Container
from config import config
from core.exceptions import MaxRenewTimesExceededError
from utils.lifecycle_store import LifecycleStore

logger = logging.getLogger(__name__)

EXPIRES_AT_LABEL = "moegate.expires_at"
RENEW_COUNT_LABEL = "moegate.renew_count"
RESERVED_ID_PREFIX = "__reserved_"
_quota_thread_local = threading.local()

# 到期销毁的执行池：销毁涉及 Docker stop/remove，不能在调度线程里同步跑，
# 否则一次慢删除会卡住后续所有容器的到期处理。
_expiry_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="moegate-expiry")


class ContainerManager:
    """容器管理器：缓存容器对象、管理到期销毁与续期。"""

    # Docker 侧受管容器数量的缓存有效期（秒）
    _MANAGED_COUNT_TTL_SEC = 2.0
    _managed_count_cache: Dict[str, float] = {"at": 0.0, "value": 0}
    _managed_count_lock = threading.Lock()

    def __init__(self):
        self._containers: Dict[str, Container] = {}
        # 到期时间最小堆：(expires_at, seq, container_id)，配合单个定时器调度
        self._expiry_heap: List[Any] = []
        self._expiry_seq = 0
        self._timer: Optional[threading.Timer] = None
        self._timer_generation = 0
        self._counts: Dict[str, int] = {}
        self._expires_at: Dict[str, int] = {}
        self._lifecycle_store = LifecycleStore(config.ALLOWED_BASE_DIR)
        self._containers_lock = threading.Lock()
        self._timers_lock = threading.Lock()
        # _counts 与 _expires_at 同属生命周期元数据，必须共用一把锁：
        # 续期会同时改这两者，分开加锁会出现"计数已 +1、到期时间还是旧的"的中间态。
        self._lifecycle_lock = threading.RLock()
        self._destroy_callbacks: List[Callable[[str], None]] = []
        self._pending_count = 0
        self._reconcile_thread: Optional[threading.Thread] = None
        self._reconcile_running = False
        self._reconcile_lock = threading.Lock()

    def register_destroy_callback(self, callback: Callable[[str], None]):
        """注册销毁回调（参数为 container_id）。"""
        self._destroy_callbacks.append(callback)

    @staticmethod
    def is_reserved_id(container_id: str) -> bool:
        return str(container_id).startswith(RESERVED_ID_PREFIX)

    def _real_container_count(self) -> int:
        return sum(1 for value in self._containers.values() if value is not None)

    def get_active_count(self) -> int:
        """返回当前真实容器数量（不含预留占位）。"""
        with self._containers_lock:
            return self._real_container_count()

    def get_usage_count(self) -> int:
        with self._containers_lock:
            managed = self._docker_managed_count()
            return max(self._real_container_count(), managed, 0) + self._pending_count

    @classmethod
    def _docker_managed_count(cls) -> int:
        """查询 Docker 侧受管容器数量（带短 TTL 缓存）。

        每次创建容器都全量 list 一遍会明显放大并发开销，短 TTL 内复用结果即可：
        本进程新建的部分由 `_pending_count` 覆盖，跨进程由共享配额文件锁覆盖。

        Returns:
            int: 受管容器数量；**-1 表示查不出来**。调用方必须按"未知"处理，
                 绝不能当成 0——那会把配额算得极其宽松，导致超额下发靶机。
        """
        now = time.time()
        with cls._managed_count_lock:
            cached = cls._managed_count_cache
            if now - float(cached.get("at") or 0.0) < cls._MANAGED_COUNT_TTL_SEC:
                return int(cached.get("value") or 0)

        try:
            from infra.docker import ensure_client

            client = ensure_client()
            if not client:
                return cls._fallback_managed_count("Docker 客户端不可用")
            value = len(client.containers.list(all=True, filters={"label": "moegate.managed=true"}))
        except Exception as exc:
            return cls._fallback_managed_count(str(exc))

        with cls._managed_count_lock:
            cls._managed_count_cache = {"at": now, "value": value}
        return value

    @classmethod
    def _fallback_managed_count(cls, reason: str) -> int:
        """查询失败时用上次的结果兜底；从未成功过则返回 -1（未知）。"""
        with cls._managed_count_lock:
            cached = cls._managed_count_cache
            if float(cached.get("at") or 0.0) > 0:
                logger.warning("查询 Docker 受管容器数量失败，沿用上次结果: %s", reason)
                return int(cached.get("value") or 0)
        logger.error("无法确认 Docker 受管容器数量（%s），创建请求将按未知处理", reason)
        return -1

    @staticmethod
    def _pop_quota_reservation() -> Optional[str]:
        reservation_ids = getattr(_quota_thread_local, "reservation_ids", None)
        if not reservation_ids:
            return None
        reservation_id = reservation_ids.pop()
        if not reservation_ids:
            delattr(_quota_thread_local, "reservation_ids")
        return reservation_id

    @staticmethod
    def _push_quota_reservation(reservation_id: str) -> None:
        reservation_ids = getattr(_quota_thread_local, "reservation_ids", None)
        if reservation_ids is None:
            reservation_ids = []
            _quota_thread_local.reservation_ids = reservation_ids
        reservation_ids.append(reservation_id)

    @staticmethod
    def _release_shared_quota_reservation() -> None:
        if not getattr(config, "ENABLE_SHARED_QUOTA", True):
            return
        reservation_id = ContainerManager._pop_quota_reservation()
        if not reservation_id:
            return
        try:
            from utils.quota_store import get_shared_quota_store

            get_shared_quota_store().release(reservation_id)
        except Exception as exc:
            logger.warning("释放共享配额预留失败: %s", exc)

    def check_and_reserve(self, max_containers: int, slots: int = 1) -> bool:
        slots = max(1, int(slots))
        managed_count = self._docker_managed_count()
        if managed_count < 0:
            # 真实占用查不出来时一律拒绝：宁可少发，也不能在未知基数上超额下发。
            logger.error("Docker 受管容器数量未知，拒绝本次创建请求（slots=%s）", slots)
            return False
        reservation_id = None
        if getattr(config, "ENABLE_SHARED_QUOTA", True):
            try:
                from utils.quota_store import get_shared_quota_store

                reservation_id = get_shared_quota_store().try_reserve(
                    slots=slots,
                    max_containers=max_containers,
                    managed_count=managed_count,
                )
                if reservation_id is None:
                    return False
            except Exception as exc:
                logger.warning("共享配额预留失败，回退到进程内计数: %s", exc)
                reservation_id = None

        with self._containers_lock:
            # 在锁内重新取一次，避免用锁外读到的陈旧计数做判定
            # 未知（-1）不参与 max，交由上面的拒绝分支兜住
            active_count = max(self._real_container_count(), self._docker_managed_count(), 0)
            if active_count + self._pending_count + slots > max_containers:
                if reservation_id is not None:
                    try:
                        from utils.quota_store import get_shared_quota_store

                        get_shared_quota_store().release(reservation_id)
                    except Exception as exc:
                        logger.warning("回滚共享配额预留失败: %s", exc)
                return False
            self._pending_count += slots
            if reservation_id is not None:
                self._push_quota_reservation(reservation_id)
            return True

    def release_reservation(self, slots: int = 1):
        slots = max(1, int(slots))
        self._release_shared_quota_reservation()
        with self._containers_lock:
            self._pending_count = max(0, self._pending_count - slots)

    def consume_reservation(self, slots: int = 1):
        slots = max(1, int(slots))
        self._release_shared_quota_reservation()
        with self._containers_lock:
            self._pending_count = max(0, self._pending_count - slots)

    def add_container(self, container_id: str, container: Container, *, consume_reservation: bool = True):
        """缓存容器对象；创建流程成功时可消费一个预留名额。"""
        with self._containers_lock:
            self._containers[container_id] = container
            if consume_reservation and self._pending_count > 0:
                self._pending_count -= 1

    def get_container(self, container_id: str) -> Optional[Container]:
        """获取容器对象（不存在则返回 None）。"""
        with self._containers_lock:
            return self._containers.get(container_id)

    def remove_container(self, container_id: str) -> Optional[Container]:
        """移除并返回容器对象（不存在则返回 None）。"""
        with self._containers_lock:
            return self._containers.pop(container_id, None)

    def get_all_containers(self) -> Dict[str, Container]:
        """获取容器字典副本（不含预留占位）。"""
        with self._containers_lock:
            return {
                container_id: container
                for container_id, container in self._containers.items()
                if container is not None
            }

    def get_container_ids(self) -> List[str]:
        """获取所有真实容器 ID（不含预留占位）。"""
        with self._containers_lock:
            return [
                container_id
                for container_id, container in self._containers.items()
                if container is not None
            ]

    @staticmethod
    def compute_expires_at(ttl_seconds: int) -> int:
        return int(time.time()) + max(0, int(ttl_seconds))

    @staticmethod
    def _read_expires_at_from_labels(container: Container) -> Optional[int]:
        labels = ((container.attrs or {}).get("Config") or {}).get("Labels") or {}
        raw = labels.get(EXPIRES_AT_LABEL)
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def read_expires_at(container: Container) -> Optional[int]:
        return ContainerManager._read_expires_at_from_labels(container)

    @staticmethod
    def _read_renew_count_from_labels(container: Container) -> int:
        labels = ((container.attrs or {}).get("Config") or {}).get("Labels") or {}
        raw = labels.get(RENEW_COUNT_LABEL)
        if raw is None:
            return 0
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def read_renew_count(container: Container) -> int:
        return ContainerManager._read_renew_count_from_labels(container)

    def _read_persisted_lifecycle(self, container_id: str) -> Optional[Dict[str, int]]:
        try:
            return self._lifecycle_store.get(container_id)
        except Exception as exc:
            logger.warning("读取容器 %s 生命周期持久化失败: %s", container_id, exc)
            return None

    def ensure_lifecycle_state(self, container: Container) -> None:
        """从持久化或 labels 加载生命周期状态到进程内缓存。"""
        self._resolve_expires_at(container)
        self._resolve_renew_count(container)

    def _resolve_expires_at(self, container: Container) -> Optional[int]:
        container_id = container.id
        # 先无锁读一次（dict.get 是原子操作），命中就直接返回，避免锁内做磁盘 IO
        cached = self._expires_at.get(container_id)
        if cached is not None:
            return cached

        with self._lifecycle_lock:
            cached = self._expires_at.get(container_id)
            if cached is not None:
                return cached

            persisted = self._read_persisted_lifecycle(container_id) or {}
            persisted_expires_at = persisted.get("expires_at")
            if persisted_expires_at is not None:
                self._expires_at[container_id] = persisted_expires_at
                return persisted_expires_at

            expires_at = self._read_expires_at_from_labels(container)
            if expires_at is not None:
                self._expires_at[container_id] = expires_at
            return expires_at

    def _resolve_renew_count(self, container: Container) -> int:
        container_id = container.id
        with self._lifecycle_lock:
            if container_id in self._counts:
                return self._counts[container_id]

        persisted = self._read_persisted_lifecycle(container_id) or {}
        if "renew_count" in persisted:
            renew_count = max(0, int(persisted["renew_count"]))
        else:
            renew_count = self._read_renew_count_from_labels(container)

        with self._lifecycle_lock:
            self._counts[container_id] = renew_count
        return renew_count

    def _persist_lifecycle_metadata(self, container_id: str, labels: Dict[str, str]) -> None:
        expires_at = None
        renew_count = None
        if EXPIRES_AT_LABEL in labels:
            expires_at = int(labels[EXPIRES_AT_LABEL])
        if RENEW_COUNT_LABEL in labels:
            renew_count = max(0, int(labels[RENEW_COUNT_LABEL]))
        if expires_at is None and renew_count is None:
            return
        try:
            self._lifecycle_store.upsert(
                container_id,
                expires_at=expires_at,
                renew_count=renew_count,
            )
        except Exception as exc:
            logger.warning("持久化容器 %s 生命周期失败: %s", container_id, exc)

    def _update_lifecycle_metadata(self, container_id: str, labels: Dict[str, str]):
        """更新生命周期元数据。

        Docker 容器 labels 在创建后不可变；运行期变更写入进程内缓存与 lifecycle.json。
        创建时写入的 labels 仍作为无持久化记录时的初始值。
        """
        if EXPIRES_AT_LABEL in labels or RENEW_COUNT_LABEL in labels:
            with self._lifecycle_lock:
                if EXPIRES_AT_LABEL in labels:
                    try:
                        self._expires_at[container_id] = int(labels[EXPIRES_AT_LABEL])
                    except (TypeError, ValueError) as exc:
                        logger.warning("容器 %s 的 %s 无效: %s", container_id, EXPIRES_AT_LABEL, exc)
                if RENEW_COUNT_LABEL in labels:
                    try:
                        self._counts[container_id] = max(0, int(labels[RENEW_COUNT_LABEL]))
                    except (TypeError, ValueError) as exc:
                        logger.warning("容器 %s 的 %s 无效: %s", container_id, RENEW_COUNT_LABEL, exc)
        self._persist_lifecycle_metadata(container_id, labels)

    def register_container(self, container: Container, max_time: int, metadata: Optional[Dict[str, Any]] = None):
        """登记容器并设置到期销毁（进程内定时器）。

        名额预留由创建入口统一消费，这里只登记不消耗，避免重复扣减。
        """
        self.add_container(container.id, container, consume_reservation=False)
        self.set_timer(container.id, max_time, container_name=container.name, metadata=metadata)

    def _register_expiry(self, container_id: str, expires_at: int):
        """登记一个到期时间点。

        所有容器的到期时间落在同一个最小堆里，进程内只保留**一个**定时器指向
        最早到期的那个。原来每个容器一个 `threading.Timer`，几百台靶机就是几百个
        常驻线程；改成单定时器后线程占用与容器数无关。
        """
        with self._timers_lock:
            heapq.heappush(self._expiry_heap, (int(expires_at), self._expiry_seq, container_id))
            self._expiry_seq += 1
        self._schedule_next_expiry()

    def _pop_due_expiry(self):
        """弹出堆中仍然有效的到期项；返回 (container_id, expires_at) 或 None。"""
        now = int(time.time())
        with self._timers_lock:
            while self._expiry_heap:
                expires_at, _seq, container_id = self._expiry_heap[0]
                # 惰性删除：续期、销毁、取消都会让堆里的旧条目失效
                if self._expires_at.get(container_id) != expires_at:
                    heapq.heappop(self._expiry_heap)
                    continue
                if expires_at > now:
                    return None
                heapq.heappop(self._expiry_heap)
                return container_id, expires_at
        return None

    def _schedule_next_expiry(self):
        """只保留一个定时器，始终指向堆中最早到期的容器。"""
        with self._timers_lock:
            # 递增代号：并发重调度时，旧定时器到点后发现自己已过期就直接退出，
            # 避免留下多余的常驻线程
            self._timer_generation += 1
            generation = self._timer_generation

            timer = self._timer
            if timer is not None:
                timer.cancel()
                self._timer = None

            # 先清掉堆顶的失效条目
            while self._expiry_heap:
                expires_at, _seq, container_id = self._expiry_heap[0]
                if self._expires_at.get(container_id) == expires_at:
                    break
                heapq.heappop(self._expiry_heap)

            if not self._expiry_heap:
                return

            expires_at, _seq, _container_id = self._expiry_heap[0]
            delay = max(0.0, float(expires_at) - time.time())
            timer = threading.Timer(delay, self._on_expiry_tick, args=[generation])
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _on_expiry_tick(self, generation: int):
        """定时器到点：处理所有已到期的容器并重新调度下一个。

        真正的销毁交给线程池执行，避免一次 Docker 删除卡住整个到期调度。
        """
        with self._timers_lock:
            if generation != self._timer_generation:
                return
        try:
            while True:
                due = self._pop_due_expiry()
                if due is None:
                    break
                container_id, _expires_at = due
                _expiry_executor.submit(self._trigger_destroy, container_id)
        except Exception as exc:  # pragma: no cover - 防御性分支
            logger.error("处理容器到期时发生错误: %s", exc)
        finally:
            self._schedule_next_expiry()

    def set_timer(
        self,
        container_id: str,
        max_time: int,
        container_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """设置容器的销毁定时器（初始设置，不增加续期计数）。

        创建时 labels 写入初始到期时间；运行期变更保存在进程内缓存。
        """
        expires_at = self.compute_expires_at(max_time)
        log_func = logger.debug if not config.DEBUG else logger.info
        log_func("设置容器 %s 的到期销毁时间，将在 %s 秒后销毁。", container_id, max_time)
        self._update_lifecycle_metadata(container_id, {EXPIRES_AT_LABEL: str(expires_at)})
        self._register_expiry(container_id, expires_at)

    def renew(self, container_id: str, max_time: int, max_renew_times: int):
        """续期容器（更新到期时间并增加续期计数）。"""
        container = self.get_container(container_id)
        if container is not None:
            self.ensure_lifecycle_state(container)

        with self._lifecycle_lock:
            current_count = self._counts.get(container_id, 0)
            new_count = current_count + 1

            if new_count > max_renew_times:
                logger.warning(
                    "容器 %s 续期次数已达上限 (%s/%s)，无法续期。",
                    container_id,
                    current_count,
                    max_renew_times,
                )
                raise MaxRenewTimesExceededError(container_id, current_count, max_renew_times)

            self._counts[container_id] = new_count
            logger.debug("容器 %s 续期计数已更新: %s -> %s", container_id, current_count, new_count)

        expires_at = self.compute_expires_at(max_time)
        self._update_lifecycle_metadata(
            container_id,
            {
                EXPIRES_AT_LABEL: str(expires_at),
                RENEW_COUNT_LABEL: str(new_count),
            },
        )

        log_func = logger.debug if not config.DEBUG else logger.info
        log_func(f"容器 {container_id} 续期成功，将在 {max_time} 秒后销毁。")
        self._register_expiry(container_id, expires_at)

    def cancel_timer(self, container_id: str):
        """取消到期销毁定时器。"""
        # 移掉到期时间即可让堆里的旧条目失效（惰性删除），无需在堆中查找
        with self._lifecycle_lock:
            self._expires_at.pop(container_id, None)
        self._schedule_next_expiry()

    def cancel_all_timers(self):
        """取消所有到期销毁定时器。"""
        with self._timers_lock:
            if self._timer is not None:
                try:
                    self._timer.cancel()
                except Exception:
                    pass
                self._timer = None
            self._expiry_heap.clear()
        with self._lifecycle_lock:
            self._expires_at.clear()

    def get_renew_count(self, container_id: str) -> int:
        """获取续期次数。"""
        with self._lifecycle_lock:
            if container_id in self._counts:
                return self._counts[container_id]

        container = self.get_container(container_id)
        if container is not None:
            return self._resolve_renew_count(container)

        persisted = self._read_persisted_lifecycle(container_id) or {}
        return max(0, int(persisted.get("renew_count") or 0))

    def remove_count(self, container_id: str):
        """清理续期计数、到期缓存与持久化记录。"""
        with self._lifecycle_lock:
            self._counts.pop(container_id, None)
            self._expires_at.pop(container_id, None)
        try:
            self._lifecycle_store.remove(container_id)
        except Exception as exc:
            logger.warning("清理容器 %s 生命周期持久化失败: %s", container_id, exc)

    def _trigger_destroy(self, container_id: str):
        """触发销毁回调。"""
        for callback in self._destroy_callbacks:
            try:
                callback(container_id)
            except Exception as e:
                logger.error("执行销毁回调时发生错误: %s", e)

    def restore_timer_from_container(self, container: Container):
        """根据容器标签恢复定时器与续期计数（启动时或 reconcile 使用）。"""
        container_id = container.id
        expires_at = self._resolve_expires_at(container)
        if expires_at is None:
            logger.debug("容器 %s 缺少 %s 标签，跳过自动到期", container_id, EXPIRES_AT_LABEL)
            return

        remaining = expires_at - int(time.time())
        self._resolve_renew_count(container)

        if remaining <= 0:
            logger.info("容器 %s 已过期（expires_at=%s），触发销毁", container_id, expires_at)
            self._trigger_destroy(container_id)
            return

        self._register_expiry(container_id, expires_at)

    def reconcile_managed_containers(self) -> int:
        """扫描 Docker 受管容器，恢复缓存与到期定时器。"""
        try:
            from infra.docker import ensure_client
            from utils.port_utils import collect_host_ports_from_containers, sync_host_ports_from_docker

            client = ensure_client()
            if not client:
                logger.warning("Docker 客户端不可用，跳过容器到期 reconcile")
                return 0

            managed = client.containers.list(all=True, filters={"label": "moegate.managed=true"})
            seen_ids = set()
            for container in managed:
                container_id = container.id
                seen_ids.add(container_id)
                self.add_container(container_id, container, consume_reservation=False)
                self.restore_timer_from_container(container)

            sync_host_ports_from_docker(collect_host_ports_from_containers(managed))

            try:
                self._lifecycle_store.prune(seen_ids)
            except Exception as exc:
                logger.warning("清理 lifecycle.json 过期记录失败: %s", exc)

            try:
                from services.container.tap import reconcile_taps

                reconcile_taps()
            except Exception as exc:
                logger.debug("流量取证 reconcile 失败: %s", exc)

            logger.info("容器到期 reconcile 完成，受管容器数: %d", len(seen_ids))
            return len(seen_ids)
        except Exception as exc:
            logger.error("容器到期 reconcile 失败: %s", exc)
            return 0

    def _reconcile_loop(self):
        interval = max(30, int(getattr(config, "EXPIRE_RECONCILE_INTERVAL_SEC", 60) or 60))
        while self._reconcile_running:
            try:
                self.reconcile_managed_containers()
            except Exception as exc:
                logger.error("容器到期 reconcile 循环错误: %s", exc)
            for _ in range(interval):
                if not self._reconcile_running:
                    break
                time.sleep(1)

    def start_reconcile_worker(self):
        """启动后台 reconcile 线程（启动时重建定时器 + 周期性校验）。"""
        with self._reconcile_lock:
            if self._reconcile_running:
                return
            self._reconcile_running = True
            self._reconcile_thread = threading.Thread(
                target=self._reconcile_loop,
                daemon=True,
                name="ContainerExpireReconcile",
            )
            self._reconcile_thread.start()
            logger.info("容器到期 reconcile 线程已启动")

    def stop_reconcile_worker(self):
        """停止后台 reconcile 线程。"""
        with self._reconcile_lock:
            self._reconcile_running = False
            thread = self._reconcile_thread
        if thread and thread.is_alive():
            thread.join(timeout=5)


_container_manager: Optional[ContainerManager] = None
_manager_lock = threading.Lock()


def get_container_manager() -> ContainerManager:
    """获取容器管理器单例。"""
    global _container_manager
    if _container_manager is None:
        with _manager_lock:
            if _container_manager is None:
                _container_manager = ContainerManager()
    return _container_manager


def shutdown_expiry_executor(wait: bool = True) -> None:
    """关闭到期销毁执行池（进程退出前调用）。"""
    try:
        _expiry_executor.shutdown(wait=wait)
    except Exception as exc:
        logger.debug("关闭到期执行池失败: %s", exc)

# 并发模型与关键契约

MoeGate 是单进程多线程服务：Flask 请求线程、后台 reconcile 线程、到期调度线程、
销毁线程池会同时操作同一批 Docker 资源。下面记录各处加锁的原因，以及几条**不能随意改**
的契约——这些都是排查"偶发失败"时最先要对齐的地方。

## 线程与执行器

| 角色 | 位置 | 说明 |
|------|------|------|
| 请求线程 | Flask | 创建/续期/销毁容器，全部走 `services/container/lifecycle.py` |
| reconcile 线程 | `ContainerManager.start_reconcile_worker` | 周期扫描受管容器，重建缓存与到期时间 |
| 到期调度定时器 | `ContainerManager._schedule_next_expiry` | 全局**只有一个**，指向最早到期的容器 |
| 到期执行池 | `container_manager._expiry_executor` | 真正跑销毁回调，避免慢 Docker 调用卡住调度 |
| 销毁任务池 | `utils/destroy.py::_destroy_executor` | 异步销毁容器，带任务状态与去重 |
| 清理任务池 | `utils/destroy.py::_cleanup_executor` | Compose 项目网络清理 |

## 契约一：容器名额由创建入口统一消费

`check_and_reserve` 会同时占用两块资源：跨进程文件锁里的预留（`utils/quota_store.py`）
和进程内的 `_pending_count`。**释放必须由调用 `check_and_reserve` 的那一方负责**，
也就是 `lifecycle.start_container` / `start_container_streaming`：

- 成功 → `manager.consume_reservation(slots=slots)`
- 失败 → `manager.release_reservation(slots=slots)`（`try/except` 里）

容器登记（`register_container` / `add_container`）**不消耗名额**。历史上单容器路径靠
`add_container(consume_reservation=True)` 隐式扣减，结果跨进程预留永远没人释放，
只能等 600 秒 TTL 过期——并发开考时会大面积误报"容器数超限"。现在两条路径一致。

## 契约二：端口靠"预留"互斥，且有 TTL 兜底

`utils/port_utils.py` 里 `_allocating_ports` 记录"已分配但容器尚未绑定"的端口，
其他线程不会选中它们。两点约束：

- 候选的 socket 探测**放在锁外**执行。这是最慢的一步，放在锁里会把所有分配请求串行堵住。
- 预留带 600 秒 TTL。异常路径漏掉 `release_port` 时最多影响 10 分钟，
  不会像以前那样把端口永久占死。

探测失败的端口进 `_blocked_ports` 短期拉黑，避免在端口池较满时反复重试同一个端口。

## 契约三：到期销毁用单一调度器

几百台靶机如果每台一个 `threading.Timer`，就是几百个常驻线程。现在所有到期时间放在一个
最小堆里，只保留一个定时器指向堆顶（最早到期）：

- 续期、销毁、取消定时器都会让堆里的旧条目失效，采用惰性删除（弹出时校验）；
- 调度代号（`_timer_generation`）保证并发重调度时不会留下多余的定时器线程；
- 到期后在**线程池**里执行销毁回调，一次慢删除不会阻塞后续容器的到期处理；
- reconcile 仍会周期性兜底，即使定时器出问题也不会漏销毁。

## 契约四：查不到占用就拒绝，不能当成 0

`ContainerManager._docker_managed_count()` 用 **-1** 表示"查不出来"（Docker 不可用、
从未成功查询过且没有上次结果）。`check_and_reserve` 遇到 -1 **直接拒绝创建**：

- 把 -1 当 0 会把配额算得极其宽松，多副本并发开考时必然超额下发；
- 查不出真实占用说明 Docker 链路已经异常，此时放行没有任何意义。

## 契约五：Docker 客户端不能在别人用时被关闭

`infra/docker.py` 的 `ensure_client()` 全程在锁内取值。健康检查失败时，旧客户端进入
退役队列**延迟 60 秒**关闭，而不是立即 `close()`——否则正在用它发请求的线程会中途失败。

## 其他锁的职责边界

| 锁 | 保护对象 |
|----|----------|
| `ContainerManager._containers_lock` | `_containers` 与 `_pending_count` |
| `ContainerManager._lifecycle_lock` | `_counts` 与 `_expires_at`（必须同一把：续期会同时改两者） |
| `ContainerManager._timers_lock` | 到期堆与调度定时器 |
| `ContainerManager._managed_count_lock` | Docker 受管容器数量的 2 秒 TTL 缓存 |
| `port_utils._port_allocation_lock` | 端口预留、拉黑集合、Docker 同步端口 |
| `tap._TAP_LOCK` | sidecar 的"清残留 → 创建"关键区（sidecar 名按靶机 id 固定，并发会撞名） |
| `quota_store._file_lock` | 跨进程配额文件 |

## 已知的取舍

- 受管容器数量有 2 秒缓存：本进程新建的部分由 `_pending_count` 覆盖，
  跨进程由配额文件锁覆盖，所以短缓存不会导致超额。
- 到期销毁是异步的：定时器到点后由线程池执行，不保证"到点即删"的严格时序。
- 取证 sidecar 的创建是串行的（同一把锁）：compose 多 service 时会略微增加创建耗时，
  换来的是不会出现孤儿 sidecar。

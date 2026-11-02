# 流量取证（Traffic Tap）

为动态靶机抓取完整流量并落盘为 pcap，用于考核复盘、异常行为分析与争议仲裁。

## 能力边界

| 能看到 | 看不到 |
|--------|--------|
| 靶机的全部进出报文（HTTP 明文、SQL 注入 payload、扫描行为） | 学生本机屏幕、键盘、浏览器历史 |
| 请求时间、顺序、频率、User-Agent、路径 | 学生在自己机器上复制题面的动作 |
| 同一学生多个靶机之间的横向访问 | 加密（HTTPS）会话的正文，只能看到 TLS 元信息 |
| 谁在什么时间对哪个容器做了什么请求 | 端口映射场景下的真实来源 IP（被 Docker NAT 掉了） |

**核心价值**：动态 flag 只能从靶机内部取，所以任何"外部工具代做"最终都会以**请求**的形式落在靶机网卡上——
工具类 User-Agent、机器化的请求节奏、异常高频的路径探测、逐字节相同的 payload，都是可复核的证据。

## 工作原理

MoeGate 在靶机启动后追加一个 sidecar 容器：

```
靶机容器 (netns)  ←── network_mode: container:<target_id> ──  取证 sidecar (tcpdump)
                                                                      │
                                              写 /capture/<capture_key>/traffic-<epoch>.pcapN
                                                                      │
                                               Docker 卷 moegate-captures（MoeGate 只读挂载）
```

- **每个靶机一个子目录**（`capture_key`：compose 项目为 `<project>__<service>`，单机为容器名）。
  Docker 卷模式下整卷挂在 `/capture` 上，sidecar 自己 `mkdir -p` 出这个子目录再写；
  少这一层的话所有靶机的 pcap 会平铺在卷根，既无法归属，读取侧也永远找不到文件。

- **共享网络命名空间**，而不是网桥镜像：不需要宿主机 NET_ADMIN / iptables TEE，只有 docker.sock 权限也能用，且能看到 lo 上的流量。
- sidecar 只加 `NET_ADMIN` + `NET_RAW`，内存默认 128MB；不写 `moegate.managed=true`，**不占学生容器配额**、不出现在容器列表里。
- pcap 按会话命名（`traffic-<毫秒时间戳>-<随机后缀>.pcapN`），同一秒内 stop/start 或重复点击「开始抓包」不会复用文件名、不会覆盖上一轮证据。
- 单个 tcpdump 进程按 64MB 轮转、最多保留 8 个文件（约 512MB）；**每次重启/手动开始都会新开一组文件名**，多轮会话会累积到保留期（`TRAFFIC_CAPTURE_RETENTION_HOURS`）为止。请按考试场次预留磁盘，并监控取证目录占用。

## 部署

### 1. 构建取证镜像

```bash
docker build -t moegate-tap:latest deploy/tap
```

MoeGate 启动容器时若发现镜像缺失，也会用 `deploy/tap/Dockerfile` 自动构建一次（需要能访问 apk 源）。
离线环境请提前构建并 `docker save` / `docker load` 分发。

### 2. 开启开关

```env
ENABLE_TRAFFIC_CAPTURE=true
TRAFFIC_CAPTURE_VOLUME=moegate-captures
TRAFFIC_CAPTURE_DIR=/data/captures
```

`docker-compose.yml` 已内置 `moegate-captures` 卷并挂到 `/data/captures`，直接复用即可。
卷定义带了显式 `name: moegate-captures`，避免 Compose 自动加项目前缀；MoeGate 在启动 sidecar 时
还会从自身容器的 `Mounts` 里解析实际卷名，二者不一致时以实际挂载为准（并在日志里提示）。

> ⚠️ **卷模式下 MoeGate 必须自己挂载同一个卷。** sidecar 写进卷里，MoeGate 按
> `TRAFFIC_CAPTURE_DIR` 读；如果 MoeGate 跑在容器外（裸机/Windows），卷在 Docker 的 VM 里，
> 宿主机根本读不到——表现是"sidecar 在录制，文件列表始终是 0"。启动日志会打印一行
> `读不到取证根目录` 的警告，取证面板顶部也会直接给出提示。

裸机部署（不走容器）时改用宿主机路径：

```env
TRAFFIC_CAPTURE_VOLUME=
TRAFFIC_CAPTURE_HOST_DIR=/opt/moegate/captures
```

（配了 `HOST_DIR` 后它就是 MoeGate 的读取路径，`TRAFFIC_CAPTURE_DIR` 可留默认值。）

### 3. 验证

```bash
# 创建靶机后，确认 sidecar 已起来（注意它带 moegate.tap=true 标签）
docker ps --filter label=moegate.tap=true

# 查看取证状态与文件
curl -s -H "X-API-Key: $KEY" \
  http://localhost:8080/api/v1/containers/<container_uuid>/traffic
```

## 配置项

| 变量 | 默认 | 说明 |
|------|------|------|
| `ENABLE_TRAFFIC_CAPTURE` | `false` | 总开关（关掉则任何容器都不抓） |
| `TRAFFIC_CAPTURE_DEFAULT` | `false` | 总开关打开后，未显式指定 `traffic_capture` 的容器默认是否抓 |
| `TRAFFIC_CAPTURE_IMAGE` | `moegate-tap:latest` | sidecar 镜像 |
| `TRAFFIC_CAPTURE_VOLUME` | `moegate-captures` | Docker 卷名（与 `HOST_DIR` 二选一） |
| `TRAFFIC_CAPTURE_HOST_DIR` | 空 | 宿主机绝对路径 |
| `TRAFFIC_CAPTURE_DIR` | `/data/captures` | MoeGate 读取 pcap 的目录；配了 `HOST_DIR` 时以 `HOST_DIR` 为准 |
| `TRAFFIC_CAPTURE_SNAPLEN` | `0` | `0` 抓完整报文；`256` 只抓头部省 IO |
| `TRAFFIC_CAPTURE_ROTATE_MB` | `64` | 轮转大小 |
| `TRAFFIC_CAPTURE_MAX_FILES` | `8` | 最多保留文件数 |
| `TRAFFIC_CAPTURE_FILTER` | 空 | 额外 BPF 表达式，如 `not port 22` |
| `TRAFFIC_CAPTURE_RETENTION_HOURS` | `168` | pcap 保留时长，`0` 不清理 |
| `TRAFFIC_CAPTURE_QUOTA_MB` | `1024` | 每个靶机/service 的 pcap 总量上限，超出后删最旧文件；`0` 不限制。正在录制的靶机会跳过配额清理 |
| `TRAFFIC_CAPTURE_MEMORY_LIMIT` | `128m` | sidecar 内存上限 |
## 按参数控制是否抓包

抓包有两层开关，互不冲突：

| 层级 | 手段 | 生效范围 | 典型用途 |
|------|------|----------|----------|
| 平台级 | `ENABLE_TRAFFIC_CAPTURE` | 整个实例 | 是否具备取证能力 |
| 容器级 | 创建参数 `traffic_capture` | 单台靶机（写入标签 `moegate.traffic_capture=on/off`） | 只录考试场次 |
| 运行时 | `POST .../traffic/start` `/stop` | 停止状态持久生效；手动 start 清除停止标记 | 临时补录 / 立即停录 |

默认姿态：**能力可开、默认不录、按场次显式开**。

```env
ENABLE_TRAFFIC_CAPTURE=true
TRAFFIC_CAPTURE_DEFAULT=false
```

创建靶机时显式开启：

```bash
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"image":"ctf/web:latest","traffic_capture":true}'
```

| 取值 | 行为 |
|------|------|
| 不传 | 走 `TRAFFIC_CAPTURE_DEFAULT` |
| `true` / `"true"` | 强制抓包；若平台没开 `ENABLE_TRAFFIC_CAPTURE`，请求直接 400，**不会静默降级** |
| `false` / `"false"` | 本靶机不抓，连 sidecar 都不创建，零额外资源 |
| 其他值 | 400，`traffic_capture 取值非法` |

要点：

- 标签落在**靶机**上而非 sidecar 上，所以靶机重启、MoeGate 重启、`reconcile_taps()` 补齐时都以标签为准，不会被"补抓"逻辑偷偷打开。
- Docker 标签创建后不可变，因此 `POST .../traffic/start` 的强制开启只在**本次 sidecar 生命周期**内有效；靶机重启后回到创建参数决定的策略。需要持久开启请在创建时就传 `traffic_capture: true`。
- `POST .../traffic/stop` 的停止状态会写入 `captures.json`，`reconcile_taps()` 不会在下一轮把 sidecar 建回来（避免"管理员已停录、平台却又偷偷录"）；再次 `POST .../traffic/start` 会清除该标记。
- 靶机销毁后，pcap 与「容器 → 取证目录」的映射仍保留：`/traffic`、`/traffic/summary` 和下载接口继续可用，直到保留期清理。
- 关闭抓包的靶机在创建响应里是 `"traffic_capture": {"enabled": false}`，WebUI 与 API 都不会把"没录"说成"已录"。

## Docker Compose 项目怎么录

**做法**：创建请求照常传 `traffic_capture: true`，它会对**项目下的每个 service 生效**——
每个 service 各起一个 sidecar，pcap 落在 `<compose_project_id>__<service>/` 目录：

```bash
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"path":"web-cluster","traffic_capture":true}'
```

```
captures/
├── 6c96bebe__web/traffic-1793584198.pcap0     # 学生访问入口 service
├── 6c96bebe__api/traffic-1793584199.pcap0     # web 调用 api 的内部流量
└── 6c96bebe__db/traffic-1793584200.pcap0      # api 查库
```

生命周期都已接好：项目重启（逐个 `container.restart()`）会重建各自的 tap，
销毁项目会逐个停 tap 并保留 pcap。

**为什么不能"一个 sidecar 抓整个项目"**：

- 共享 netns（`network_mode: container:<id>`）本质是一对一的，一个 netns 只能绑一个容器；
- 想在项目网络上抓也不行：**同一个 bridge 内容器互访是二层直连，不经过宿主机网桥**，
  桥上只能看到进出宿主机的南北向流量，看不到 service 之间（web → api → db）的会话；
- 所以 per-service 是唯一能覆盖内部流量的方案。

**代价与取舍**：

- 服务间通信会被两端各抓一次（同一条会话在 web 和 api 的 pcap 里各一份），按时间戳对齐即可；
- 磁盘随 service 数线性增长：每 service 上限 `64MB × 8 ≈ 512MB`，3-service 项目约 1.5GB；
- 参数目前是**请求级**的，无法只录某一个 service。可行的替代：
  用 `TRAFFIC_CAPTURE_FILTER` 配 BPF 只留关心的端口（如 `port 8080`，全局生效），
  或者对该项目先不录音、事后对关心的容器 `POST /containers/<id>/traffic/start` 单独补录。

**内部流量要能被录到，项目必须声明自定义网络**。MoeGate 只会为 compose 里显式声明的
`networks` 建网；如果 `docker-compose.yml` 没有 `networks:` 段，容器会落到默认 bridge 上，
按容器名互访都不通，自然也没什么内部流量可录。所以:

```yaml
services:
  web:
    image: ctf/web
    networks: [ctfnet]
  api:
    image: ctf/api
    networks: [ctfnet]
networks:
  ctfnet:
```

**实测**（2-service 项目，web 暴露 3000、api 仅内网可见；宿主机打 web 4 次，再从 web 内部打 api 4 次）：

```
1793588644__web/traffic-1793588647.pcap0   53660 bytes   90 packets   8 条 HTTP   2 个客户端
1793588644__api/traffic-1793588647.pcap0   26412 bytes   43 packets   4 条 HTTP   1 个客户端
```

- web 侧 8 条 = 4 条南北向 + 4 条东西向（它自己发出的请求也被自己录到）；
- api 侧只有 4 条东西向——**这段会话在宿主机网桥上是抓不到的**，只有 per-service sidecar 能看到；
- 两组 pcap 里那 4 条东西向是同一批请求，做时间线对齐时要去重。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/containers/<id>/traffic` | 取证状态 + 文件列表 + 总大小 |
| `GET` | `/api/v1/containers/<id>/traffic/summary` | 解析 pcap 生成摘要（可加 `?max_packets=50000&max_http=200`） |
| `GET` | `/api/v1/containers/<id>/traffic/<filename>` | 下载单个 pcap |
| `POST` | `/api/v1/containers/<id>/traffic/start` | 手动开启（可覆盖 `traffic_capture=false`，仅本次运行有效；同时清除停止标记） |
| `POST` | `/api/v1/containers/<id>/traffic/stop` | 停止抓包并持久化停止状态，**已落盘文件保留** |

状态里的排障字段：`storage_mode`（`volume` / `host`）、`capture_root`、`readable`（MoeGate 能否读到根目录）、
`target_exists`（靶机容器是否还在）、`stopped`（是否被管理员显式停止）、`hint`（一句可执行的排查结论，
正常落盘或已有留存文件时为空字符串）。
`hint` 优先描述实际状态：sidecar 正在录时不会因为创建参数为 `off` 而误报"不会抓包"。

容器销毁后，状态与下载仍按持久化映射工作（`target_exists=false`）；`summary` 在部分文件损坏时会返回
`message` 说明，而不是 `ok`。

> 取证数据的读取会被审计：`/traffic`、`/traffic/summary`、`/traffic/<filename>` 以及 `/logs`、`/logs/stream`
> 都会写入 `moegate.audit`（含来源 IP、request_id、路径），便于回答"谁在什么时候导出了证据"。

`summary` 返回结构（节选）：

```json
{
  "summary": {
    "packets": 18342,
    "first_seen": "2026-11-02T10:00:03",
    "last_seen": "2026-11-02T10:41:55",
    "clients": [
      {
        "ip": "172.17.0.1",
        "requests": 214,
        "median_interval_ms": 87.5,
        "peak_requests_per_minute": 120,
        "user_agents": ["python-requests/2.31.0"],
        "sample_paths": ["/login.php", "/upload.php?id=1' or 1=1-- -"]
      }
    ],
    "signals": {
      "automation_user_agents": ["python-requests/2.31.0"],
      "automation_clients": ["172.17.0.1"],
      "min_median_request_interval_ms": 87.5,
      "peak_requests_per_minute": 120
    }
  }
}
```

## WebUI 取证面板

容器卡片上的 **取证** 按钮打开面板（`frontend/src/components/container/TrafficForensicsModal.vue`）：

- **取证状态**：录制中 / 未录制、策略来源（显式指定 or 默认）、文件数与总大小、`停止抓包 / 开始抓包 / 刷新`；
- **pcap 文件**：文件列表（大小、修改时间）与逐个下载；
- **生成摘要**：流量概览（报文数、时间范围、请求数、峰值与中位间隔）、客户端画像表、请求时间线
  （时间 / 方法 / 路径 / User-Agent，最多 200 条）。

创建容器时在「基础参数 → 流量取证」可选 **跟随服务端默认 / 录制 / 不录制**，对应请求体的 `traffic_capture`。

面板只呈现可复核的事实，**不做评分、不判"可疑"**：判断留给看 pcap 的人。

## 取证工作流

**1. 先读事实，再下判断**

`signals` 只给事实，不给结论：

- `automation_user_agents` / `automation_clients`：命中的工具型 UA（`python-requests` / `curl` / `HeadlessChrome` / `Playwright`…）与对应客户端；
- `min_median_request_interval_ms`：请求中位间隔，人手点页面通常 500ms 以上；
- `peak_requests_per_minute`：一分钟内的最大请求数。

典型对照：没有目录爆破、没有 404 试错就直接命中漏洞点，说明访问者对题目结构早有预期；
不同学生 pcap 里出现**逐字节相同的 payload**，说明内容是复制的而不是各自构造的。

**2. 复核**

下载 pcap 用 Wireshark 打开（`http.request` 过滤器），完整还原访问路径，比看日志可靠。
所有结论请以 pcap 原文为准——平台不给分数，也不做定性。

## 局限与注意事项

- **端口映射会把源 IP NAT 成网桥网关**。因此身份归属要靠"容器 ↔ 学生"的绑定关系，不能靠 pcap 里的 IP。
  需要真实源 IP 时，在宿主机对 `docker0` 做 iptables TEE 镜像到独立网卡，再让 sidecar 抓该网卡（改动更大，按需启用）。
- **HTTPS 抓不到正文**。CTF 靶机以 HTTP 为主，若题目走 HTTPS，摘要里的路径会是空的，只剩连接元信息。
- **pcap 是敏感数据**，包含学生全部请求内容。建议 `TRAFFIC_CAPTURE_RETENTION_HOURS` 设成考试周期 + 申诉窗口；
  导出接口只对管理员开放，`moegate.audit` 会记录 pcap 与日志的读取。
- 单个 tcpdump 进程默认最多占 512MB 磁盘；`TRAFFIC_CAPTURE_QUOTA_MB`（默认 1024）会按靶机/service
  限制多轮会话的 pcap 总量，超出后 reconcile 删最旧文件；正在录制的靶机会跳过，避免删掉 tcpdump 打开的 inode。
- 关闭开关后不会再启动新 tap，但已有 tap 需 `POST .../traffic/stop` 或销毁容器才会退出；保留期清理与配额清理会继续执行。
- 摘要按 **TCP 流重组**尽力解析 HTTP：请求行/请求头跨段、pipelined 请求、Content-Length 主体已处理；
  HTTPS 正文、抓包截断导致首段丢失等情况仍可能漏计，关键争议请下载 pcap 用 Wireshark 复核。
  IPv6 逐跳/路由/目的选项/分片扩展头已支持跳过，UA 识别包含 busybox `Wget`。
- 摘要中的时间使用 MoeGate 进程本地时区（无偏移量），跨时区比对请统一到 UTC 或同时参考 pcap 内的时间戳。

## 故障排查

| 现象 | 排查 |
|------|------|
| 创建容器后没有 tap | 看日志是否有"启动流量取证失败"；确认 `ENABLE_TRAFFIC_CAPTURE=true` |
| tap 在跑但文件列表始终为 0 | 看状态里的 `hint`：多数是 MoeGate 与 sidecar 没共享存储（卷模式要求 MoeGate 也挂该卷，裸机请设 `TRAFFIC_CAPTURE_HOST_DIR`） |
| 有 tap 但目录为空 | 容器没有流量，或 BPF 过滤表达式写错 |
| tap 容器 Exited / 状态显示未运行 | 看 sidecar 日志（`docker logs moegate-tap-<id>`）；BPF 写错、镜像缺 tcpdump 都会导致秒退。reconcile 会移除失效 tap 并按策略重建 |
| 容器销毁后下载 404 | 升级到含 `captures.json` 的版本；确认使用创建时返回的容器 UUID/名称，且文件未被保留期清理 |
| compose 部署下文件列表一直为空 | 确认 MoeGate 与 sidecar 挂的是同一个卷；新版本会显式 `name: moegate-captures` 并从自身 Mounts 解析实际卷名 |
| pcap 平铺在卷根、没有子目录 | 旧版本遗留：sidecar 未写进 `<capture_key>/`，升级后重启靶机即可，旧文件无法归属靶机 |
| 下载 404 | 确认 `TRAFFIC_CAPTURE_DIR` 与卷挂载点一致（容器外路径 vs 容器内路径） |
| `summary` 报 pcap 解析失败 | 文件正在写入被截断，稍后重试；或 `SNAPLEN` 过小导致头部缺失 |
| 镜像构建失败 | 离线环境手动 `docker build -t moegate-tap:latest deploy/tap` |

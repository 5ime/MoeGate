# API 文档

基础路径为 `/api/v1`。除探活端点外，所有 `/api/v1/*` 接口均需认证。

## 认证

支持两种方式（二选一，权限等效）：

| 方式 | 适用场景 | 说明 |
|------|----------|------|
| **Header** | curl、自动化脚本 | 请求头携带 `X-API-Key` |
| **Cookie** | WebUI | 登录后写入 HttpOnly Session Cookie，API Key 不进入 JavaScript |

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/auth/login` | 使用 `{"api_key": "..."}` 登录，写入 Session Cookie |
| `POST` | `/api/v1/auth/logout` | 退出登录：清 Cookie **并在服务端吊销该会话** |
| `DELETE` | `/api/v1/auth/session` | 吊销当前会话（等价带鉴权的 logout） |
| `POST` | `/api/v1/auth/logout-all` | 吊销全部已签发会话（需鉴权；轮换 API Key 后使用） |
| `GET` | `/api/v1/auth/session` | 查询当前登录状态 |

Session Cookie 是无状态签名串，仅清浏览器 Cookie **不会**让已泄露的 Cookie 失效。
`logout` / `DELETE /auth/session` 会在服务端吊销当前会话，`logout-all` 直接作废所有已签发会话。
吊销记录仅在当前进程内生效，多实例部署需对每个副本调用 `logout-all`（或重启）。

Cookie 模式下，变更类请求（POST/PUT/PATCH/DELETE）还须携带 `X-CSRF-Token` 请求头（与 `moegate_csrf` Cookie 值一致）。使用 `X-API-Key` 的脚本调用不受 CSRF 约束。详见 [SECURITY.md](SECURITY.md)。

`GET /api/v1/auth/session` 与 `POST /api/v1/auth/login` 成功时，响应 `data.csrf_token` 与 `moegate_csrf` Cookie 可用于后续变更请求。

## 响应格式

成功与失败均返回 JSON：

```json
{"code": 200, "msg": "说明", "data": {}}
```

- `code`：HTTP 状态码（与响应状态一致）
- `msg`：人类可读说明
- `data`：业务数据（部分接口可为 `null` 或省略）

## 请求头（可选）

| 请求头 | 说明 |
|--------|------|
| `X-User-Id` / `X-Operator-Id` | 创建容器时写入 label `moegate.created_by`，便于审计追溯 |
| `X-Request-Id` | 客户端可传入；未提供时服务端自动生成并回写响应头 |

## 探活与监控

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/healthz` | 无 | Liveness 探针，仅返回 HTTP 200/503 |
| `GET` | `/metrics` | `X-Metrics-Token` | Prometheus 抓取；端点可见条件为 `ENABLE_PUBLIC_METRICS=true` 或已配置 `METRICS_TOKEN`，访问时 token 必填 |
| `GET` | `/api/v1/metrics` | 是 | WebUI 用 Prometheus 文本指标（API Key / Session） |

## 容器

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/containers` | 创建容器 |
| `POST` | `/api/v1/containers/stream` | 创建容器（SSE 流式） |
| `GET` | `/api/v1/containers` | 容器列表 |
| `GET` | `/api/v1/containers/<id>` | 容器详情 |
| `PATCH` | `/api/v1/containers/<id>` | 重启容器 |
| `DELETE` | `/api/v1/containers/<id>` | 删除容器（异步，**HTTP 202**） |
| `GET` | `/api/v1/containers/<id>/destroy-status` | 删除任务状态 |
| `POST` | `/api/v1/containers/<id>/renew` | 续期 |
| `GET` | `/api/v1/containers/<id>/logs` | 容器日志快照（stdout + stderr），见下方 [容器日志](#容器日志) |
| `GET` | `/api/v1/containers/<id>/logs/stream` | 容器日志 SSE 流式跟随（先补历史再持续推送） |

### 统一入口

自动识别单容器或 Compose 项目：

| 方法 | 路径 | 说明 |
|------|------|------|
| `PATCH` | `/api/v1/containers/restart/<id>` | 重启 |
| `DELETE` | `/api/v1/containers/destroy/<id>` | 删除（异步，**HTTP 202**） |
| `POST` | `/api/v1/containers/renew/<id>` | 续期（按当前 `MAX_TIME` 延长，受 `MAX_RENEW_TIMES` 限制） |

### Compose 项目

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/containers/project/<id>` | 项目详情 |
| `PATCH` | `/api/v1/containers/project/<id>` | 重启项目 |
| `DELETE` | `/api/v1/containers/project/<id>` | 删除项目（异步，**HTTP 202**） |
| `GET` | `/api/v1/containers/project/<id>/destroy-status` | 删除状态 |
| `POST` | `/api/v1/containers/project/<id>/renew` | 续期项目 |

**续期与到期时间**：创建时写入容器 labels（`moegate.expires_at`、`moegate.renew_count`）；因 Docker labels 创建后不可变，续期后的变更会写入 `ALLOWED_BASE_DIR/.moegate/lifecycle.json`，供进程重启后恢复定时器。续期时长固定为当前配置的 `MAX_TIME`（不可在续期请求中单独指定）。详见 [deploy.md](deploy.md#容器生命周期持久化)。

**详情查询**：`GET /api/v1/containers/<id>`、`GET /api/v1/containers/project/<id>`、`GET /api/v1/images/detail/<ref>` 支持 `?verbose=true`，返回完整 `environment` / Docker `attrs`；默认仅返回 `environment_keys` 等摘要字段。

**删除任务状态**：`destroy-status` 返回 `status`（`pending` / `running` / `success` / `failed` / `not_found`）及时间戳字段。

### 容器日志

`GET /api/v1/containers/<id>/logs` 读取**受管容器**的 stdout + stderr：

| 参数 | 默认 | 说明 |
|------|------|------|
| `tail` | `200` | 从末尾取多少行，上限 `5000` |
| `timestamps` | `false` | 是否保留 docker 时间戳前缀 |
| `since` | 空 | 只返回该 Unix 秒级时间戳之后的日志 |

```bash
curl -s -H "X-API-Key: <key>" \
  "http://localhost:8080/api/v1/containers/<container_uuid>/logs?tail=500&timestamps=true"
```

响应：`lines`（已按行拆分）、`line_count`、`truncated`、`container_name` 等。

#### 流式跟随（SSE）

`GET /api/v1/containers/<id>/logs/stream` 以 SSE（`text/event-stream`）返回：先推送 `tail` 行历史，再持续推送新增日志，直到超时或客户端断开。

| 参数 | 默认 | 说明 |
|------|------|------|
| `tail` | `100` | 先补多少行历史，上限 `5000` |
| `timestamps` | `false` | 是否保留 docker 时间戳前缀 |
| `max_seconds` | `300` | 最长跟随秒数，上限 `3600` |
| `max_lines` | `5000` | 本次连接最多推送行数，上限 `20000` |

```bash
curl -N -H "X-API-Key: <key>" \
  "http://localhost:8080/api/v1/containers/<container_uuid>/logs/stream?tail=200&max_seconds=600"
```

事件类型（与其它 SSE 接口一致，由 `core/sse_helpers.py` 统一产出）：

| 事件 | 说明 |
|------|------|
| `log` | 一行日志，`data` 为该行文本 |
| `error` | 出错，`data` 为 `{"msg": ..., "code": ...}`；发完后服务端关闭连接 |
| `result` | 不会出现在本接口（仅创建/构建类 SSE 的收尾结果） |

服务端到达 `max_seconds` / `max_lines` 时直接关闭流，不发终止事件；前端据此认为"本次跟随正常结束"，可再次连接继续跟随。`max_seconds` 由服务端本地计时强制生效——即使容器长时间没有新日志（Docker 在无新数据时不会主动检查 `until`）也会按时关闭，不会永久占用连接。超长行按 `SSE_MAX_LOG_LINE_LENGTH`（默认 2000 字符）截断并追加 `... [truncated]`。

前端实现见 `frontend/src/composables/useContainerLogs.js`：`fetch` + `response.body.getReader()` 逐块解析 `event:` / `data:`，退出时 `AbortController.abort()` 断开。

#### 共同约束

- 只服务带 `moegate.managed=true` 标签的容器，其它容器一律按不存在处理（404）
- 非 TTY 容器的 docker 日志是带 8 字节帧头的多路复用流，接口已解帧，不会返回二进制噪声；`tail` 按字节偏移定位可能落在帧中间，已做帧头校验与前向重新同步，不会吞掉行首字符
- 快照单次返回上限 512KB，超出保留**尾部**并置 `truncated: true`（调小 `tail` 或到宿主机看完整日志）
- 多容器项目里每个 service 都是独立容器，对各自容器 ID 调用即可
- 流式接口内部按 5 秒为窗口滚动续拉：快照与 follow 都用内部时间戳去重，传 `since` 不会把历史重放一遍；窗口以当前时间为基准，空闲容器也不会空转或漏读
- 日志读取（`/logs`、`/logs/stream`）属于证据访问，会写入 `moegate.audit` 审计日志（含来源 IP、request_id、路径）

### 流量取证

需 `ENABLE_TRAFFIC_CAPTURE=true`，详见 [traffic-capture.md](traffic-capture.md)。

创建容器时可用请求体参数 `traffic_capture`（`true` / `false`，不传走 `TRAFFIC_CAPTURE_DEFAULT`）决定该靶机是否抓包；该值写入标签 `moegate.traffic_capture`，重启与 reconcile 都以标签为准。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/containers/<id>/traffic` | 取证状态（`policy` / `requested` / `running` / `stopped` / `target_exists`）+ pcap 文件列表 |
| `GET` | `/api/v1/containers/<id>/traffic/summary` | pcap 摘要，支持 `?max_packets=50000&max_http=200` |
| `GET` | `/api/v1/containers/<id>/traffic/<filename>` | 下载单个 pcap（`application/vnd.tcpdump.pcap`） |
| `POST` | `/api/v1/containers/<id>/traffic/start` | 手动开启（可强制覆盖 `traffic_capture=false`，仅本次 sidecar 有效） |
| `POST` | `/api/v1/containers/<id>/traffic/stop` | 停止抓包（写入持久停止状态，reconcile 不会自动重启），已落盘文件保留 |

`summary` 的 `signals` 字段给出可复核的事实统计（工具型 UA、请求量、节奏、峰值）：`automation_user_agents`、`automation_clients`、`min_median_request_interval_ms`、`peak_requests_per_minute`。`summary["files"]` 列出参与聚合的 pcap；存在无法解析的文件时 `message` 会给出说明，而不是笼统的 `ok`。

容器销毁后 `captures.json` 仍保留「容器 ID/名称 → capture_key」映射：`traffic` 状态、`summary` 与 pcap 下载在靶机被自动销毁后依然可用（直到 `TRAFFIC_CAPTURE_RETENTION_HOURS` 到期清理）。此时 `target_exists` 为 `false`，`running` 为 `false`。

`traffic` 与 `traffic/<filename>` 属于证据导出，GET 请求也会写入 `moegate.audit` 审计日志。

## 镜像

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/images` | 受管镜像列表 |
| `GET` | `/api/v1/images/detail/<ref>` | 镜像详情 |
| `POST` | `/api/v1/images/pull` | 拉取镜像 |
| `POST` | `/api/v1/images/pull/stream` | 拉取镜像（SSE） |
| `DELETE` | `/api/v1/images/<ref>` | 删除镜像（`?force=true` 强制） |
| `POST` | `/api/v1/images/prune` | 清理悬空镜像 |

受管镜像由 MoeGate 在拉取/构建时登记；列表与删除仅针对已登记记录。删除时 `?force=true` 可强制删除仍被引用的镜像。

## 网络

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/networks` | 受管网络列表 |
| `GET` | `/api/v1/networks/<id>` | 网络详情 |
| `POST` | `/api/v1/networks` | 创建网络 |
| `PUT` | `/api/v1/networks/<id>` | 更新网络（离线重建） |
| `DELETE` | `/api/v1/networks/<id>` | 删除网络 |

被容器占用的网络不可更新或删除。

### 创建 / 更新参数

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 网络名称（必填） |
| `subnet` | string | IPv4 CIDR（可选） |
| `gateway` | string | 网关（可选；须与 subnet 一致） |
| `driver` | string | 驱动（默认 `bridge`） |
| `internal` | bool | 内部网络（默认 `false`） |
| `attachable` | bool | 是否允许手动 attach（默认 `false`） |
| `enable_ipv6` | bool | 启用 IPv6（默认 `false`） |
| `compose_project_id` | string | 关联 Compose 项目 ID（可选） |
| `labels` | object | 额外 Docker labels（可选） |

## FRP

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/frp/proxies` | 代理列表 |
| `POST` | `/api/v1/frp/proxies` | 创建代理 |
| `GET` | `/api/v1/frp/proxies/<name>` | 代理详情 |
| `PUT` | `/api/v1/frp/proxies/<name>` | 更新代理 |
| `DELETE` | `/api/v1/frp/proxies/<name>` | 删除代理 |
| `GET` | `/api/v1/frp/config` | 完整配置 |
| `POST` | `/api/v1/frp/reload` | 热重载 |
| `GET` | `/api/v1/frp/health` | 健康检查 |
| `GET/PUT` | `/api/v1/frp/settings` | FRP 设置 |

**FRP 未启用时**：GET 类接口返回 `enabled: false` 的空数据（HTTP 200）；变更类接口（创建/更新/删除代理、reload）返回 **403**。

**健康检查**：`GET /api/v1/frp/health` 在 `overall_ok=false` 时仍返回 JSON，HTTP 状态为 **503**。

**手动创建代理**（`POST /api/v1/frp/proxies`）必填 `name`、`localPort`；可选 `type`（`tcp` / `http`，默认 `tcp`）、`localIP`（环回或 `host.docker.internal`）、`remotePort`、`customDomains`（HTTP 域名数组）。

**配置读取**：`GET /api/v1/frp/config` 返回的 TOML 已脱敏（`config_redacted: true`）。

## 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/status` | 服务器状态 |
| `POST` | `/api/v1/alerts/test` | 测试告警 |
| `GET/PUT` | `/api/v1/settings/alerts/webhook` | Webhook 设置 |
| `GET/PUT` | `/api/v1/settings/image-source` | 镜像源设置 |
| `GET/PUT` | `/api/v1/settings/networking` | 网络地址池设置 |
| `GET/PUT` | `/api/v1/settings/webui` | WebUI 设置 |
| `GET` | `/api/v1/settings/container-defaults` | 容器默认配置 |

### 运行时设置

以下接口支持通过 API **修改进程内配置**（GET 查询当前值，PUT 提交变更）：

- `/api/v1/settings/image-source`
- `/api/v1/settings/webui`
- `/api/v1/settings/networking`
- `/api/v1/settings/alerts/webhook`
- `/api/v1/frp/settings`

变更**仅当前进程生效**，进程重启后恢复为启动时 `.env` / 环境变量中的配置。PUT 成功时响应 `message` 会附加「（仅当前进程生效）」提示。

### 设置接口请求体

| 接口 | 方法 | 字段 |
|------|------|------|
| `/api/v1/settings/image-source` | PUT | `image_source`（string，可为空字符串表示清除前缀） |
| `/api/v1/settings/webui` | PUT | **必填** `api_base`（string）、`poll_interval_sec`（int）；**可选** `max_containers`、`max_renew_times`（受 `LOCK_RUNTIME_QUOTA_TO_BOOT` 约束） |
| `/api/v1/settings/networking` | PUT | `compose_managed_subnet_pool`（string）、`compose_managed_subnet_prefix`（int） |
| `/api/v1/settings/alerts/webhook` | PUT | **可选** `webhook_url`（string，空字符串关闭）、`webhook_timeout`（int，秒） |
| `/api/v1/frp/settings` | PUT | 见 [frp.md](frp.md#3-moegate-配置)（不含 `FRP_LOCAL_IP`） |

`GET /api/v1/settings/container-defaults` 只读，返回启动时 `.env` 中的容器默认配额（`max_time`、`min_port`、`max_port`、资源限制等），**无** PUT 接口。

### 告警

配置 `ALERT_WEBHOOK_URL` 后，可通过 `POST /api/v1/alerts/test` 发送测试消息。飞书机器人 webhook（`/open-apis/bot/v2/hook/...`）会自动使用 interactive 卡片格式，失败时降级为 text。通用 webhook 收到 JSON：`{event_type, service, payload}`。

> 当前版本**不会**在容器异常、资源阈值等事件上自动推送告警；仅支持手动测试与 Webhook 配置管理。

## 创建参数

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | string | Dockerfile / docker-compose.yaml 所在目录（须在 `ALLOWED_BASE_DIR` 内）；目录内按 `docker-compose.yaml` → `docker-compose.yml` → `Dockerfile` 优先级解析 |
| `image` | string | 镜像名称（与 `path` 二选一） |
| `source` / `source_type` | string | 显式指定 `path` 或 `image`（可选） |
| `command` | string / array | 镜像模式下的启动命令（可选） |
| `env` | object | 全局环境变量，键值均为字符串（受 `MAX_CONTAINER_ENV_KEYS` / `MAX_CONTAINER_ENV_VALUE_LEN` 限制） |
| `max_time` | int | 最大运行时长（秒，不超过 `MAX_TIME`；省略时使用 `MAX_TIME`） |
| `uid` | string | 自定义容器 UUID v4（可选；默认自动生成） |
| `tag` | string | Dockerfile 构建镜像 tag（可选） |
| `network` | string | 加入指定**受管**网络（可选） |
| `port_mappings` | string / array | 固定端口映射，如 `"8080:80,8443:443"` 或 `["8080:80"]`；支持 `host:container/protocol`（`tcp`/`udp`）；host 端口须在 `MIN_PORT`–`MAX_PORT` 内 |
| `min_port` / `max_port` | int | 随机端口分配子范围（会被 clamp 到 `MIN_PORT`–`MAX_PORT`；与 `port_mappings` 互斥） |
| `resource_limits` | object | 资源限制：`memory_limit`、`cpu_limit`、`cpu_shares`（可选） |
| `memory_limit` / `mem_limit` | string | 也可在顶层传入（与 `resource_limits` 等效） |
| `cpu_limit` | float | 也可在顶层传入 |
| `cpu_shares` | int | 也可在顶层传入 |
| `traffic_capture` | bool | 该靶机是否开启流量取证（共享 netns 的 tcpdump sidecar）；不传走 `TRAFFIC_CAPTURE_DEFAULT`，`true` 而平台未开 `ENABLE_TRAFFIC_CAPTURE` 时直接 400。多 service Compose 下对**每个 service** 各起一个 sidecar。详见 [traffic-capture.md](traffic-capture.md) |

**端口映射规则：**

- `port_mappings` 与 `min_port` / `max_port` **只能二选一**
- **多 service Compose** 项目会忽略 API 传入的 `port_mappings`，各 service 端口由 compose 文件中的 `ports` 定义并由 MoeGate 自动分配

`env` 注入规则（详见 [compose.md](compose.md#三种-flag-模式)）：

- **模式 1 — 镜像 / Dockerfile / 单 service Compose**：完整透传，例如 `{"FLAG": "flag{...}"}` 一定进入容器
- **模式 2 — 多 service 各自独立 flag**：用自定义槽位 `{"DEDECMS_FLAG": "f1", "XINHU_FLAG": "f2"}`，
  各 service 只拿到自己引用的那个变量，不跨服务泄漏
- **模式 3 — 多 service 共用一个 flag（默认）**：`{"FLAG": "flag{...}"}` 注入**所有** service，
  无需 compose 逐个声明 `${FLAG}`；未下发时引用 `${FLAG}` 的 service 各自生成随机值，
  响应 `data` 的 `compose_warnings` 会给出提示

Compose 里 `${VAR}` 占位符会被解析。

**创建响应**：Compose 项目成功时，响应 `data` 可能包含 `compose_warnings` 字符串数组：
YAML 含永久不支持字段时给出策略提示（`COMPOSE_UNSUPPORTED=warn`），多容器项目未下发 `FLAG` 时给出 flag 提示。
多 service 项目成功时 `data` 为容器信息数组；单容器/单 service 时为对象。

## 示例

```bash
# 状态
curl -s http://localhost:8080/api/v1/status -H "X-API-Key: <key>"

# 从 Dockerfile 创建
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/my-app", "max_time": 1800}'

# 从 Compose 创建，并注入全局环境变量
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/ctf-lab", "max_time": 3600, "env": {"DEDE_FLAG": "flag{custom}"}}'

# 从镜像创建
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"image": "nginx:latest", "max_time": 3600}'

# 创建并开启流量取证（多容器项目会对每个 service 各起一个 sidecar）
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/ssrf/docker", "max_time": 3600, "env": {"FLAG": "flag{xxx}"}, "traffic_capture": true}'

# 查看取证状态与 pcap 列表
curl -s -H "X-API-Key: <key>" \
  http://localhost:8080/api/v1/containers/<container_uuid>/traffic

# 拉取镜像
curl -s -X POST http://localhost:8080/api/v1/images/pull \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"image": "nginx:latest"}'

# 创建网络
curl -s -X POST http://localhost:8080/api/v1/networks \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"name": "lab-net", "subnet": "172.28.0.0/16", "gateway": "172.28.0.1"}'
```

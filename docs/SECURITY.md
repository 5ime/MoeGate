# 安全说明与威胁模型

MoeGate 是面向 **受控内网 / 单租户** 场景的 Docker 容器管理网关。部署到公网或多租户环境前，请阅读本文并落实加固措施。

## 信任边界

持有有效 `API_KEY`（或等效的 HttpOnly Session）的操作员，在设计上拥有以下能力：

- 通过 Docker Engine 创建、挂载、联网容器（等效于宿主机 Docker 控制权）
- 在 `ALLOWED_BASE_DIR` 白名单内构建与启动任意镜像/Compose
- 配置 FRP 穿透、Webhook 告警、运行时部分配置

**当前架构不支持：** 多租户隔离、细粒度 RBAC、按用户撤销权限。

### Cookie Session 与 Header 认证（M2 / M6）

| 模式 | 说明 |
|------|------|
| **Cookie（WebUI）** | 登录后写入 HttpOnly Session Cookie；**等效于完整 API_KEY 权限**，密钥不进入 JavaScript 上下文 |
| **Header（`X-API-Key`）** | curl、自动化脚本等在请求头携带密钥；**不受 CSRF 约束**，密钥由调用方自行保管 |

WebUI **仅**支持 Cookie Session 认证，不再提供将 API Key 存入 `localStorage` 的前端模式。

生产环境请启用 HTTPS + `API_SESSION_COOKIE_SECURE=true`。脚本调用使用 Header 认证时，须妥善保管密钥、避免写入前端代码或公开仓库。

Session 签名使用独立的 `API_SESSION_SECRET`（不得与 `API_KEY` 相同），详见 `env.example`。

## 高风险组件

### Docker Socket（H1）

`docker-compose.yml` 默认挂载 `/var/run/docker.sock`。API Key 泄露可导致：

- 启动特权容器、挂载宿主机根目录
- 操纵任意非 MoeGate 容器（取决于 Docker 权限模型）

**缓解措施：**

| 措施 | 说明 |
|------|------|
| 网络隔离 | 仅 VPN / 内网 / 反代后暴露 API，防火墙限制来源 IP |
| 强密钥与轮换 | `API_KEY` 使用高熵随机值，定期轮换并审计 `moegate.audit` 日志 |
| WebUI 双层认证 | 配置 `WEBUI_BASIC_AUTH_*`，生产启用 HTTPS |
| Docker Socket Proxy | 使用 `deploy/compose/socket-proxy.example.yml` 叠加部署，限制 exec/swarm 等高危 API |
| 非 root / rootless | 宿主机使用专用低权限用户运行 Docker（能力仍高，但可缩小爆炸半径） |
| 容器资源上限 | 为 MoeGate 自身容器设置 `mem_limit` / `cpus`，避免资源耗尽 |

### Cookie Session CSRF（M4）

Cookie 模式下，变更类 API（POST/PUT/PATCH/DELETE）启用 **Double-Submit Cookie** 校验（`ENABLE_API_CSRF=true`，默认开启）：

- 登录或 `GET /api/v1/auth/session` 时下发 `moegate_csrf` Cookie（非 HttpOnly，供前端读取）
- 前端须在请求头携带匹配的 `X-CSRF-Token`
- 使用 `X-API-Key` Header 认证的脚本调用**不受** CSRF 约束

SameSite=Lax 提供基础跨站防护；CSRF token 进一步保护同站恶意页面发起的变更请求。

### 单 Key 无 RBAC（H2）

所有认证请求共享同一权限。变更类 API 调用会写入 `moegate.audit` 日志（来源 IP、方法、路径、认证方式），便于事后追溯，但**无法**按用户单独撤销或降级。

**运维建议：**

| 措施 | 说明 |
|------|------|
| 密钥轮换 | 定期更换 `API_KEY` 后，旧 Session 自动失效；使用 Header 认证的脚本需同步更新 |
| 审计日志 | 将 `moegate.audit` 接入 SIEM，对异常 IP / 高频变更告警 |
| 网络分域 | 管理 API 与选手靶场网络隔离，避免 Key 泄露波及宿主机 |
| 未来扩展 | 多 Key / RBAC 需架构级改造，当前版本不在路线图内 |

### 用户 Compose SDK 子集（CTF 设计权衡）

MoeGate 使用 **Docker SDK 编排**（非 `docker compose` CLI），在保留受控网络、随机端口池与 FRP 的前提下支持 Compose 子集。

**已支持（经 SDK 映射）**：`image` / `build`、`ports`（MoeGate 自动分配宿主机端口）、`command`、`environment`、`networks`、bind mount `volumes`、`privileged`、`cap_add` / `cap_drop`、`depends_on`（仅启动顺序）、API 传入的 `resource_limits`。

**永久不支持**（与受控网络/随机端口冲突或未实现）：`network_mode: host`、`healthcheck`、`deploy`（除 API 资源限制）、`ipc: host` / `pid: host`、named volume。

| 环境变量 | 说明 |
|----------|------|
| `COMPOSE_POLICY=strict` | 额外拒绝 `privileged`、高危 `cap_add`、`network_mode` / `ipc` / `pid: host` 等（永久不支持字段仍由 `COMPOSE_UNSUPPORTED` 控制） |
| `COMPOSE_UNSUPPORTED=error` | 对永久不支持字段拒绝启动（默认 `warn` 仅记录并在 API 返回 `compose_warnings`） |

**无论 `COMPOSE_POLICY` 为何值**，bind mount 解析均会拒绝 Docker Socket 及 `/etc`、`/proc` 等敏感宿主机路径。

生产建议：`COMPOSE_POLICY=strict` + `COMPOSE_UNSUPPORTED=error`。详见 [compose.md](compose.md)。

**运维须承担：**

- MoeGate 宿主机与选手容器**网络/文件系统隔离**（独立 VM、rootless Docker、或专用节点）
- 不在宿主机敏感目录挂载 `ALLOWED_BASE_DIR`
- 非 CTF 场景使用 `COMPOSE_POLICY=strict` 拒绝 `privileged` 与高危 `cap_add`；`ctf` 模式在上述 bind mount 硬限制之外允许特权容器等 CTF 常见配置

## 已实施的安全控制

- Webhook URL SSRF 防护 + DNS 固定 IP 发送（`utils/url_validator.py`）
- 可信反代 IP 白名单（`TRUSTED_PROXY_IPS` + `middleware/ip.py`）
- 认证失败临时封禁（`middleware/auth_guard.py`）
- 运行态配额不得高于启动配置（`LOCK_RUNTIME_QUOTA_TO_BOOT`）
- 容器 env 键值数量与长度上限
- Webhook / FRP 敏感字段 API 脱敏（host + 路径末段 / 密码占位）
- `port_mappings` 宿主机端口强制落在 `MIN_PORT`–`MAX_PORT`；请求的 `min_port`/`max_port` 也会被 clamp 到该范围
- 容器/镜像详情 API 默认不返回完整 `environment` / Docker `attrs`（`?verbose=true` 可获取）
- FRP 手动代理 `localIP` 限制为环回地址（`127.0.0.1` / `::1`）或 Docker 宿主机别名（`host.docker.internal` / `host.containers.internal`）；TOML 字段转义防注入
- API Key 恒定时间比较、路径白名单、受管容器标签隔离
- 生产模式（`API_DEBUG=false`）路径校验错误不返回绝对路径

### 限流与多实例（M7）

IP 限流为**单进程内存**实现（`middleware/rate_limit.py`）。多实例部署时限流计数不共享，需在前置反代或 WAF 层做分布式限流。详见 [deploy.md](deploy.md#多实例限制)。

多实例共享 `ALLOWED_BASE_DIR` 时，可启用 `ENABLE_SHARED_QUOTA=true`（默认）通过文件锁协调容器名额预留；限流与销毁任务状态仍不跨进程共享。

### Metrics 与探活（L1 / L2）

- `/metrics` 在 `ENABLE_PUBLIC_METRICS=true` 或已配置 `METRICS_TOKEN` 时注册；**访问时始终需要** `METRICS_TOKEN`，通过请求头 `X-Metrics-Token` 传递（不支持 query string，避免日志/Referer 泄露）
- 生产模式（`API_DEBUG=false`）下启用 `ENABLE_PUBLIC_METRICS` 时，启动校验要求必须配置 `METRICS_TOKEN`
- `/healthz` 为无认证 liveness 探针，仅返回 HTTP 200/503，**不**返回 JSON 或组件信息

### 生产启动检查（L3–L5）

非调试模式（`API_DEBUG=false`）启动时，以下误配会写入启动日志 warning：

| 配置 | 风险 |
|------|------|
| `TRUST_PROXY_HEADERS=true` 且未配置 `TRUSTED_PROXY_IPS` | 生产环境启动失败；调试模式下忽略代理头 |
| `API_HOST=0.0.0.0` | 监听所有网卡，需防火墙限制端口 |
| `API_SESSION_COOKIE_SECURE=false` + HTTPS | Session Cookie 可能明文传输 |

### 运行时配置（M8）

部分设置 API 支持**进程内**修改，变更不会写入 `.env`，重启后恢复为启动配置。

默认启用 `LOCK_RUNTIME_QUOTA_TO_BOOT=true`：运行态 API **不能**将 `MAX_CONTAINERS` / `MAX_RENEW_TIMES` 提高到超过 `.env` 启动值，防止临时扩大资源配额。

## 推荐生产加固（第二阶段）

| 措施 | 配置 / 文件 | 说明 |
|------|-------------|------|
| Docker Socket 代理 | `deploy/compose/socket-proxy.example.yml` | MoeGate 经 `docker-socket-proxy` 访问 Docker，禁用 EXEC/SWARM 等高危 API |
| 可信反代 IP 白名单 | `TRUSTED_PROXY_IPS` | 与 `TRUST_PROXY_HEADERS=true` 配合；仅反代 IP 命中时才读 `X-Forwarded-For` |
| 认证失败封禁 | `AUTH_FAILURE_LIMIT_PER_MIN` | 同一 IP 每分钟认证失败超阈值后返回 429 |
| 运行态配额锁定 | `LOCK_RUNTIME_QUOTA_TO_BOOT=true` | 禁止通过 WebUI/API 临时抬高容器上限 |
| env 注入上限 | `MAX_CONTAINER_ENV_KEYS` / `MAX_CONTAINER_ENV_VALUE_LEN` | 限制创建容器时的环境变量规模 |
| Metrics 强制 token | `METRICS_TOKEN` | 生产环境启用 `ENABLE_PUBLIC_METRICS` 时必填 |

**推荐启动命令：**

```bash
docker compose -f docker-compose.yml -f deploy/compose/socket-proxy.example.yml up -d --build
```

## 生产检查清单

- [ ] `API_KEY` 已替换为 **≥32 字符**高熵随机值
- [ ] `API_SESSION_SECRET` 已配置且与 `API_KEY` 不同
- [ ] `API_DEBUG=False`
- [ ] 使用 `deploy/compose/socket-proxy.example.yml` 叠加部署（或等效 Socket Proxy）
- [ ] TLS 终止于反向代理，`API_SESSION_COOKIE_SECURE=true`（若使用 Cookie 登录）
- [ ] 反代后部署时：`TRUST_PROXY_HEADERS=true` 且配置 `TRUSTED_PROXY_IPS`
- [ ] `METRICS_TOKEN` 已配置（若启用 `/metrics`）
- [ ] `WEBUI_BASIC_AUTH_*` 或等效网络层访问控制
- [ ] `ALLOWED_BASE_DIR` 仅包含必要构建目录
- [ ] `LOCK_RUNTIME_QUOTA_TO_BOOT=true`
- [ ] 非 CTF 场景评估 `COMPOSE_POLICY=strict`
- [ ] 防火墙限制 8080 / API 端口仅内网可达
- [ ] 日志采集包含 `moegate.audit` 与认证失败告警

## 报告安全问题

如发现漏洞，请通过仓库 Issue 或维护者私下渠道联系，勿在公开渠道披露可利用细节。

## 安全审计

CI 运行 Bandit 与 pip-audit 进行静态分析与依赖漏洞扫描。变更认证或容器创建路径时请自行验证相关安全控制。

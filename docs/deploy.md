# 部署指南

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | **3.11**（官方支持） | 裸机部署；Docker 镜像已固定 `python:3.11-slim` |
| Docker Engine | 20.10+ | 需可访问 Docker Daemon |
| Node.js | 18+ | 仅本地构建 WebUI 时需要 |

### 版本口径

| 类别 | Python | Flask | 说明 |
|------|--------|-------|------|
| **官方支持** | 3.11 | 3.1 | Docker 镜像、CI、文档与 `requirements.txt` 锁定以此为基准 |

## 快速部署（裸机）

```bash
pip install -r requirements.txt
cp env.example .env   # 编辑 .env
python app.py
```

启动后访问 `http://localhost:8080`。

## Docker 部署（推荐）

```bash
cp env.example .env
# 编辑 .env：至少设置 API_KEY；容器内 ALLOWED_BASE_DIR 默认为 /data/containers

docker compose up -d --build
```

说明：

- 镜像多阶段构建：Node 构建 WebUI → Python slim + gunicorn
- 容器内以非 root 用户 `moegate` 运行；entrypoint 会将该用户加入 `docker.sock` 所在组
- 挂载 `/var/run/docker.sock` 以管理宿主机容器（等效 root，见 [SECURITY.md](SECURITY.md#docker-socketh1)）
- 数据目录 `moegate-data` 命名卷映射到 `/data/containers`（构建白名单根目录）；默认由 Docker 管理卷，无需本机路径
- 若需 bind 到宿主机目录，可叠加 `docker-compose.override.yml` 或参考下方示例
- 健康检查：`GET /healthz`
- 默认 `SHUTDOWN_DESTROY_CONTAINERS=false`，重启 MoeGate 不会删除受管容器

### 数据目录 bind 挂载（可选）

默认 `docker-compose.yml` 使用 Docker 命名卷。若希望数据落在宿主机固定路径：

```yaml
# docker-compose.override.yml
services:
  moegate:
    volumes:
      - /path/on/host/containers:/data/containers
```

请将 `/path/on/host/containers` 替换为实际路径，并确保目录存在且容器进程可写。

### 容器生命周期持久化

受管容器的续期次数与到期时间：

- **创建时**：写入 Docker labels（`moegate.expires_at`、`moegate.renew_count`）
- **续期后**：labels 不可变，变更写入进程内缓存，并持久化到 `ALLOWED_BASE_DIR/.moegate/lifecycle.json`
- **进程重启**：reconcile 从 JSON 恢复定时器；容器删除时清理对应记录

裸机部署时该文件位于 `ALLOWED_BASE_DIR` 下；Docker 部署时在 `moegate-data` 卷内（通常为 `/data/containers/.moegate/lifecycle.json`）。

### 运行态设置共享（可选，多 worker）

默认运行态 API 修改仅写入进程内 `config`。若必须使用 `gunicorn -w 2+`，可设置 `RUNTIME_STORE_PERSIST=true`：

- 运行态字段写入 `ALLOWED_BASE_DIR/.moegate/runtime_settings.json`
- 各 worker 在读取前自动同步文件变更
- **进程重启**时 `create_app()` 会将文件重置为环境变量启动值（与 `.env` 行为一致，不写回 `.env`）

单 worker 部署无需开启；容器缓存、限流、销毁任务等仍为进程内状态，多实例问题见下文。

### 生产 gunicorn 命令（裸机）

MoeGate 使用内存状态与进程内定时器，**建议单 worker**：

```bash
gunicorn -w 1 -k gthread --threads 8 -b 0.0.0.0:8080 --timeout 120 app:app
```

## 配置说明

完整配置见根目录 `env.example`，以下为必填项和常用项：

| 变量 | 必填 | 说明 |
|------|------|------|
| `API_KEY` | **是** | API 密钥，不可用默认占位值（生产须 ≥32 字符） |
| `API_SESSION_SECRET` | **是**（Cookie 登录） | Session 签名密钥，必须与 `API_KEY` 不同 |
| `ALLOWED_BASE_DIR` | **是** | Dockerfile/Compose 构建路径白名单根目录 |
| `API_PORT` | | 监听端口（默认 `8080`；Docker 映射 `${API_PORT:-8080}:8080`） |
| `ENABLE_WEBUI` | | 是否托管 WebUI（默认 `True`） |
| `WEBUI_BASIC_AUTH_USER` / `WEBUI_BASIC_AUTH_PASSWORD` | | 两者均配置时，WebUI 启用 Basic 认证 |
| `SHUTDOWN_DESTROY_CONTAINERS` | | 进程退出时是否销毁受管容器（默认 `false`） |
| `EXPIRE_RECONCILE_INTERVAL_SEC` | | 容器到期扫描间隔（默认 `60`） |
| `MAX_RENEW_TIMES` | | 单容器最大续期次数（默认 `3`） |
| `ENABLE_SHARED_QUOTA` | | 多实例共享数据目录时协调容器名额（默认 `true`） |
| `RUNTIME_STORE_PERSIST` | | 多 worker 时运行态设置写入 JSON 共享（默认 `false`） |
| `LOCK_RUNTIME_QUOTA_TO_BOOT` | | 禁止运行态 API 抬高 `MAX_CONTAINERS` / `MAX_RENEW_TIMES`（默认 `true`） |
| `ENABLE_PUBLIC_METRICS` | | 注册 `/metrics` 端点（须配合 `METRICS_TOKEN`；生产模式启用时 token 必填） |
| `METRICS_TOKEN` | 启用 `/metrics` 时 **是** | 抓取 `/metrics` 时须在请求头携带 `X-Metrics-Token`（不支持 query token；未配置 token 时返回 401） |
| `IMAGE_SOURCE` | | 全局镜像前缀，拉取镜像时自动拼接 |
| `MAX_CONTAINERS` | | 最大同时运行容器数（默认 `30`） |
| `MAX_TIME` | | 容器最大运行时长，秒（默认 `3600`） |
| `MIN_PORT` / `MAX_PORT` | | 端口映射范围（默认 `20000`-`30000`；须满足 `MAX_PORT - MIN_PORT >= MAX_CONTAINERS`） |
| `CONTAINER_MEMORY_LIMIT` | | 内存限制（默认 `512m`） |
| `CONTAINER_CPU_LIMIT` | | CPU 核数限制 |
| `CONTAINER_CPU_SHARES` | | CPU Shares（默认未设时创建逻辑回退 `1024`） |
| `ENABLE_FRP` | | 启用 FRP 穿透（需配置其余 `FRP_*` 变量） |
| `FRP_SERVER_ADDR` | FRP 启用时 | frps 地址（Compose 联调可为服务名 `frps`） |
| `FRP_SERVER_PORT` | | frps 端口（默认 `7000`） |
| `FRP_ADMIN_IP` | | frpc 管理 API 地址（裸机 `127.0.0.1`；Docker 内 frpc 为 Compose 服务名 `frpc`） |
| `FRP_ADMIN_PORT` | | frpc 管理 API 端口（默认 `7400`） |
| `FRP_ADMIN_USER` / `FRP_ADMIN_PASSWORD` | | frpc `[webServer]` 凭据 |
| `FRP_LOCAL_IP` | | 自动注册代理 localIP（默认 `127.0.0.1`；Docker 内 frpc 用 `host.docker.internal`；仅启动配置） |
| `FRP_USE_DOMAIN` / `FRP_DOMAIN_SUFFIX` / `FRP_VHOST_HTTP_PORT` | | HTTP 虚拟主机模式（可选） |
| `COMPOSE_MANAGED_SUBNET_POOL` | | Compose 子网地址池（默认 `172.30.0.0/16`） |
| `COMPOSE_MANAGED_SUBNET_PREFIX` | | Compose 子网前缀长度（默认 `24`） |
| `COMPOSE_POLICY` | | Compose 启动策略：`ctf`（默认）或 `strict` |
| `COMPOSE_UNSUPPORTED` | | 永久不支持字段：`warn`（默认）或 `error` |
| `ALERT_WEBHOOK_URL` / `ALERT_WEBHOOK_TIMEOUT` | | 告警 Webhook（当前仅 `POST /api/v1/alerts/test` 手动触发） |
| `TRUST_PROXY_HEADERS` / `TRUSTED_PROXY_IPS` | | 反向代理真实 IP（生产启用前者时后者必填） |
| `CORS_ALLOWED_ORIGINS` | | 浏览器跨域白名单（逗号分隔） |
| `RATE_LIMIT_PER_MIN` / `AUTH_FAILURE_LIMIT_PER_MIN` | | IP 限流与认证失败封禁（默认 `60` / `10`） |

完整列表与 Session/CSRF/SSE/日志等变量见根目录 `env.example`。

## 探活与监控

| 端点 | 认证 | 说明 |
|------|------|------|
| `GET /healthz` | 无 | Liveness：仅返回 HTTP 200/503，不暴露组件细节 |
| `GET /metrics` | `X-Metrics-Token` | Prometheus 文本指标；端点可见条件为 `ENABLE_PUBLIC_METRICS=true` 或已配置 `METRICS_TOKEN`，访问时 token 必填 |

## Docker Socket Proxy（H1 缓解）

默认 `docker-compose.yml` 直接挂载宿主机 socket。**推荐生产**叠加 Socket Proxy：

```bash
docker compose -f docker-compose.yml -f deploy/compose/socket-proxy.example.yml up -d --build
```

该方案通过 [Tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) 禁止 `exec`、`swarm` 等端点，并将 MoeGate 的 `DOCKER_HOST` 指向代理；叠加文件使用 `volumes: !reset` 移除 MoeGate 对 `docker.sock` 的直接挂载。可按需调整代理环境变量；**不能**替代网络隔离与强密钥。

更多叠加示例见 [deploy/compose/README.md](../deploy/compose/README.md)。

## 生产环境建议

完整威胁模型与 Docker Socket 风险说明见 [SECURITY.md](SECURITY.md)。

- 将 `API_DEBUG` 设为 `False`
- 替换 `API_KEY` 为强随机密钥，并定期轮换
- 配置独立的 `API_SESSION_SECRET`（启用 Cookie 登录时必填）
- WebUI 仅使用 Cookie Session 认证，API Key 不进入浏览器 `localStorage`
- 限制 API 仅内网/VPN/反代后可访问；评估 `deploy/compose/socket-proxy.example.yml`
- 保持 `ENABLE_API_CSRF=true`（Cookie 登录时的变更 API CSRF 防护）
- 谨慎配置 `ALLOWED_BASE_DIR`，防止目录越权
- 配置 `WEBUI_BASIC_AUTH_*` 或仅内网暴露 WebUI
- 若部署在反向代理后：启用 `TRUST_PROXY_HEADERS=true` 并配置 `TRUSTED_PROXY_IPS`（反代来源 IP/CIDR）
- 配置 `CORS_ALLOWED_ORIGINS` 限制跨域来源；调试模式默认允许 `localhost:5173`
- 使用 TLS 终止于 Nginx/Caddy/Traefik，不要直接暴露 HTTP 到公网

### 反向代理示例（Nginx）

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
}
```

## 多实例限制

MoeGate 的容器缓存、限流、销毁任务状态均为**单进程内存**实现。水平扩展多实例会导致：

- 限流失效
- 销毁任务状态不可共享

**容器名额**：默认启用 `ENABLE_SHARED_QUOTA=true`，在共享 `ALLOWED_BASE_DIR` 卷时通过 `.moegate/quota_reservations.json` 与文件锁协调预留，可缓解多副本超额创建；定时器与缓存仍不跨进程共享。

生产环境请使用 **单实例 + 单 worker**，或接受上述限制并在文档中明确。

## 前端开发

默认后端托管 `static/` 下的构建产物。构建时会写入 `static/.moegate-build.json`（版本与构建时间）；启动时若缺失该文件会记录 warning。

如需热更新开发：

```bash
# 1. 后端：.env 中设置 ENABLE_WEBUI=False，然后
python app.py

# 2. 前端
cd frontend && npm install && npm run dev
```

Vite 已配置代理，开发模式下 `/api` 请求会自动转发到后端。

构建产物：

```bash
cd frontend && npm run build
# 输出到 static/，并生成 .moegate-build.json；Flask 自动托管
```

Docker 构建会自动执行前端 build，无需手动提交 `static/` 更新。

### 裸机部署 WebUI

若未使用 Docker 镜像，更新 WebUI 后须重新构建：

```bash
cd frontend && npm ci && npm run build
```

创建容器时可通过请求头 `X-User-Id` 或 `X-Operator-Id` 传递操作者标识，写入容器 label `moegate.created_by` 便于追溯。

## Compose 启动策略

| 能力 | `ctf`（默认） | `strict` |
|------|---------------|----------|
| `privileged` | 允许 | 拒绝 |
| 高危 `cap_add`（如 `SYS_ADMIN`） | 允许 | 拒绝 |
| `network_mode` / `ipc` / `pid: host` | **不支持**（SDK 不实现；默认 warn，见 `COMPOSE_UNSUPPORTED`） | 策略层额外拒绝 |
| Docker Socket、`/etc` 等敏感 bind mount | **始终拒绝**（与策略无关） | 始终拒绝 |

环境变量：`COMPOSE_POLICY=strict`（见 `env.example`）。完整字段说明见 [compose.md](compose.md) 与 [SECURITY.md](SECURITY.md)。

## FRP 穿透

详见 [frp.md](frp.md)。Compose 叠加示例见 [deploy/compose/README.md](../deploy/compose/README.md)。

| 文件 | 说明 |
|------|------|
| [deploy/compose/frp.example.yml](../deploy/compose/frp.example.yml) | 独立 compose，同机运行 moegate + frpc（`frpc.toml` 在仓库根目录） |
| [deploy/compose/frpc.example.yml](../deploy/compose/frpc.example.yml) | 与根 `docker-compose.yml` 叠加，仅追加 frpc |
| [deploy/compose/frps.example.yml](../deploy/compose/frps.example.yml) | 与 `frp.example.yml` 叠加，同网启动 frps（需 `deploy/compose/frps.toml`） |
| [deploy/compose/frps.example.toml](../deploy/compose/frps.example.toml) | frps 配置模板，复制为 `frps.toml` |
| [docker-compose.frp-test.yml](../docker-compose.frp-test.yml) | 根目录联调叠加：frps + frpc + `FRP_LOCAL_IP=host.docker.internal` |

# MoeGate

轻量级 Docker 容器管理网关。支持 Dockerfile / Docker Compose / 镜像名称创建容器，到期自动销毁，内置 FRP 穿透。适用于 CTF 靶场、临时演示、在线实验室。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue) ![Flask](https://img.shields.io/badge/Flask-2.x-black) ![Docker](https://img.shields.io/badge/Docker-Engine-2496ED)

![示例截图](https://github.com/user-attachments/assets/b8f64b98-7ca0-4417-aef6-3bf50b1b7f66)

## 特性

- 多模式创建：Dockerfile 构建 / Docker Compose 编排 / 镜像名称拉取
- 生命周期管理：自动到期销毁、续期、重启，异步删除
- 资源限制：内存、CPU 核数、CPU Shares
- 端口管理：线程安全的自动分配，范围可配
- SSE 流式日志：构建和拉取镜像过程实时输出
- 受管网络：子网/网关校验，Compose 项目自动分配子网
- 受管镜像：自动登记、悬空清理、引用关系约束
- FRP 穿透：容器创建后自动注册 frpc 代理，支持 TCP/HTTP
- 告警通知：Webhook / 飞书机器人卡片消息
- 安全：API Key 认证、IP 限流、路径白名单、CORS、请求体校验
- 隔离：只管理 MoeGate 创建的容器（`moegate.managed=true`），不影响宿主机
- WebUI：Vue 3 + Tailwind CSS，容器/镜像/网络/FRP/系统设置一站式管理

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | |
| Docker Engine | 20.10+ | 需可访问 Docker Daemon |
| Node.js | 18+ | 仅构建 WebUI 时需要 |

## 快速开始

```bash
pip install -r requirements.txt
cp env.example .env   # 编辑 .env
python app.py
```

启动后访问 `http://localhost:8080`。

## 配置

完整配置见 `env.example`，以下为必填项和常用项：

| 变量 | 必填 | 说明 |
|------|------|------|
| `API_KEY` | **是** | API 密钥，不可用默认占位值 |
| `ALLOWED_BASE_DIR` | **是** | Dockerfile/Compose 构建路径白名单根目录 |
| `ENABLE_WEBUI` | | 是否托管 WebUI（默认 `True`） |
| `IMAGE_SOURCE` | | 全局镜像前缀，拉取镜像时自动拼接 |
| `MAX_CONTAINERS` | | 最大同时运行容器数（默认 `30`） |
| `MAX_TIME` | | 容器最大运行时长，秒（默认 `3600`） |
| `MIN_PORT` / `MAX_PORT` | | 端口映射范围（默认 `20000`-`30000`） |
| `CONTAINER_MEMORY_LIMIT` | | 内存限制（默认 `512m`） |
| `CONTAINER_CPU_LIMIT` | | CPU 核数限制 |
| `ENABLE_FRP` | | 启用 FRP 穿透（需配置 `FRP_*` 变量） |
| `ALLOW_RUNTIME_CONFIG_WRITE` | | 允许通过 API 持久化设置到 `.env`（默认 `False`） |
| `COMPOSE_MANAGED_SUBNET_POOL` | | Compose 子网地址池（默认 `172.30.0.0/16`） |

## 前端开发

默认后端托管 `static/` 下的构建产物。如需热更新开发：

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
# 输出到 static/，Flask 自动托管
```

## 项目结构

```
app.py                  # Flask 入口
config/                 # 配置加载与校验
core/                   # 事件总线、异常、日志、响应、关闭钩子
infra/                  # Docker 客户端（单例、自动重连）
middleware/             # 认证、限流、请求校验、日志
routes/                 # API 路由
services/
  container/            # 构建、生命周期、端口管理、信息查询
  frp/                  # FRP 代理管理、配置解析
  image.py              # 受管镜像服务
  network.py            # 受管网络服务
utils/                  # 销毁任务、端口工具、路径校验、告警、镜像登记
workers/                # 性能监控
frontend/               # Vue 3 WebUI 源码
static/                 # WebUI 构建产物
```

## API

所有接口需要 `X-API-Key` 请求头。

### 容器

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/containers` | 创建容器 |
| `POST` | `/api/v1/containers/stream` | 创建容器（SSE 流式） |
| `GET` | `/api/v1/containers` | 容器列表 |
| `GET` | `/api/v1/containers/<id>` | 容器详情 |
| `PATCH` | `/api/v1/containers/<id>` | 重启容器 |
| `DELETE` | `/api/v1/containers/<id>` | 删除容器（异步） |
| `GET` | `/api/v1/containers/<id>/destroy-status` | 删除任务状态 |
| `POST` | `/api/v1/containers/<id>/renew` | 续期 |

**统一入口**（自动识别单容器或 Compose 项目）：

| 方法 | 路径 | 说明 |
|------|------|------|
| `PATCH` | `/api/v1/containers/restart/<id>` | 重启 |
| `DELETE` | `/api/v1/containers/destroy/<id>` | 删除 |
| `POST` | `/api/v1/containers/renew/<id>` | 续期 |

**Compose 项目**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/containers/project/<id>` | 项目详情 |
| `PATCH` | `/api/v1/containers/project/<id>` | 重启项目 |
| `DELETE` | `/api/v1/containers/project/<id>` | 删除项目 |
| `GET` | `/api/v1/containers/project/<id>/destroy-status` | 删除状态 |
| `POST` | `/api/v1/containers/project/<id>/renew` | 续期项目 |

### 镜像

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/images` | 受管镜像列表 |
| `GET` | `/api/v1/images/detail/<ref>` | 镜像详情 |
| `POST` | `/api/v1/images/pull` | 拉取镜像 |
| `POST` | `/api/v1/images/pull/stream` | 拉取镜像（SSE） |
| `DELETE` | `/api/v1/images/<ref>` | 删除镜像（`?force=true` 强制） |
| `POST` | `/api/v1/images/prune` | 清理悬空镜像 |

### 网络

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/networks` | 受管网络列表 |
| `GET` | `/api/v1/networks/<id>` | 网络详情 |
| `POST` | `/api/v1/networks` | 创建网络 |
| `PUT` | `/api/v1/networks/<id>` | 更新网络（离线重建） |
| `DELETE` | `/api/v1/networks/<id>` | 删除网络 |

被容器占用的网络不可更新或删除。

### FRP

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

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/status` | 服务器状态 |
| `GET` | `/api/v1/metrics` | Prometheus 指标 |
| `POST` | `/api/v1/alerts/test` | 测试告警 |
| `GET/PUT` | `/api/v1/settings/alerts/webhook` | Webhook 设置 |
| `GET/PUT` | `/api/v1/settings/alerts/perf` | 性能告警设置 |
| `GET/PUT` | `/api/v1/settings/image-source` | 镜像源设置 |
| `GET/PUT` | `/api/v1/settings/networking` | 网络地址池设置 |
| `GET/PUT` | `/api/v1/settings/webui` | WebUI 设置 |
| `GET` | `/api/v1/settings/container-defaults` | 容器默认配置 |

### 示例

```bash
# 状态
curl -s http://localhost:8080/api/v1/status -H "X-API-Key: <key>"

# 从 Dockerfile 创建
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/my-app", "max_time": 1800}'

# 从镜像创建
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"image": "nginx:latest", "max_time": 3600}'

# 拉取镜像
curl -s -X POST http://localhost:8080/api/v1/images/pull \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"image": "nginx:latest"}'

# 创建网络
curl -s -X POST http://localhost:8080/api/v1/networks \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"name": "lab-net", "subnet": "172.28.0.0/16", "gateway": "172.28.0.1"}'
```

## FRP 配置

1. 部署 **frps**：

```toml
# frps.toml
bindPort = 7000
bindAddr = "0.0.0.0"

# HTTP 代理端口（可选：仅在需要 HTTP vhost 时启用）
vhostHTTPPort = 80

# 鉴权配置（可选）
[auth]
method = "token"
token = "your-strong-random-token"

# 日志配置（可选）
[log]
level = "info"
maxDays = 3
to = "frps.log"
```

2. 部署 **frpc**（需启用 `webServer` 供 MoeGate 调用管理 API）：

```toml
# frpc.toml
serverAddr = "frps.example.com"
serverPort = 7000

[auth]
method = "token"
token = "your-strong-random-token"

[webServer]
addr = "127.0.0.1"
port = 7400
user = "admin"
password = "admin"
```

3. `.env` 中设置 `ENABLE_FRP=True` 并填写 `FRP_*` 变量（`FRP_SERVER_ADDR`、`FRP_ADMIN_USER`/`FRP_ADMIN_PASSWORD` 等）
4. 容器创建时 MoeGate 自动注册 frpc 代理，删除时自动清理

## FAQ

**容器列表为空？** MoeGate 只管理自己创建的容器（`moegate.managed=true`），不展示宿主机其他容器。

**网络无法更新/删除？** 被容器占用的网络禁止操作，需先释放容器。

**镜像删除失败？** 可能仍被容器引用，或同一镜像有多个 tag 需要 `force=true`。

**设置重启后丢失？** `ALLOW_RUNTIME_CONFIG_WRITE=False`（默认）时，API 修改仅在内存生效，不写入 `.env`。

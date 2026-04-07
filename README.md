# MoeGate - 轻量级 Docker 容器管理网关

MoeGate 支持通过 **Dockerfile / Docker Compose / 镜像名称** 一键创建容器，自带**到期自动销毁**、续期、资源限制、**受管网络**、FRP 内网穿透等能力。适用于 CTF / 靶场、临时演示环境、在线实验室等场景。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue) ![Flask](https://img.shields.io/badge/Flask-2.x-black) ![Docker](https://img.shields.io/badge/Docker-Engine-2496ED)

![示例截图](https://github.com/user-attachments/assets/a087c14f-fab2-4748-a00a-173fa8ff0d65)

## 功能特性
- **多模式创建**：支持 Dockerfile 构建、Docker Compose 编排、直接拉取镜像
- **生命周期管理**：容器创建、重启、续期、异步销毁，到期自动清理
- **资源精细化控制**：独立配置内存、CPU 核数、CPU Shares 限制
- **线程安全端口管理**：自动分配或指定端口映射，避免冲突
- **SSE 流式构建日志**：前端实时展示 `docker build` 过程
- **受管网络管理**：支持子网/网关校验、IPAM 配置，占用网络禁止改删，更新采用离线重建策略
- **多渠道告警**：支持 Webhook、飞书机器人卡片消息通知
- **安全防护**：API Key 认证、IP 限流、路径/CORS 白名单、请求体大小校验
- **受控隔离**：仅管理 MoeGate 创建的容器，不影响宿主机原有容器
- **WebUI**：基于 Vue3+Vite 开发，支持网络管理、搜索筛选、详情弹窗等交互
- **FRP 穿透**：容器创建后自动注册 frpc 代理，支持 TCP/HTTP 域名映射

## 环境要求
| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | - |
| Docker Engine | 20.10+ | 需可访问 Docker Daemon（常见为 Linux 的 `/var/run/docker.sock`） |
| Node.js | 18+ | 仅在自行构建 WebUI 或前端开发时需要 |

## 快速开始
### Linux / macOS

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
python app.py
```

### Windows (PowerShell)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item env.example .env
python app.py
```

## 开发模式（前后端分离）
默认情况下，后端会托管 `static/`（即前端 `vite build` 的产物）。如果你希望使用 Vite 的热更新开发 WebUI，推荐按下面方式启动：

### 1) 启动后端 API（禁用内置 WebUI）
在 `.env` 中设置：

- `ENABLE_WEBUI=False`
- （可选）`API_DEBUG=True`（仅本地开发）

然后启动：

```bash
python app.py
```

### 2) 启动前端 Dev Server
在 `frontend/` 下执行：

```bash
npm install
npm run dev
```

前端默认监听 `127.0.0.1:5173`。如需让前端请求指向后端 API，可在 `.env` 中设置：

- `WEBUI_API_BASE=http://127.0.0.1:8080`

> 注意：生产模式下若启用浏览器跨域访问，请配置 `CORS_ALLOWED_ORIGINS` 白名单。

## 配置要点（必填/常用）
完整配置项见 `env.example`，这里只列出“必填且经常踩坑”的项。

| 环境变量 | 是否必填 | 说明 |
|----------|----------|------|
| `API_KEY` | **必填** | API 访问密钥（不可使用默认占位值） |
| `ALLOWED_BASE_DIR` | **必填** | 允许构建的目录白名单根路径（用于限制 Dockerfile/Compose 的读取路径） |
| `ENABLE_WEBUI` | 否 | 是否托管 WebUI 静态页面 |
| `ENABLE_FRP` | 否 | 是否启用 FRP 代理管理（启用后需要配置 `FRP_*`） |

## 项目结构

```text
├── app.py                  # Flask 应用入口
├── config/                 # 配置加载与校验
├── core/                   # 事件总线、异常、日志、响应格式、关闭钩子
├── infra/                  # Docker 客户端管理
├── middleware/             # 认证、限流、请求校验、日志
├── routes/                 # API 路由（容器、网络、FRP、系统/设置）
├── services/
│   ├── container/          # 容器构建、生命周期、端口管理、信息查询
│   ├── frp/                # FRP 代理管理、配置解析、事件处理
│   └── network.py          # 受管网络服务
├── utils/                  # 销毁任务、端口工具、路径校验、告警
├── workers/                # 性能监控
├── frontend/               # Vue 3 WebUI 源码
└── static/                 # WebUI 构建产物（Flask 托管）
```

## WebUI
- **开关**：`ENABLE_WEBUI=True`（默认开启）
- **构建前端产物**：

```bash
cd frontend
npm install
npm run build
```

产物将输出到 `static/`，由 Flask 自动托管。

### WebUI 能做什么（新增）
- **受管网络管理**：在 Networks 页创建/编辑/删除受管网络，支持搜索与“占用中/空闲/已绑归属”等筛选
- **标签编辑体验**：使用 Key-Value 行编辑器编辑 `labels`（支持 `key=value` / `key: value`）
- **统一详情弹窗**：对容器/网络/FRP 等对象提供通用的详情展示（便于排障与复制字段）

## API 概览
所有接口均需在请求头中携带 `X-API-Key`。

### 容器

#### 单容器
| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/containers` | 创建容器 |
| `POST` | `/api/v1/containers/stream` | 创建容器（SSE 流式） |
| `GET` | `/api/v1/containers` | 容器列表 |
| `GET` | `/api/v1/containers/<id>` | 容器详情 |
| `PATCH` | `/api/v1/containers/<id>` | 重启容器 |
| `DELETE` | `/api/v1/containers/<id>` | 异步删除容器 |
| `GET` | `/api/v1/containers/<id>/destroy-status` | 删除任务状态 |
| `POST` | `/api/v1/containers/<id>/renew` | 续期容器 |

> 说明：容器列表/详情等查询与操作仅针对 **受管容器**（`moegate.managed=true`）；当没有受管容器时列表为空，不会展示宿主机其它容器。

#### 统一实体入口
适用于“调用方不确定传入的是单容器 ID 还是 Compose 项目 ID”的场景，后端会自动识别并路由到对应操作。

| 方法 | 路径 | 说明 |
|------|------|------|
| `PATCH` | `/api/v1/containers/restart/<id>` | 自动识别并重启（容器/项目） |
| `DELETE` | `/api/v1/containers/destroy/<id>` | 自动识别并异步删除（容器/项目） |
| `POST` | `/api/v1/containers/renew/<id>` | 自动识别并续期（容器/项目） |

#### Compose 项目
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/containers/project/<id>` | 项目详情 |
| `PATCH` | `/api/v1/containers/project/<id>` | 重启项目 |
| `DELETE` | `/api/v1/containers/project/<id>` | 异步删除项目 |
| `GET` | `/api/v1/containers/project/<id>/destroy-status` | 项目删除状态 |
| `POST` | `/api/v1/containers/project/<id>/renew` | 续期项目 |

### 网络
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/networks` | 受管网络列表 |
| `GET` | `/api/v1/networks/<id>` | 受管网络详情 |
| `POST` | `/api/v1/networks` | 创建受管网络 |
| `PUT` | `/api/v1/networks/<id>` | 更新受管网络 |
| `DELETE` | `/api/v1/networks/<id>` | 删除受管网络 |

> 说明：网络管理仅针对 **受管网络**（`moegate.managed=true`）。已被容器占用的网络不能更新或删除；更新采用“离线重建”策略，因此只允许修改空闲网络。

### FRP
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/frp/proxies` | 代理列表 |
| `POST` | `/api/v1/frp/proxies` | 创建代理 |
| `GET` | `/api/v1/frp/proxies/<name>` | 代理详情 |
| `PUT` | `/api/v1/frp/proxies/<name>` | 更新代理 |
| `DELETE` | `/api/v1/frp/proxies/<name>` | 删除代理 |
| `GET` | `/api/v1/frp/config` | 完整 FRP 配置 |
| `POST` | `/api/v1/frp/reload` | 热重载 FRP 配置 |
| `GET` | `/api/v1/frp/health` | FRP 健康检查 |
| `GET` | `/api/v1/frp/settings` | FRP 设置 |
| `PUT` | `/api/v1/frp/settings` | 更新 FRP 设置 |

### 系统
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/status` | 服务器状态 |
| `GET` | `/api/v1/metrics` | Prometheus 指标 |
| `POST` | `/api/v1/alerts/test` | 测试告警 |
| `GET/PUT` | `/api/v1/settings/alerts/webhook` | 告警 Webhook 设置 |
| `GET/PUT` | `/api/v1/settings/image-source` | 全局镜像源 |
| `GET/PUT` | `/api/v1/settings/webui` | WebUI 偏好 |
| `GET` | `/api/v1/settings/container-defaults` | 容器默认配置 |

### 示例

```bash
# 查看服务器状态
curl -s http://localhost:8080/api/v1/status \
  -H "X-API-Key: <your_key>"

# 从 Dockerfile 创建容器
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <your_key>" \
  -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/my-app", "max_time": 1800}'

# 从镜像创建容器
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <your_key>" \
  -H "Content-Type: application/json" \
  -d '{"image": "nginx:latest", "max_time": 3600}'

# 创建受管网络
curl -s -X POST http://localhost:8080/api/v1/networks \
  -H "X-API-Key: <your_key>" \
  -H "Content-Type: application/json" \
  -d '{"name": "lab-net", "subnet": "172.28.0.0/16", "gateway": "172.28.0.1", "attachable": true, "labels": {"env": "test"}}'
```

## FRP 使用说明
1. 在服务器上部署 **frps**：

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

2. 在运行 MoeGate 的机器上部署 **frpc**，启用 `webServer`：

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

> 如果设置了 `webServer.user` / `webServer.password`，需同步填写 `.env` 中的 `FRP_ADMIN_USER` / `FRP_ADMIN_PASSWORD`。

3. 在 `.env` 中配置 `FRP_*` 相关变量并设置 `ENABLE_FRP=True`
4. MoeGate 会在创建容器时自动通过 frpc 管理 API 注册/删除代理

## FAQ
### 为什么容器列表为空？
MoeGate 仅展示 `moegate.managed=true` 的**受管容器**，不会读取/操作宿主机其他容器。

### 为什么网络无法更新/删除？
受管网络在**被容器占用**时禁止更新/删除；更新采用离线重建策略，仅允许修改空闲网络。
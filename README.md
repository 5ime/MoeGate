# MoeGate - 轻量级 Docker 容器管理 API
MoeGate 支持通过 Dockerfile / Docker Compose / 镜像名称一键创建容器，自带到期自动销毁、续期、资源限制、FRP 内网穿透等功能。适用于 CTF / 靶场、临时演示环境、在线实验室等场景。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)![Flask](https://img.shields.io/badge/Flask-2.x-black)![Docker](https://img.shields.io/badge/Docker-Engine-2496ED)

![示例截图](https://github.com/user-attachments/assets/a087c14f-fab2-4748-a00a-173fa8ff0d65)

## 功能特性
- **多种创建模式** — Dockerfile 目录构建 / Docker Compose 编排 / 直接拉取镜像
- **生命周期管理** — 创建、重启、续期、异步销毁；到期自动清理
- **资源限制** — 内存、CPU 核数、CPU Shares 可按容器单独指定
- **端口管理** — 自动分配空闲端口或显式指定映射，线程安全
- **SSE 流式构建** — 前端可实时展示 `docker build` 日志
- **告警通知** — Webhook / 飞书机器人卡片消息
- **安全** — API Key 认证、IP 限流、路径白名单、CORS 白名单、请求体大小校验
- **受控管理** — 仅管理由 MoeGate 创建的容器（不会影响宿主机原有容器）
- **WebUI（可选）** — Vue 3 + Vite 单页面，开箱即用
- **FRP 内网穿透（可选）** — 创建容器后自动注册 frpc 代理，支持 TCP / HTTP（域名）

## 环境要求
| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | - |
| Docker Engine | 20.10+ | 需可通过 `/var/run/docker.sock` 访问 |
| Node.js | 18+ | 仅自行构建 WebUI 时需要 |

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
copy env.example .env
python app.py
```

> **首启必填项**
>
> | 环境变量 | 说明 | 示例 |
> |----------|------|------|
> | `API_KEY` | API 访问密钥（不可使用默认占位值） | 一个随机强密码 |
> | `ALLOWED_BASE_DIR` | 允许构建的目录白名单根路径 | `/var/containers` |
>
> 未正确配置时程序将拒绝启动。

## 项目结构
```
├── app.py                  # Flask 应用入口
├── config/                 # 配置加载与校验
├── core/                   # 事件总线、异常、日志、响应格式、关闭钩子
├── infra/                  # Docker 客户端管理
├── middleware/             # 认证、限流、请求校验、日志
├── routes/                 # API 路由（容器、FRP、系统/设置）
├── services/
│   ├── container/          # 容器构建、生命周期、端口管理、信息查询
│   └── frp/                # FRP 代理管理、配置解析、事件处理
├── utils/                  # 容器管理器、销毁、端口工具、路径校验、告警
├── workers/                # 性能监控
├── frontend/               # Vue 3 WebUI 源码
└── static/                 # WebUI 构建产物（Flask 托管）
```

## API 概览
所有接口均需在请求头中携带 `X-API-Key`。

### 容器
| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/containers` | 创建容器 |
| `POST` | `/api/v1/containers/stream` | 创建容器（SSE 流式） |
| `GET` | `/api/v1/containers` | 容器列表 |
| `GET` | `/api/v1/containers/<id>` | 容器详情 |
| `PATCH` | `/api/v1/containers/<id>` | 重启容器 |
| `DELETE` | `/api/v1/containers/<id>` | 异步删除容器 |
| `DELETE` | `/api/v1/containers/destroy/<id>` | 自动识别并异步删除（容器/项目） |
| `GET` | `/api/v1/containers/<id>/destroy-status` | 删除任务状态 |
| `POST` | `/api/v1/containers/<id>/renew` | 续期容器 |

> 说明：容器列表/详情等查询与操作仅针对 **受管容器**（`moegate.managed=true`）；当没有受管容器时列表为空，不会展示宿主机其它容器。

### Compose 项目
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/containers/project/<id>` | 项目详情 |
| `PATCH` | `/api/v1/containers/project/<id>` | 重启项目 |
| `DELETE` | `/api/v1/containers/project/<id>` | 异步删除项目 |
| `GET` | `/api/v1/containers/project/<id>/destroy-status` | 项目删除状态 |
| `POST` | `/api/v1/containers/project/<id>/renew` | 续期项目 |

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
```

## 配置参考
完整配置项见 `env.example`，下面列出按功能分组的核心参数。

### 服务
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_PORT` | `8080` | 监听端口 |
| `API_HOST` | `0.0.0.0` | 监听地址 |
| `API_DEBUG` | `False` | 调试模式（生产务必关闭） |
| `ENABLE_WEBUI` | `True` | 是否托管 WebUI 静态页面 |

### 容器
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MAX_TIME` | `3600` | 默认最大存活时间（秒） |
| `MAX_CONTAINERS` | `30` | 最大受管容器数 |
| `MIN_PORT` / `MAX_PORT` | `20000` / `30000` | 自动端口分配范围 |
| `MAX_RENEW_TIMES` | `3` | 最大续期次数 |
| `CONTAINER_MEMORY_LIMIT` | `512m` | 默认内存限制 |
| `CONTAINER_CPU_LIMIT` | — | 默认 CPU 核数限制 |
| `ALLOWED_BASE_DIR` | **必填** | 允许构建的目录白名单根路径 |

### 安全
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_KEY` | **必填** | API 访问密钥 |
| `RATE_LIMIT_PER_MIN` | `60` | 每 IP 每分钟最大请求数 |
| `TRUST_PROXY_HEADERS` | `False` | 是否信任 X-Forwarded-For 等代理头 |
| `CORS_ALLOWED_ORIGINS` | — | 跨域白名单（逗号分隔） |
| `ALLOW_RUNTIME_CONFIG_WRITE` | `False` | 允许 API 持久化写入 .env（生产建议关闭） |

### FRP（可选）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_FRP` | `False` | 启用后自动为容器创建 frpc 代理 |
| `FRP_SERVER_ADDR` | — | frps 地址（启用时必填） |
| `FRP_SERVER_PORT` | `7000` | frps 端口 |
| `FRP_ADMIN_IP` | `127.0.0.1` | frpc webServer 地址 |
| `FRP_ADMIN_PORT` | `7400` | frpc webServer 端口 |
| `FRP_USE_DOMAIN` | `False` | 启用 HTTP 代理（域名模式） |
| `FRP_DOMAIN_SUFFIX` | — | 域名后缀（如 `example.com`） |
| `FRP_VHOST_HTTP_PORT` | — | frps vhost http 端口 |

### 日志 / 监控
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | — | 日志级别，不设则自动按 DEBUG 判断 |
| `LOG_FILE` | — | 日志文件路径（启用文件日志） |
| `LOG_MAX_SIZE` | `10MB` | 单个日志文件最大大小（滚动日志） |
| `LOG_BACKUP_COUNT` | `5` | 保留的历史日志文件个数 |
| `ENABLE_PERFORMANCE_MONITORING` | `False` | 是否启用性能监控（记录 CPU/内存/容器数等） |
| `PERFORMANCE_LOG_INTERVAL` | `300` | 性能指标采样/记录间隔（秒） |
| `ALERT_WEBHOOK_URL` | — | 告警 Webhook（支持飞书机器人） |
| `ALERT_WEBHOOK_TIMEOUT` | `5` | 告警 Webhook 请求超时时间（秒） |
| `ALERT_CPU_THRESHOLD` | `95` | CPU 告警阈值（百分比） |
| `ALERT_CPU_SUSTAINED_INTERVALS` | `3` | CPU 连续超过阈值多少个采样区间后触发告警 |
| `ALERT_MEM_THRESHOLD` | `90` | 内存告警阈值（百分比） |
| `ALERT_MEM_SUSTAINED_INTERVALS` | `3` | 内存连续超过阈值多少个采样区间后触发告警 |
| `ALERT_COOLDOWN_SEC` | `900` | 告警冷却时间（秒，冷却期内不重复发送同类告警） |

## WebUI
- 开关：`ENABLE_WEBUI=True`（默认开启）
- 构建前端产物：
```bash
cd frontend
npm install
npm run build
```
产物将输出到 `static/`，由 Flask 自动托管。也可使用预构建的 `static/index.html`。

## FRP 使用说明
1. 在服务器上部署 **frps**：
   ```toml
   # frps.toml
   bindPort = 7000
   bindAddr = "0.0.0.0"

   # HTTP 代理端口
   vhostHTTPPort = 80

   # 鉴权配置（可选）
   [auth]
   method = "token"              # 鉴权方式，可选值：token 或 oidc
   token = "your-strong-random-token"     # 如果设置了 token，客户端也需要配置相同的 token

   # 日志配置（可选）
   [log]
   level = "info"                # 日志级别：trace, debug, info, warn, error
   maxDays = 3                   # 日志文件最大保留天数
   to = "frps.log"
   ```

2. 在运行 MoeGate 的机器上部署 **frpc**，启用 `webServer`：
   ```toml
   # frpc.toml
   serverAddr = "124.221.191.235"
   serverPort = 7000

   [auth]
   method = "token"
   token = "your-strong-random-token"

   # 管理 API
   [webServer]
   addr = "127.0.0.1"
   port = 7400
   user = "admin"
   password = "admin"
   ```

   > 如果设置了 `webServer.user` / `webServer.password`，需同步填写 `.env` 中的 `FRP_ADMIN_USER` / `FRP_ADMIN_PASSWORD`。

3. 在 `.env` 中配置 `FRP_*` 相关变量并设置 `ENABLE_FRP=True`
4. MoeGate 会在创建容器时自动通过 frpc 管理 API 注册/删除代理
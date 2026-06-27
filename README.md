# MoeGate

轻量级 Docker 容器管理网关，专为 CTF 动态靶机、在线实验室与临时演示环境设计。支持 Dockerfile、Docker Compose 与镜像快速部署，提供自动销毁、FRP 穿透、资源限制与 WebUI 管理能力。

![Python](https://img.shields.io/badge/Python-3.11-blue) ![Flask](https://img.shields.io/badge/Flask-3.1-black) ![Docker](https://img.shields.io/badge/Docker-Engine-2496ED)

![示例截图](https://github.com/user-attachments/assets/b8f64b98-7ca0-4417-aef6-3bf50b1b7f66)

## 特性

**专为 CTF 动态靶场设计** — Compose 模板变量解析、多 service 独立 FLAG 注入，开箱即用。

### 容器编排

- 多模式创建：Dockerfile 构建 / Docker Compose 编排 / 镜像名称拉取
- 动态变量注入：支持 Compose 模板变量解析，创建时自动完成参数替换
- 多 FLAG 支持：多服务环境可独立注入 FLAG，支持自定义变量映射规则
- 环境变量继承：支持 API 与 WebUI 动态传参，自动合并至所有服务实例
- 生命周期管理：自动到期销毁、续期、重启，异步删除

### 资源与网络

- 资源限制：内存、CPU 核数、CPU Shares
- 端口管理：线程安全的自动分配，范围可配
- 受管网络：子网/网关校验，Compose 项目自动分配子网
- FRP 穿透：容器创建后自动注册 frpc 代理，支持 TCP/HTTP

### 运维能力

- SSE 流式日志：构建和拉取镜像过程实时输出
- 告警 Webhook：支持通用 JSON 与飞书机器人卡片（`POST /api/v1/alerts/test` 手动测试）
- 受管镜像：自动登记、悬空清理、引用关系约束

### 安全与隔离

- 双模式 API 认证：脚本/API 使用 `X-API-Key` Header；WebUI 使用 Cookie Session（密钥不进入 JavaScript）
- Cookie 模式下变更类请求启用 CSRF 防护（Double-Submit Cookie）
- IP 限流、路径白名单、CORS、请求体校验；可选 WebUI Basic 认证
- 容器隔离：只管理 MoeGate 创建的容器（`moegate.managed=true`），不影响宿主机

### WebUI

- Vue 3 + Tailwind CSS，容器/镜像/网络/FRP/系统设置一站式管理
- 登录后通过 HttpOnly Cookie 调用 API，无需在浏览器存储密钥

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env   # 编辑 .env
python app.py
```

启动后访问 `http://localhost:8080`。环境要求：**Python 3.11**（与 Docker 镜像一致），建议使用虚拟环境隔离依赖，详见 [docs/deploy.md](docs/deploy.md)。

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
utils/                  # 销毁任务、端口工具、路径校验、告警、镜像登记、Docker 镜像解析
frontend/               # Vue 3 WebUI 源码
static/                 # WebUI 构建产物
deploy/compose/         # Docker Compose 叠加示例（FRP、Socket Proxy）
```

## API

完整 API 文档见 [docs/api.md](docs/api.md)。

`/api/v1/*` 接口支持两种认证方式（二选一）：

- **Header**：请求头 `X-API-Key`（适合 curl、自动化脚本）
- **Cookie**：WebUI 登录后写入 HttpOnly Session Cookie（生产推荐）

主要接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/containers` | 创建容器 |
| `GET` | `/api/v1/containers` | 容器列表 |
| `DELETE` | `/api/v1/containers/<id>` | 删除容器 |
| `POST` | `/api/v1/images/pull` | 拉取镜像 |
| `GET` | `/api/v1/status` | 服务状态 |

```bash
# 从 Compose 创建，并注入全局环境变量
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/ctf-lab", "max_time": 3600, "env": {"DEDE_FLAG": "flag{custom}"}}'
```

## Compose 变量替换

Compose 文件的 `environment` 和 `command` 支持 `${VAR}` 占位符，MoeGate 会在启动前完成解析：

```yaml
services:
  web:
    image: nginx:latest
    environment:
      - FLAG=${FLAG}
    command: ["/bin/sh", "-c", "echo '${FLAG}' > /flag && nginx -g 'daemon off;'"]
```

- 创建时传入的 `env` 会作为全局变量合并进各 service
- compose 文件中已写明的变量优先保留
- 被引用但未赋值的变量（常见如 `FLAG`）会自动生成 `flag{uuid}` 格式的唯一值
- **多 service 项目里，每个 service 各自生成独立 FLAG**，避免共用同一个 flag

自定义变量名同样生效，例如 `env: {"DEDE_FLAG": "flag{xxx}"}` 可配合 compose 中的 `${DEDE_FLAG}` 使用。

> **注意**：MoeGate 使用简化 Compose 子集，支持 `image`/`build`/`ports`/`command`/`environment`/`networks`、**bind mount `volumes`**、`privileged`（`COMPOSE_POLICY=ctf` 时）等；**named volume**、`network_mode: host` 等不支持。详见 [docs/compose.md](docs/compose.md)。

## 文档

| 文档 | 说明 |
|------|------|
| [docs/api.md](docs/api.md) | 完整 API 参考 |
| [docs/deploy.md](docs/deploy.md) | 部署、配置与前端开发 |
| [docs/SECURITY.md](docs/SECURITY.md) | 安全说明与威胁模型 |
| [docs/frp.md](docs/frp.md) | FRP 穿透配置 |
| [docs/compose.md](docs/compose.md) | Compose 变量替换机制 |
| [deploy/compose/README.md](deploy/compose/README.md) | Docker Compose 叠加示例（Socket Proxy、FRP） |

## FAQ

**为什么看不到宿主机容器？** MoeGate 默认只管理自身创建的资源（`moegate.managed=true`），避免误删或影响现有业务。

**支持 Docker Swarm / Kubernetes 吗？** 当前仅支持 Docker Engine 与 Docker Compose。

**容器列表为空？** 同上，MoeGate 只展示自己创建的容器。

**网络无法更新/删除？** 被容器占用的网络禁止操作，需先释放容器。

**镜像删除失败？** 可能仍被容器引用，或同一镜像有多个 tag 需要 `force=true`。

**设置重启后丢失？** 通过 API 修改的设置仅在当前进程内存生效，重启后恢复为 `.env` / 环境变量中的启动配置。

**续期/到期时间存在哪里？** 创建时在容器 labels 写入初始值；因 Docker labels 创建后不可变，续期与到期变更会同步写入 `ALLOWED_BASE_DIR/.moegate/lifecycle.json`，以便进程重启后恢复定时器。删除容器时会清理对应记录。

**告警会自动推送吗？** 当前版本仅支持配置 Webhook 并通过 `POST /api/v1/alerts/test` 手动测试；飞书机器人 URL 会自动适配卡片格式。容器异常等资源告警尚未自动触发。

# FRP 配置

MoeGate 可在容器创建后自动向 frpc 注册代理，删除容器时自动清理。启用前需部署 frps 与 frpc，并在 `.env` 中配置 `FRP_*` 变量。

## 1. 部署 frps

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

# 允许 MoeGate 分配的 remotePort 范围（须与 .env 中 MIN_PORT / MAX_PORT 一致）
[[allowPorts]]
start = 20000
end = 30000

# 日志配置（可选）
[log]
level = "info"
maxDays = 3
to = "frps.log"
```

## 2. 部署 frpc

frpc 需启用 `webServer`，供 MoeGate 调用管理 API：

```toml
# frpc.toml
serverAddr = "frps.example.com"
serverPort = 7000

[auth]
method = "token"
token = "your-strong-random-token"

[webServer]
addr = "0.0.0.0"
port = 7400
user = "admin"
password = "admin"
```

同机 Docker 部署时，使用 `deploy/compose/frp.example.yml` 可将 moegate 的 `FRP_ADMIN_IP` 设为 Compose 服务名 `frpc`（见该文件中的 `environment` 覆盖）。

**Docker 内运行 frpc 时注意：**

1. `frpc.toml` 挂载到容器时**不要**加 `:ro`，MoeGate 会通过 frpc 管理 API 热更新配置并写回文件。
2. frpc 在容器内无法通过 `127.0.0.1` 访问宿主机端口映射，需设置 `FRP_LOCAL_IP=host.docker.internal`，并为 frpc 服务配置 `extra_hosts: host.docker.internal:host-gateway`（`frp.example.yml` / `frpc.example.yml` 已包含）。
3. 本地联调可使用根目录 `docker-compose.frp-test.yml`（详见 [deploy/compose/README.md](../deploy/compose/README.md)）。

## 3. MoeGate 配置

在 `.env` 中设置 `FRP_*` 变量。WebUI / `PUT /api/v1/frp/settings` 可调整开关、服务端地址、管理 API 等运行态字段；**`FRP_LOCAL_IP` 仅通过 `.env` 或进程启动环境变量生效**，不在运行态 API 中，修改后须重启 MoeGate。

### 裸机部署（frpc 与 MoeGate 同机、非容器）

```bash
ENABLE_FRP=True
FRP_SERVER_ADDR=frps.example.com
FRP_SERVER_PORT=7000
FRP_ADMIN_IP=127.0.0.1
FRP_ADMIN_PORT=7400
FRP_ADMIN_USER=admin
FRP_ADMIN_PASSWORD=admin
FRP_LOCAL_IP=127.0.0.1
```

### Docker Compose 部署（frpc 为 Compose 服务）

与 `deploy/compose/frp.example.yml` 或 `docker-compose.frp-test.yml` 配合时，管理 API 走 Docker 网络内服务名，localIP 指向宿主机：

```bash
ENABLE_FRP=True
FRP_SERVER_ADDR=frps
FRP_SERVER_PORT=7000
FRP_ADMIN_IP=frpc
FRP_ADMIN_PORT=7400
FRP_ADMIN_USER=admin
FRP_ADMIN_PASSWORD=admin
FRP_LOCAL_IP=host.docker.internal
```

`FRP_LOCAL_IP` 默认为 `127.0.0.1`（裸机同机 frpc）。frpc 运行在 Docker 容器内时请设为 `host.docker.internal`（Linux 容器另需 `extra_hosts`，见上文 §2）。

可选：HTTP 虚拟主机模式

```bash
FRP_USE_DOMAIN=True
FRP_DOMAIN_SUFFIX=container.example.com
FRP_VHOST_HTTP_PORT=80
```

## 4. 工作流程

1. 容器创建时，MoeGate 根据端口映射自动注册 frpc 代理（支持 TCP / HTTP）
2. **Compose 多 service** 时，每个有端口映射的服务都会注册独立代理；HTTP 域名模式使用 `{service}-{project_tag}.{FRP_DOMAIN_SUFFIX}`（例如 `web-550e8400.example.com`）
3. 多 service / 多端口场景下，FRP 配置会**批量写入** frpc，减少竞态
4. 无端口映射的内部 service（如纯 DB）会自动跳过 FRP 注册
5. 容器删除时，对应代理自动清理（含同一容器的多端口代理）
6. 也可通过 [FRP API](api.md#frp) 手动管理代理

### 运行态 API 可写字段（`PUT /api/v1/frp/settings`）

| 字段 | 说明 |
|------|------|
| `enabled` | 开关（bool） |
| `server_addr` / `server_port` | frps 地址与端口 |
| `admin_ip` / `admin_port` / `admin_user` / `admin_password` | frpc 管理 API |
| `use_domain` / `domain_suffix` / `vhost_http_port` | HTTP 虚拟主机 |

`FRP_LOCAL_IP` **不在**运行态 API 中，仅 `.env` / 启动环境变量生效。

完整环境变量说明见 [deploy.md](deploy.md) 与根目录 `env.example`。

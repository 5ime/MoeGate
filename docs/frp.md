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
addr = "127.0.0.1"
port = 7400
user = "admin"
password = "admin"
```

## 3. MoeGate 配置

在 `.env` 中设置：

```bash
ENABLE_FRP=True
FRP_SERVER_ADDR=frps.example.com
FRP_SERVER_PORT=7000
FRP_ADMIN_IP=127.0.0.1
FRP_ADMIN_PORT=7400
FRP_ADMIN_USER=admin
FRP_ADMIN_PASSWORD=admin
```

可选：HTTP 虚拟主机模式

```bash
FRP_USE_DOMAIN=True
FRP_DOMAIN_SUFFIX=container.example.com
FRP_VHOST_HTTP_PORT=80
```

## 4. 工作流程

1. 容器创建时，MoeGate 根据端口映射自动注册 frpc 代理（支持 TCP / HTTP）
2. 容器删除时，对应代理自动清理
3. 也可通过 [FRP API](api.md#frp) 手动管理代理

完整环境变量说明见 [deploy.md](deploy.md) 与根目录 `env.example`。

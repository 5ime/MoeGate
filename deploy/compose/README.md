# Docker Compose 叠加示例

本目录提供与根目录 `docker-compose.yml` **叠加使用**的示例文件，用于生产加固或可选组件。

## Socket Proxy（推荐生产）

MoeGate 经 `docker-socket-proxy` 访问 Docker，不直接挂载 `docker.sock`；代理侧禁用 EXEC、SWARM 等高危端点。

在仓库根目录执行：

```bash
docker compose -f docker-compose.yml -f deploy/compose/socket-proxy.example.yml up -d --build
```

| 文件 | 说明 |
|------|------|
| [socket-proxy.example.yml](./socket-proxy.example.yml) | 叠加片段，覆盖 `moegate` 的 `volumes` / `environment` / `depends_on` |

**要求 Docker Compose v2.24+**：叠加文件对 `moegate.volumes` 使用 `!reset`，用于移除根 `docker-compose.yml` 中的 `/var/run/docker.sock` 挂载。

## FRP 同机部署

与 MoeGate 同机运行 frpc 客户端：

```bash
docker compose -f deploy/compose/frp.example.yml up -d --build
```

若 frps 也需在本机 Compose 中启动，可叠加 [frps.example.yml](./frps.example.yml)：

```bash
cp deploy/compose/frps.example.toml deploy/compose/frps.toml
docker compose -f deploy/compose/frp.example.yml -f deploy/compose/frps.example.yml up -d --build
```

| 文件 | 说明 |
|------|------|
| [frp.example.yml](./frp.example.yml) | 独立 compose，通过 `extends` 引用根 `docker-compose.yml` 中的 `moegate` 服务 |
| [frpc.example.yml](./frpc.example.yml) | 与根 `docker-compose.yml` 叠加，仅追加 frpc |
| [frps.example.yml](./frps.example.yml) | 与 `frp.example.yml` 叠加，提供同网 frps |
| [frps.example.toml](./frps.example.toml) | frps 配置模板，复制为同目录 `frps.toml`（已在 `.gitignore`） |

部署前请准备：

1. 仓库根目录的 `frpc.toml`（详见 [docs/frp.md](../../docs/frp.md)）
2. `frpc.toml` 中 `[webServer]` 的 `addr` 设为 `0.0.0.0`（容器内需对 moegate 暴露管理端口）
3. `.env` 中 `ENABLE_FRP=True` 并配置其余 `FRP_*` 变量
4. 使用 `frps.example.yml` 时：`cp deploy/compose/frps.example.toml deploy/compose/frps.toml`，并调整 token 与 `[[allowPorts]]` 与 `.env` 端口池一致

示例 compose 已将 moegate 的 `FRP_ADMIN_IP` 覆盖为 `frpc`、`FRP_LOCAL_IP` 设为 `host.docker.internal`，并为 frpc 配置了 `extra_hosts`。

## 本地 FRP 联调（WSL / Docker Desktop）

在仓库根目录叠加 `docker-compose.frp-test.yml`，同网启动 frps + frpc + moegate：

```bash
cp deploy/compose/frps.example.toml deploy/compose/frps.toml
docker compose -f docker-compose.yml -f docker-compose.frp-test.yml up -d --build
```

| 文件 | 说明 |
|------|------|
| [../../docker-compose.frp-test.yml](../../docker-compose.frp-test.yml) | 根目录叠加片段：frps、frpc、`FRP_LOCAL_IP=host.docker.internal` |
| [frps.example.toml](./frps.example.toml) | frps 示例配置，复制为同目录 `frps.toml`（已在 `.gitignore`） |

**注意：**

- `frpc.toml` 必须以**可写**方式挂载（勿 `:ro`）。
- Docker Desktop 上不宜一次性映射上万 remotePort；本地测试可缩小 `.env` 中的 `MAX_PORT`，或直接在 WSL 宿主机运行 frps/frpc。
- 本 compose 仅将 frps 的 **7000** 映射到宿主机；`MIN_PORT`–`MAX_PORT` 段未映射。代理可正常注册，但从宿主机访问 `localhost:<remotePort>` **可能不通**，除非自行添加端口映射、缩小端口池，或在 WSL/Linux 宿主机直接运行 frps。

## 组合使用

Socket Proxy 与 FRP 可分别按需叠加；若需同时启用，可自行合并两个文件中的 `services` 段，或维护本地 `docker-compose.override.yml`（该文件通常不入库，见 `.gitignore`）。

更多部署说明见 [docs/deploy.md](../../docs/deploy.md) 与 [docs/SECURITY.md](../../docs/SECURITY.md)。

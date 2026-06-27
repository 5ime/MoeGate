# Compose 变量替换

Compose 文件的 `environment` 和 `command` 支持 `${VAR}` 占位符，MoeGate 会在启动前完成解析。这是 MoeGate 与 Portainer、Dockge 等同类工具的核心差异之一，专为 CTF 动态靶场场景设计。

## 基本示例

```yaml
services:
  vulhub_redis:
    image: vulhub/redis:4.0.14
    command: ["/bin/sh", "-c", "echo '${FLAG}' > /flag && docker-entrypoint.sh redis-server"]
```

## 规则说明

- 创建时传入的 `env` 会作为全局变量合并进各 service
- compose 文件中已写明的变量优先保留
- 被引用但未赋值的变量（常见如 `FLAG`）会自动生成 `flag{uuid}` 格式的唯一值
- **多 service 项目里，每个 service 各自生成独立 FLAG**，避免共用同一个 flag

## 自定义变量名

自定义变量名同样生效，例如 `env: {"DEDE_FLAG": "flag{xxx}"}` 可配合 compose 中的 `${DEDE_FLAG}` 使用：

```bash
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/ctf-lab", "max_time": 3600, "env": {"DEDE_FLAG": "flag{custom}"}}'
```

## 多 service 场景

```yaml
services:
  web:
    image: nginx:latest
    environment:
      - FLAG=${FLAG}
  db:
    image: mysql:8
    environment:
      - FLAG=${FLAG}
```

上述 compose 启动后，`web` 与 `db` 各自获得不同的 `FLAG` 值，适合 CTF 中需要 per-service 独立 flag 的题型。

## MoeGate Compose SDK 子集

MoeGate 通过 **Docker SDK 直接创建容器**（非 `docker compose` CLI），在保留受控网络、随机端口池、FRP 注册与 TTL 的前提下，支持以下字段。

**路径解析**：`path` 目录内按 `docker-compose.yaml` → `docker-compose.yml` → `Dockerfile` 顺序选择配置文件。

| 字段 | 说明 |
|------|------|
| `image` / `build` | 镜像拉取或 Dockerfile 构建（build context 受路径白名单约束） |
| `ports` | 宿主机端口由 MoeGate 自动分配（落在 `MIN_PORT`–`MAX_PORT`）；YAML 中勿写固定 host port |
| `command` | 启动命令，支持 `${VAR}` 替换 |
| `environment` | 环境变量，支持 `${VAR}` 替换与全局 `env` 合并 |
| `networks` | 受管 Compose 网络与子网分配 |
| `volumes` | **仅 bind mount**；宿主机路径须在 `ALLOWED_BASE_DIR` 内，禁止挂载 Docker Socket 等敏感路径 |
| `privileged` | 特权容器（`COMPOSE_POLICY=strict` 时拒绝） |
| `cap_add` / `cap_drop` | Linux capabilities（strict 模式拒绝部分高危 cap） |
| `depends_on` | 仅决定**启动顺序**，不等待 healthcheck |
| API `resource_limits` | 内存/CPU 限制（映射到容器创建参数） |

### 永久不支持的字段

以下字段与 MoeGate 的受控网络 / 随机端口模型冲突，或尚未实现。配置了这些字段时：

- 默认 **`COMPOSE_UNSUPPORTED=warn`**：记录日志并在 API 响应的 `compose_warnings` 中提示
- 设为 **`COMPOSE_UNSUPPORTED=error`**：直接拒绝启动

| 字段 | 原因 |
|------|------|
| `network_mode: host` | 绕过端口映射与 FRP 注册 |
| `healthcheck` | 未实现 health 等待语义 |
| `deploy` | 除 API 传入 `resource_limits` 外不生效 |
| `ipc: host` / `pid: host` | 未通过 SDK 实现；strict 模式额外拒绝 |

**named volume**（如 `mydata:/var/lib/mysql`）不受支持，请改用 bind mount。

### 配置项

| 环境变量 | 取值 | 说明 |
|----------|------|------|
| `COMPOSE_POLICY` | `ctf`（默认） / `strict` | strict 拒绝 privileged、敏感 mount、高危 cap 等 |
| `COMPOSE_UNSUPPORTED` | `warn`（默认） / `error` | 对永久不支持字段的处理方式 |

生产环境建议：`COMPOSE_POLICY=strict` + `COMPOSE_UNSUPPORTED=error`。

## 相关 API

创建容器时通过 `env` 字段传参，详见 [api.md](api.md#创建参数)。

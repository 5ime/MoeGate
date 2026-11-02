# Compose 变量替换

Compose 文件的 `environment` 和 `command` 支持 `${VAR}` 占位符，MoeGate 会在启动前完成解析。这是 MoeGate 与 Portainer、Dockge 等同类工具的核心差异之一，专为 CTF 动态靶场场景设计。

## 基本示例

```yaml
services:
  vulhub_redis:
    image: vulhub/redis:4.0.14
    command: ["/bin/sh", "-c", "echo '${FLAG}' > /flag && docker-entrypoint.sh redis-server"]
```

## 三种 FLAG 模式

| 模式 | 场景 | 上游传参 | 行为 |
|------|------|----------|------|
| 1. 单容器单 FLAG | 单 service / 镜像 / Dockerfile | `env: {"FLAG": "flag{xxx}"}` | `env` **完整注入**容器，compose 里写不写 `${FLAG}` 都生效 |
| 2. 多容器多 FLAG | 多 service，各容器一道独立题 | `env: {"DEDECMS_FLAG": "f1", "XINHU_FLAG": "f2"}` | 按变量名对号入座，各 service 只拿到自己引用的那个槽位 |
| 3. 多容器单 FLAG（默认） | 多 service 协同出题，如 SSRF 入口 + 内网 flag 服务 | `env: {"FLAG": "flag{xxx}"}` | 下发的 `FLAG` 注入**所有** service，多容器共用同一个值 |

模式 2 与模式 3 可以共存：自定义槽位（`${DEDECMS_FLAG}` 等）始终按名字透传，只有名为 `FLAG` 的变量被当作共享槽位。

## 规则说明

- **模式 1**：API 传入的 `env` **完整注入**容器（即使 compose 未写 `${FLAG}`）。上游单 FLAG 场景应传 `env.FLAG`，MoeGate 原样写入。
- **模式 2**：`env` 仅注入各 service 在 `environment` / `command` 中实际引用的 `${VAR}`，避免其它服务的变量泄漏
- **模式 3**：下发的 `FLAG` 注入所有 service，且**优先于 compose 中写死的同名值**；未下发（含空值）时引用 `${FLAG}` 的 service 各自生成 `flag{uuid}`，并记录 warning、同时出现在 API 响应 `data[].compose_warnings` 中提示平台无法校验
- 被引用但未赋值的变量会自动生成 `flag{uuid}` 格式的唯一值
- 需要「多容器、每容器各自不同 flag」时，用不同的自定义变量名（`${WEB_FLAG}` / `${DB_FLAG}`）各自下发，
  即模式 2；MoeGate 不会凭空生成平台无法校验的 flag

## 自定义变量名（模式 2）

自定义变量名即独立的 FLAG 槽位，例如 `env: {"DEDE_FLAG": "flag{xxx}"}` 配合 compose 中的 `${DEDE_FLAG}` 使用：

```bash
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/ctf-lab", "max_time": 3600, "env": {"DEDE_FLAG": "flag{custom}"}}'
```

## 多容器单 FLAG（模式 3，默认）

多容器协同题目最常见的形态：平台只下发一个 flag，入口容器与内网服务必须拿到**同一个**值，
否则平台校验必然失败。

```yaml
services:
  healthscan:
    build: ../
    environment:
      - FLAG=${FLAG}      # 写了会被替换成下发值
  opsagent:
    build: ../opsagent
    environment:
      - FLAG=${FLAG}
```

调用：

```bash
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/ssrf/docker", "max_time": 3600, "env": {"FLAG": "flag{xxx}"}}'
```

两个 service 都会拿到 `flag{xxx}`。即使某个 service 没写 `${FLAG}`，下发值同样会注入，
无需在 compose 中逐个声明；compose 里写死的占位 flag（如 `FLAG: "flag{test}"`）会被下发值覆盖。

## MoeGate Compose SDK 子集

MoeGate 通过 **Docker SDK 直接创建容器**（非 `docker compose` CLI），在保留受控网络、随机端口池、FRP 注册与 TTL 的前提下，支持以下字段。

**路径解析**：`path` 目录内按 `docker-compose.yaml` → `docker-compose.yml` → `Dockerfile` 顺序选择配置文件（不递归子目录）。

| 字段 | 说明 |
|------|------|
| `image` / `build` | 镜像拉取或 Dockerfile 构建（build context 受路径白名单约束） |
| `ports` | 宿主机端口由 MoeGate 自动分配（落在 `MIN_PORT`–`MAX_PORT`）；YAML 中勿写固定 host port |
| `command` | 启动命令，支持 `${VAR}` 替换 |
| `environment` | 环境变量，支持 `${VAR}` 替换与全局 `env` 合并 |
| `networks` | 受管 Compose 网络与子网分配；`external: true` 只允许引用本平台创建的网络 |
| `volumes` | **仅 bind mount**；宿主机路径须在 `ALLOWED_BASE_DIR` 内，禁止挂载 Docker Socket 等敏感路径 |
| `privileged` | 特权容器（`COMPOSE_POLICY=strict` 时拒绝；`ctf` 放行但会在 `compose_warnings` 提示） |
| `cap_add` / `cap_drop` | Linux capabilities（strict 模式拒绝高危 cap；ctf 模式对高危 cap 给出提示） |
| `depends_on` | 仅决定**启动顺序**，不等待 healthcheck |
| API `resource_limits` | 内存/CPU 限制（映射到容器创建参数）；单容器上限 64G / 64 核 |

> **服务名互访**：MoeGate 会把每个 service 名注册为所在网络的别名（含 `networks` 中声明的额外网络），
> 因此 `web` 内可以直接 `curl http://api:8080`、`api` 内可以访问 `http://db:3306`，与 `docker compose` 行为一致。
> 仍建议 compose 显式声明 `networks:`，否则容器落在默认 bridge 上，服务名解析与内部流量取证都不可靠。

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

`networks` 中的 `external: true` 会被校验：目标网络必须带 `moegate.managed=true` 标签（即由 MoeGate 创建），
否则拒绝启动——避免靶机被接进宿主机上任意既有网络。

### 配置项

| 环境变量 | 取值 | 说明 |
|----------|------|------|
| `COMPOSE_POLICY` | `ctf`（默认） / `strict` | strict 拒绝 privileged、敏感 mount、高危 cap 等；ctf 放行但在响应 `compose_warnings` 中提示 |
| `COMPOSE_UNSUPPORTED` | `warn`（默认） / `error` | 对永久不支持字段的处理方式 |

生产环境建议：`COMPOSE_POLICY=strict` + `COMPOSE_UNSUPPORTED=error`。

## 相关 API

创建容器时通过 `env` 字段传参，详见 [api.md](api.md#创建参数)。

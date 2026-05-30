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

## 相关 API

创建容器时通过 `env` 字段传参，详见 [api.md](api.md#创建参数)。

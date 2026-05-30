# API 文档

所有接口需要 `X-API-Key` 请求头，基础路径为 `/api/v1`。

## 容器

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

### 统一入口

自动识别单容器或 Compose 项目：

| 方法 | 路径 | 说明 |
|------|------|------|
| `PATCH` | `/api/v1/containers/restart/<id>` | 重启 |
| `DELETE` | `/api/v1/containers/destroy/<id>` | 删除 |
| `POST` | `/api/v1/containers/renew/<id>` | 续期 |

### Compose 项目

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/containers/project/<id>` | 项目详情 |
| `PATCH` | `/api/v1/containers/project/<id>` | 重启项目 |
| `DELETE` | `/api/v1/containers/project/<id>` | 删除项目 |
| `GET` | `/api/v1/containers/project/<id>/destroy-status` | 删除状态 |
| `POST` | `/api/v1/containers/project/<id>/renew` | 续期项目 |

## 镜像

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/images` | 受管镜像列表 |
| `GET` | `/api/v1/images/detail/<ref>` | 镜像详情 |
| `POST` | `/api/v1/images/pull` | 拉取镜像 |
| `POST` | `/api/v1/images/pull/stream` | 拉取镜像（SSE） |
| `DELETE` | `/api/v1/images/<ref>` | 删除镜像（`?force=true` 强制） |
| `POST` | `/api/v1/images/prune` | 清理悬空镜像 |

## 网络

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/networks` | 受管网络列表 |
| `GET` | `/api/v1/networks/<id>` | 网络详情 |
| `POST` | `/api/v1/networks` | 创建网络 |
| `PUT` | `/api/v1/networks/<id>` | 更新网络（离线重建） |
| `DELETE` | `/api/v1/networks/<id>` | 删除网络 |

被容器占用的网络不可更新或删除。

## FRP

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

## 系统

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

## 创建参数

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | string | Dockerfile / docker-compose.yaml 所在目录 |
| `image` | string | 镜像名称（与 `path` 二选一） |
| `env` | object | 全局环境变量，键值均为字符串 |
| `max_time` | int | 最大运行时长（秒） |
| `port_mappings` | string | 固定端口映射，如 `8080:80,8443:443` |

`env` 会传入 Compose 各 service，并与 compose 文件中的 `environment` 合并。Compose 里 `${VAR}` 占位符会被解析；未赋值且被引用的变量（如 `FLAG`）会自动生成唯一值。多 service 场景下，每个 service 各自获得独立的 `FLAG`。

Compose 变量替换机制详见 [compose.md](compose.md)。

## 示例

```bash
# 状态
curl -s http://localhost:8080/api/v1/status -H "X-API-Key: <key>"

# 从 Dockerfile 创建
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/my-app", "max_time": 1800}'

# 从 Compose 创建，并注入全局环境变量
curl -s -X POST http://localhost:8080/api/v1/containers \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"path": "/var/containers/ctf-lab", "max_time": 3600, "env": {"DEDE_FLAG": "flag{custom}"}}'

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

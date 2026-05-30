# 部署指南

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | |
| Docker Engine | 20.10+ | 需可访问 Docker Daemon |
| Node.js | 18+ | 仅构建 WebUI 时需要 |

## 快速部署

```bash
pip install -r requirements.txt
cp env.example .env   # 编辑 .env
python app.py
```

启动后访问 `http://localhost:8080`。

## 配置说明

完整配置见根目录 `env.example`，以下为必填项和常用项：

| 变量 | 必填 | 说明 |
|------|------|------|
| `API_KEY` | **是** | API 密钥，不可用默认占位值 |
| `ALLOWED_BASE_DIR` | **是** | Dockerfile/Compose 构建路径白名单根目录 |
| `ENABLE_WEBUI` | | 是否托管 WebUI（默认 `True`） |
| `IMAGE_SOURCE` | | 全局镜像前缀，拉取镜像时自动拼接 |
| `MAX_CONTAINERS` | | 最大同时运行容器数（默认 `30`） |
| `MAX_TIME` | | 容器最大运行时长，秒（默认 `3600`） |
| `MIN_PORT` / `MAX_PORT` | | 端口映射范围（默认 `20000`-`30000`） |
| `CONTAINER_MEMORY_LIMIT` | | 内存限制（默认 `512m`） |
| `CONTAINER_CPU_LIMIT` | | CPU 核数限制 |
| `ENABLE_FRP` | | 启用 FRP 穿透（需配置 `FRP_*` 变量） |
| `ALLOW_RUNTIME_CONFIG_WRITE` | | 允许通过 API 持久化设置到 `.env`（默认 `False`） |
| `COMPOSE_MANAGED_SUBNET_POOL` | | Compose 子网地址池（默认 `172.30.0.0/16`） |

## 生产环境建议

- 将 `API_DEBUG` 设为 `False`
- 替换 `API_KEY` 为强随机密钥
- 谨慎配置 `ALLOWED_BASE_DIR`，防止目录越权
- 保持 `ALLOW_RUNTIME_CONFIG_WRITE=False`，避免 API 误改持久化配置
- 若部署在反向代理后，按需启用 `TRUST_PROXY_HEADERS`（确保代理层可信）
- 配置 `CORS_ALLOWED_ORIGINS` 限制跨域来源

## 前端开发

默认后端托管 `static/` 下的构建产物。如需热更新开发：

```bash
# 1. 后端：.env 中设置 ENABLE_WEBUI=False，然后
python app.py

# 2. 前端
cd frontend && npm install && npm run dev
```

Vite 已配置代理，开发模式下 `/api` 请求会自动转发到后端。

构建产物：

```bash
cd frontend && npm run build
# 输出到 static/，Flask 自动托管
```

## FRP 穿透

详见 [frp.md](frp.md)。

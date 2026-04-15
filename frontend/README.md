# MoeGate WebUI

MoeGate 的前端管理面板，基于 Vue 3 + Vite + Tailwind CSS 构建。

## 技术栈

- **Vue 3** (Composition API)
- **Vite 5** 构建工具
- **Tailwind CSS 3** 样式
- **uPlot** 趋势图表

## 开发

```bash
npm install
npm run dev
```

启动后访问 `http://127.0.0.1:5173`。`/api` 请求会通过 Vite proxy 自动转发到后端（默认 `http://127.0.0.1:8080`）。

如需指向其他后端地址：

```bash
VITE_DEV_API_TARGET=http://192.168.1.100:8080 npm run dev
```

## 构建

```bash
npm run build
```

产物输出到 `../static/`，由后端 Flask 自动托管。

## 环境变量

见 `.env.example`。所有 `VITE_` 前缀变量会在构建时注入前端代码。

| 变量 | 说明 |
|------|------|
| `VITE_DEV_API_TARGET` | 开发模式下 Vite proxy 转发的后端地址（默认 `http://127.0.0.1:8080`） |
| `VITE_API_BASE` | 生产模式下前端请求的 API 基础地址（留空则使用 `window.location.origin`） |

## 目录结构

```
src/
  App.vue               # 根组件，Tab 导航 + 全局状态
  main.js               # 入口
  styles.css             # Tailwind 入口 + 全局样式
  api/
    client.js            # API 客户端（认证、请求、错误处理）
  stores/
    appStore.js          # 全局响应式状态
  composables/           # 可复用组合函数
  components/
    tabs/                # 各 Tab 页面（容器/创建/镜像/网络/FRP/系统）
    container/           # 容器相关弹窗
    frp/                 # FRP 代理弹窗
    images/              # 镜像详情/拉取弹窗
    networks/            # 网络表单/详情弹窗
    system/              # 系统设置弹窗
    charts/              # 趋势图表
    ui/                  # 通用 UI 组件（卡片、按钮等）
```

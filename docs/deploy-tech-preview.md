# CivilSimulator Tech Preview — 单机部署指南

面向 **本地 / 熟人邀测** 的 v0.1 Tech Preview。目标：按本文档在约 30 分钟内起服。

## 能力边界（先读）

- 单进程 uvicorn；**无** Redis / 多 worker 房间广播  
- **方案 B（v0.3）：** 退出 / 周期快照写入 SQLite；重启后成员可从「我的世界」续玩（可玩优先，非 bit-perfect）  
- Hunyuan3D 生成器为**可选**本地服务；离线时仍可浏览静态资产  
- 生产环境必须设置自定义 `AUTH_SECRET`（`ENV=production`）
- 受控邀测可设 `INVITE_ONLY=true` + `INVITE_CODE=…`（R1-5）
- Redis：`REDIS_URL` **不要指望生效**（v0.4 才接线）

## 端口约定

| 服务 | 默认端口 |
|------|----------|
| FastAPI | `8000` |
| Next.js | `3000` |
| Ollama | `11434` |
| Hunyuan3D（可选） | `8080` |

## 1. 系统依赖

- Python 3.9+  
- Node.js 18+  
- （推荐）[Ollama](https://ollama.com) + 模型：

```bash
ollama pull qwen3.8:27b
ollama pull nomic-embed-text
# 可选备用
ollama pull gpt-oss:20b
```

离线演示可跳过 Ollama，后端设 `LLM_PROVIDER=mock`。

### 资源说明

- **本机 Tech Preview：** 双进程即可；无 GPU 时用 `LLM_PROVIDER=mock`。  
- **完全商业化（多租户公网）的 OpEx / 容量：** 见仓库根目录 [README 中文 · 完全商业化后的资源开销](../README.zh-CN.md) / [English · commercial resource cost](../README.md) — **主成本是大模型推理**，不是本机装模型的磁盘占用。

## 2. 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 邀测生产样例：
#   ENV=production
#   AUTH_SECRET=<长随机串>
#   CORS_ORIGINS=http://你的前端源
#   INVITE_ONLY=true
#   INVITE_CODE=<注册码>
#   MIN_PASSWORD_LENGTH=8
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查：`curl -s http://127.0.0.1:8000/api/seeds | head`

数据目录默认 `backend/data/runtime/`（SQLite、Qdrant 嵌入式库）。

## 3. 前端

```bash
cd frontend
cp .env.example .env.local
# 确认：
#   BACKEND_URL=http://localhost:8000
#   NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
npm install
npm run dev
# 或生产构建：
# npm run build && npm run start
```

打开 http://localhost:3000 → 注册 / 登录 → 文明模拟器。

## 4. 可选：Hunyuan3D

仅在需要文生 3D 时启动；未启动时 Generator 页会标「离线」，不阻塞主玩法。

```bash
./backend/scripts/hunyuan3d/start_server.sh
```

## 5. 可选：Docker Compose 骨架

仓库可按需扩展；当前推荐直接本机双进程（uvicorn + Next）。若使用反向代理，请同时：

1. 把 `CORS_ORIGINS` 设为前端 Origin  
2. 把 WebSocket `/ws/sessions/*` 升级转发到后端 `:8000`  
3. 设置 `ENV=production` + 自定义 `AUTH_SECRET`

最小 compose 示例（可选，按需启用）：

```yaml
# docker-compose.tech-preview.yml — 参考骨架，非强制
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      ENV: production
      AUTH_SECRET: ${AUTH_SECRET}
      INVITE_CODE: ${INVITE_CODE}
      CORS_ORIGINS: http://localhost:3000
      LLM_PROVIDER: mock
    volumes:
      - civsim-data:/app/data/runtime
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      BACKEND_URL: http://backend:8000
      NEXT_PUBLIC_BACKEND_URL: http://localhost:8000
volumes:
  civsim-data:
```

> 正式镜像 Dockerfile 若尚未入库，请仍用第 2–3 节本机流程。

## 6. 冒烟清单

1. 注册用户 A；创建内建文明并 `step` 一次  
2. 用户 B 经邀请链接加入；双方移动不串号  
3. Esc 系统菜单可见「世界随进程结束」提示  
4. Generator：服务离线时有降级文案，不报致命首页错误  
5. `ENV=production` + 默认 `AUTH_SECRET` → 后端拒绝启动  
6. `ENV=production` + `CORS_ORIGINS=*` → 后端拒绝启动  
7. 用户 B 打开邀请页：未加入前不应误报「房间已结束」  

## 相关

- [首发计划](../wiki/v0.1-release-plan.md)  
- [README 快速开始](../README.md)  
- 环境变量模板：`backend/.env.example`、`frontend/.env.example`

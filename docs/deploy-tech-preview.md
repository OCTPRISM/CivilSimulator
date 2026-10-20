# CivilSimulator Tech Preview — 单机部署指南

面向 **本地 / 熟人邀测** 的 v0.1 Tech Preview。目标：按本文档在约 30 分钟内起服。

## 0. 一键部署与启动

源码进仓库；**Hunyuan 源码/权重（约 25GB）和 `frontend/tsconfig.tsbuildinfo` 不进 git**。一键脚本会在缺文件时下载并放到位：

```bash
# 完整部署（Python/Node 依赖 + Hunyuan 源码与权重 + tsbuildinfo）
./scripts/bootstrap.sh

# 启动 FastAPI :8000 + Next :3000（缺 vendor/tsbuildinfo 时仍会补拉）
./scripts/start.sh

# 同时拉起 Hunyuan3D API :8080
./scripts/start.sh --hunyuan
```

只要玩静态资产、不要文生 3D（跳过约 25GB）：

```bash
./scripts/bootstrap.sh --skip-hunyuan
./scripts/start.sh --skip-hunyuan
```

| 资产 | 默认来源 | 覆盖方式 |
|------|----------|----------|
| `third_party/Hunyuan3D-2` | `git clone` Tencent-Hunyuan/Hunyuan3D-2 | 已存在则跳过 |
| `third_party/Hunyuan3D-MLX` | `git clone` ZimengXiong/Hunyuan3D-MLX | `HY3D_SKIP_MLX=1` |
| `third_party/hy3d_models` | Hugging Face `tencent/Hunyuan3D-2` + `Hunyuan3D-2mini` | `HF_ENDPOINT` / `HF_TOKEN` |
| `third_party/hy3d_mlx_weights/paint` | `zimengxiong/hunyuan3d-mlx-paint-large` | `--skip-weights` |
| `frontend/tsconfig.tsbuildinfo` | `CIVSIM_TSBUILDINFO_URL` 或 `npx tsc --incremental` | `--skip-tsbuildinfo` |

gated 权重需先在 Hugging Face 接受许可并 `export HF_TOKEN=hf_...`。国内镜像：`export HF_ENDPOINT=https://hf-mirror.com`。

细节：[Hunyuan3D 本地部署](./hunyuan3d-setup.md)。

## 能力边界（先读）

- 单进程 uvicorn；可选 Redis 房间事件广播（`REDIS_URL`，不可达则自动单机）  
- **方案 B（v0.3）：** 退出 / 周期快照写入 SQLite；重启后成员可从「我的世界」续玩（可玩优先，非 bit-perfect）  
- Hunyuan3D 生成器为**可选**本地服务；离线时仍可浏览静态资产  
- 生产环境必须设置自定义 `AUTH_SECRET`（`ENV=production`）
- 受控邀测可设 `INVITE_ONLY=true` + `INVITE_CODE=…`（R1-5）
- Redis：`REDIS_URL` 可选（v0.4）；未设置或连不上时**仍可起服**，仅为单机房间广播

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
- **完全商业化（多租户公网）的 OpEx / 容量：** 见仓库根目录 [README](../README.md) / [中文 README](../README.zh-CN.md) 中的商业化资源开销小节 — **主成本是大模型推理**，不是本机装模型的磁盘占用。

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
备份 / 恢复演练：[backup-restore.md](./backup-restore.md)。密钥轮换：[ops-secrets.md](./ops-secrets.md)。

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

仅在需要文生 3D 时启动；未启动时 Generator 页会标「离线」，不阻塞主玩法。`bootstrap.sh` / `start.sh` 默认会拉取源码与权重；API 进程仍需显式打开：

```bash
./scripts/start.sh --hunyuan
# 或只起 3D 服务：
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

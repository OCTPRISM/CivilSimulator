<p align="center">
  <img src="docs/brand/stone-axe.svg" alt="CivilSimulator" width="96" height="96" />
</p>

<p align="center">
  <a href="./README.md">English</a> · <strong>中文</strong>
</p>

<h1 align="center">文明模拟器 · CivilSimulator</h1>

<p align="center">
  <em>可玩的文明游戏 —— 也是可动手干预的社会发展仿真沙盘。</em>
</p>

<p align="center">
  选一个文明世界，扮演其中的角色，在 3D 场景里行动，也能和好友同世界开黑。<br />
  或者打开实验平台，对人口、经济、舆论做可控推演。<br />
  本地大模型驱动 · 3D 可漫步 · 同机可多人。
</p>

<p align="center">
  <a href="https://github.com/OCTPRISM/CivilSimulator/releases/tag/v0.2.0"><img alt="release" src="https://img.shields.io/badge/release-v0.2.0-amber?style=flat-square" /></a>
  <img alt="audience" src="https://img.shields.io/badge/audience-本地%20%2F%20熟人邀测-lightgrey?style=flat-square" />
  <img alt="status" src="https://img.shields.io/badge/status-Tech%20Preview-blue?style=flat-square" />
</p>

<p align="center">
  <a href="./docs/deploy-tech-preview.md">30 分钟起服</a>
  ·
  <a href="./CHANGELOG.md">更新日志</a>
  ·
  <a href="./README.md">English</a>
</p>

<!-- Uniform 16:9 crops (960×540) — identical aspect for GitHub rendering -->
<p align="center">
  <img src="docs/brand/readme-heroes/hero-ancient.png" alt="九州·永和" width="270" height="152" />
  &nbsp;
  <img src="docs/brand/readme-heroes/hero-wuxia.png" alt="江湖·风波渡" width="270" height="152" />
  &nbsp;
  <img src="docs/brand/readme-heroes/hero-scifi.png" alt="环带·2387" width="270" height="152" />
</p>
<p align="center">
  <sub>九州 · 江湖 · 环带 — 同一画幅的世界切片</sub>
</p>

---

## 当游戏来玩

文明模拟器首先是一款 **可自由行动的叙事 RPG**，不是聊天演示：

| 玩法 | 你怎么玩 |
|------|----------|
| **选世界 / 创角色** | 内建古代、武侠、科幻等种子，或用规则编辑器自定义文明后开局 |
| **走进 3D 场景** | WASD 移动，靠近 NPC 交谈，用选择支或自由输入推进下一幕 |
| **成长与任务** | 技能、背包与任务线随进程展开；系统菜单开关 TTS / BGM / 场景插画 |
| **开黑同世界** | 复制邀请链接，好友加入同一房间，各自操控自己的角色（互不串号） |
| **改写局势** | 定时注入事件或新角色、跳转到指定 tick，亲手改变战局与社会状态 |

适合：喜欢沉浸探索、沙盒行动、和朋友一起活在同一个世界里的玩家。  
进阶玩家还可以打开 **实验平台**，用数值沙盘做「如果舆情 / 灾变 / 经济冲击不同，社会会怎样」的对照实验。

---

## 当社会发展仿真来跑

首页 **实验平台**（`/labs`）把文明变成 **可复现沙盘**。共同流程：录入背景与事件 → 推演路径 → 导出报告。

| 实验室 | 你在仿真什么 |
|--------|----------------|
| **人口发展** | 天灾、迁移、认知与长期结构变迁对人口曲线的影响 |
| **金融 / 经济** | 宏观走势、城市金融、企业估值与散户路径的情景推演 |
| **舆情发酵** | 议题扩散、情绪极化与舆论场反馈回路 |
| **气象 / 环保** | 气候扰动、区域排放与治理措施效果 |

### 如何干预事态发展

你不是只能旁观曲线——可以注入变量、改写路径：

| 方式 | 场景 | 做法 |
|------|------|------|
| **时间线事件** | 实验平台 | 上传/手写事件（灾变、丑闻、市场冲击、舆论热点…），设定发生步点后重新推演 |
| **对照实验** | 实验平台 | 同一文明、不同事件组合，对比人口 / 舆情 / 金融等结果并导出报告 |
| **冲击与变量** | 金融等实验室 | 施加市场或情景冲击，观察指标响应与路径差异 |
| **世界内注入** | Play | 预约在某一 tick **注入世界事件**或 **新 NPC**，让叙事与社会状态一起转向 |
| **跳时 / 休眠** | Play | 快进到指定 tick；或休眠角色让世界后台继续演化后再「醒来」听取简报 |
| **角色行动** | Play | 对话、技能、任务与自由输入——以第一人称撬动局势与人际关系 |

一句话：**实验室里干预参数，游戏里干预命运**——研究、教学、爽玩都可以。

---

## 你还能做什么

- **本地智能**：默认 Ollama；也可 Mock 离线演示主流程  
- **创造文明**：编辑规则、地点与势力，用自己的设定开局（M4）  
- **氛围层**：场景插画、浏览器朗读、程序化 BGM  
- **可选 3D 生成**：Hunyuan3D 本地管线；离线时仍可浏览静态资产  
- **重启后续玩（方案 B 预览）**：退出 / 周期写快照；可在「我的世界」续玩  

---

## 30 分钟起服

详细步骤见 [Tech Preview 部署指南](./docs/deploy-tech-preview.md)。

```bash
# 后端（:8000）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# 前端（:3000）— 另开终端
cd frontend
cp .env.example .env.local
npm install && npm run dev
```

打开 http://localhost:3000 → 注册 / 登录 → 选 **文明模拟器** 开玩，或进 **实验平台** 做社会仿真。

| 想这样跑 | 怎么做 |
|----------|--------|
| 完整本地 LLM | 安装 [Ollama](https://ollama.com)，拉取 `qwen3.8:27b` 与 `nomic-embed-text` |
| 无 GPU / 先看流程 | 后端 `.env` 设 `LLM_PROVIDER=mock` |
| 生产式起服 | `ENV=production` 且必须自定义 `AUTH_SECRET` |

环境变量见 [`backend/.env.example`](./backend/.env.example)、[`frontend/.env.example`](./frontend/.env.example)。端口：**8000 / 3000**。

### 邀请第二位玩家

1. Play 页点击 **邀请**，复制链接  
2. 对方登录后打开 `/join/{sessionId}` 并创建角色  
3. 双方各自行动；断线只影响自己的角色  

---

## 已知限制（请先读）

本版本是 **Tech Preview**：

| 限制 | 说明 |
|------|------|
| 续玩（方案 B） | 退出 / 周期 / 关进程会写快照；重启后可从「我的世界」续玩（MVP：**可玩**，非 bit-perfect；极旧/损坏快照可能无法恢复） |
| 单机进程 | 多人同世界依赖同一 uvicorn；**Redis / 多 worker 未实现**（目标 v0.4） |
| 非公开正式版 | 适合本机与熟人邀测，不适合无门槛公网开放注册 |
| 生成器可选 | Hunyuan3D 未启动时标「离线」，不阻塞主玩法 |
| 硬件 | 真 LLM 建议桌面机；Mock 可轻量演示 |

下一版规划见 [Release 开发文档](./wiki/v0.1-release-plan.md)。

---

## 版本与路线

| 版本 | 状态 | 一句话 |
|------|------|--------|
| **[v0.1.0-tech-preview](https://github.com/OCTPRISM/CivilSimulator/releases/tag/v0.1.0-tech-preview)** | 已发布 | 可玩 + 鉴权门禁 + 诚实短暂世界 |
| **[v0.2.0](https://github.com/OCTPRISM/CivilSimulator/releases/tag/v0.2.0)** | 已发布 | 我的世界、新手引导、更清晰的错误提示 |
| **v0.3.0** | 开发中 | 重启后续玩（方案 B 快照恢复） |
| **v0.4.0+** | 规划 | 多人运营与生产硬化 → 迈向 v1.0 |

已完成：M0 骨架 · M1 本地 LLM/Qdrant · M2 多人房间 · M3 氛围多模态 · M4 自定义文明。

---

## 技术一览

- **后端** FastAPI + WebSocket（Play / 房间需登录成员校验）  
- **前端** Next.js 14 + React Three Fiber  
- **智能** Ollama（可切换 OpenAI / Mock）+ 可选 Qdrant  

```
CivilSimulator/
├── backend/     # API、世界房间、文明与实验室
├── frontend/    # Play / 创建 / 邀请 / Labs / Generator
├── docs/        # 部署与技术规格
└── wiki/        # 里程碑与 Release 路线
```

---

## 文档与验证

| 文档 | 用途 |
|------|------|
| [部署指南](./docs/deploy-tech-preview.md) | 起服与冒烟 |
| [金融实验室](./wiki/finance-lab.md) | 经济沙盘入口说明 |
| [Release 开发文档](./wiki/v0.1-release-plan.md) | 进度与五版规划 |
| [CHANGELOG](./CHANGELOG.md) | 版本变更 |
| [Wiki 索引](./wiki/README.md) | M1–M4 与更多专题 |
| [技术文档索引](./docs/README.md) | UI / API 规格 |
| [English README](./README.md) | 英文版 |

```bash
cd backend && source .venv/bin/activate
QDRANT_ENABLED=false LLM_PROVIDER=mock pytest tests/ -q
```

---

<p align="center">
  <sub>Tech Preview · 本地优先 · 游戏与仿真仍在演化</sub>
</p>

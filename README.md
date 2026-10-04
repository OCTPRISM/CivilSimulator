<p align="center">
  <img src="docs/brand/stone-axe.svg" alt="CivilSimulator stone axe logo" width="128" height="128" />
</p>

<h1 align="center">Civilization Simulator</h1>

<p align="center">
  <em>一个把“读小说”变成“活在小说里”的虚拟体验引擎。</em><br />
  用户选定一个文明（古代 / 科幻 / 武侠 / 玄幻 / 悬疑…），描述自己想成为谁，<br />
  系统就为其生成一个 Agent 角色，并把他抛入由其它 Agent（NPC/玩家）共同演化的世界。
</p>

## 六层架构

```
┌──────────────────────────────┐
│ Layer 6  Reality Persistence │  事件溯源 / 快照 / 重放
├──────────────────────────────┤
│ Layer 5  Dream UI Runtime    │  Flipbook 翻书式沉浸 UI（Next.js）
├──────────────────────────────┤
│ Layer 4  Narrative Runtime   │  剧情导演：冲突生成、节奏控制、章节切换
├──────────────────────────────┤
│ Layer 3  Agent Society       │  角色 Agent、记忆、关系图、群体行为
├──────────────────────────────┤
│ Layer 2  Civilization Engine │  世界状态、时间推进、规则、派系、资源
├──────────────────────────────┤
│ Layer 1  Foundation Models   │  LLM / Embedding / 多模态抽象
└──────────────────────────────┘
```

## 仓库结构

```
CivilSimulator/
├── backend/        # Python FastAPI，承载 L1/L2/L3/L4/L6
│   ├── app/
│   │   ├── layer1_foundation/   # LLM 抽象 + Mock + OpenAI 适配
│   │   ├── layer2_civilization/ # World / Tick / Faction / Rule
│   │   ├── layer3_agents/       # Agent / Memory / Social
│   │   ├── layer4_narrative/    # Director / Scene / Arc
│   │   ├── layer6_persistence/  # Event store / Snapshot
│   │   ├── api/                 # FastAPI 路由 + WebSocket
│   │   └── seeds/               # 五大文明种子设定
│   └── requirements.txt
├── frontend/       # Next.js 14，Layer 5 Dream UI
│   └── src/app/    # Flipbook 入口 + 场景页
└── README.md
```

## 文档（Wiki）

- [Wiki 索引](./wiki/README.md)
- [金融实验室使用指南](./wiki/finance-lab.md)

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

不配 `OPENAI_API_KEY` 时自动启用 `MockLLM`，可全流程跑通。
要接真实模型：`export OPENAI_API_KEY=sk-...` 或 `export LLM_PROVIDER=openai`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:3000 ，选择一个文明，描述你的角色，开始体验。

## 核心交互流程

```
玩家描述 → L4 生成出场设定 → L3 生成角色 Agent
       → L2 把角色注入世界状态
       → L4 导演下一幕（选定 NPC/事件）
       → L3 多 Agent 在 L1 上推理产生对白/行动
       → L6 写入事件日志
       → L5 以"翻一页书"的方式呈现给玩家
       → 玩家做出选择 → 回到 L4 …
```

## 路线图（MVP → V1）

- [x] M0：六层骨架 + Mock LLM 可端到端跑通
- [ ] M1：接入真实 LLM、向量记忆（Qdrant）
- [ ] M2：多人同世界（WebSocket 房间 + 共享世界状态）
- [ ] M3：多模态（场景插画 / TTS 旁白 / BGM）
- [ ] M4：玩家创造文明（自定义 Seed + 规则编辑器）
```


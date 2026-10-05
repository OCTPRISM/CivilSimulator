<p align="center">
  <img src="docs/brand/stone-axe.svg" alt="CivilSimulator stone axe logo" width="128" height="128" />
</p>

<h1 align="center">Civilization Simulator</h1>

<p align="center">
  <em>一个把“读小说”变成“活在小说里”的虚拟体验引擎。</em><br />
  用户选定一个文明（古代 / 科幻 / 武侠 / 玄幻 / 悬疑…），描述自己想成为谁，<br />
  系统就为其生成一个 Agent 角色，并把他抛入由其它 Agent（NPC/玩家）共同演化的世界。
</p>

<p align="center">
  <strong>Sole developer:</strong> Zhongjiang Yao
</p>

## 六层架构

```
┌──────────────────────────────┐
│ Layer 6  Reality Persistence │  事件溯源 / 快照 / 重放 / 用户房间成员
├──────────────────────────────┤
│ Layer 5  Dream UI Runtime    │  3D 探索 + HUD / 邀请加入（Next.js）
├──────────────────────────────┤
│ Layer 4  Narrative Runtime   │  剧情导演：冲突生成、节奏控制、章节切换
├──────────────────────────────┤
│ Layer 3  Agent Society       │  角色 Agent、向量记忆、关系、群体行为
├──────────────────────────────┤
│ Layer 2  Civilization Engine │  世界状态、时间推进、规则、金融沙盘
├──────────────────────────────┤
│ Layer 1  Foundation Models   │  Ollama LLM / Embedding / Qdrant
└──────────────────────────────┘
```

## 仓库结构

```
CivilSimulator/
├── backend/                 # Python FastAPI（L1–L4 / L6）
│   ├── app/
│   │   ├── layer1_foundation/   # Ollama / OpenAI / Mock + Qdrant
│   │   ├── layer2_civilization/ # World / Finance / Live simulation
│   │   ├── layer3_agents/       # Agent / MemoryStore / Society
│   │   ├── layer4_narrative/    # Director / Scene / Wake briefing
│   │   ├── layer6_persistence/  # Event store / Users / Members
│   │   ├── labs/                # 金融等实验室
│   │   ├── session.py           # 世界房间（多人 Session）
│   │   ├── main.py              # HTTP + WebSocket
│   │   └── seeds/               # 文明种子
│   ├── tests/
│   └── requirements.txt
├── frontend/                # Next.js 14（Layer 5）
│   └── src/app/
│       ├── create/[seedKey]     # 开局选角
│       ├── play/[sid]           # 叙事 / 3D 游玩
│       ├── join/[sid]           # M2 邀请加入
│       └── labs/                # 实验室
├── docs/                    # 技术规格
├── wiki/                    # 产品 / 里程碑 Wiki
└── README.md
```

## 文档（Wiki）

- [Wiki 索引](./wiki/README.md)
- [M1：本地 LLM 与 Qdrant 向量记忆](./wiki/m1-llm-qdrant.md)
- [M2：多人同世界](./wiki/m2-multiplayer.md)
- [金融实验室使用指南](./wiki/finance-lab.md)
- [技术文档索引](./docs/README.md)

## 快速开始

### 0. 前置：Ollama

```bash
ollama pull qwen3.8:27b
# 或备用：
ollama pull gpt-oss:20b
# 向量记忆：
ollama pull nomic-embed-text
```

### 1. 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

默认 `LLM_PROVIDER=ollama`。可选 `backend/.env`：

```bash
LLM_PROVIDER=ollama
OLLAMA_TEXT_MODEL=qwen3.8:27b
OLLAMA_TEXT_FALLBACKS=gpt-oss:20b,qwen3.6:35b-a3b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
QDRANT_ENABLED=true
QDRANT_PATH=data/runtime/qdrant
# 独立 Qdrant 服务时：
# QDRANT_URL=http://localhost:6333
```

云端 OpenAI：`LLM_PROVIDER=openai` + `OPENAI_API_KEY`。离线：`LLM_PROVIDER=mock`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:3000 ：登录 → 选文明 → 进入世界。

### 3. 多人同世界（M2）

1. 房主在 Play 页点击 **邀请**，复制链接  
2. 另一账号打开 `/join/{sessionId}`，描述角色后加入  
3. 双方各自控制自己的 Agent；WebSocket 同步世界状态  

详见 [wiki/m2-multiplayer.md](./wiki/m2-multiplayer.md)。

## 核心交互流程

```
玩家描述 / 选角 → L4 生成出场设定 → L3 生成角色 Agent
       → L2 注入世界；记忆写入 Qdrant
       → L4 导演下一幕（NPC / 事件 / 同房玩家）
       → L3 多 Agent 在 L1（Ollama）上推理
       → L6 写入事件日志
       → L5 3D + HUD / 对白呈现
       → 玩家行动（HTTP 或 WebSocket）→ 回到 L4 …
```

## 路线图（MVP → V1）

- [x] **M0**：六层骨架 + Mock LLM 端到端可跑通  
- [x] **M1**：真实 LLM（本地 Ollama：qwen3.8 / gpt-oss）+ Qdrant 向量记忆  
- [x] **M2**：多人同世界（WebSocket 房间、玩家身份绑定、邀请加入；单进程共享状态）  
- [x] **M3**：多模态（场景插画 / TTS 旁白 / BGM）— Phase A：Pillow + 浏览器 SpeechSynthesis + WebAudio  
- [x] **M4**：玩家创造文明（自定义 Seed + 规则编辑器深化）  

## 测试

```bash
cd backend && source .venv/bin/activate
QDRANT_ENABLED=false LLM_PROVIDER=mock pytest tests/ -q
```

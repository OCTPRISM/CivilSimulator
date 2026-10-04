# 叙事游戏会话 — 前端 UI 与 API 技术规格

> **文档版本**：2026-08-30  
> **适用范围**：`/play/[sid]` 叙事模拟器及关联会话 API  
> **读者**：玩法前端/后端、QA  
> **关联文档**：[3D 世界与人物](./3d-world-and-characters.md)、[文档索引](./README.md)

---

## 目录

1. [产品边界](#1-产品边界)
2. [页面布局与组件树](#2-页面布局与组件树)
3. [前端状态与生命周期](#3-前端状态与生命周期)
4. [用户操作流程](#4-用户操作流程)
5. [组件规格](#5-组件规格)
6. [会话 API 规格](#6-会话-api-规格)
7. [WebSocket](#7-websocket)
8. [Session 对象结构](#8-session-对象结构)
9. [已知限制](#9-已知限制)
10. [源码索引](#10-源码索引)

---

## 1. 产品边界

### 1.1 入口

```
/ → /create/[seedKey] → createSession → /play/[sid]
```

- **创建会话**需登录（`POST /api/sessions`）
- **进入 Play** 无前端 auth gate，但需有效 `sid`
- **金融实验室**：Play 页 **不挂载** FinancePanel（实验平台 `/labs/finance` 专用）

### 1.2 与 3D 的关系

Play 页是唯一生产环境挂载 `World3D` 的页面。详见 [3D 文档 §5](./3d-world-and-characters.md#5-world3d-渲染管线)。

---

## 2. 页面布局与组件树

**文件**：`frontend/src/app/play/[sid]/page.tsx`

### 2.1 栅格布局

```
┌─────────────────────────────────────────────────────────────┐
│ Header: 世界名 | 玩家信息 | 离线/苏醒 | TTS | 音效 | 关系 | 退出 │
├──────────────────────────────┬──────────────────────────────┤
│ 左栏 (flex-col)               │ 右栏 (aside)                  │
│ ┌──────────────────────────┐ │ ┌──────────────────────────┐ │
│ │ World3D (h=520)          │ │ │ WorldAtlas (h=520)       │ │
│ └──────────────────────────┘ │ └──────────────────────────┘ │
│ ChoicePanel + 输入框          │ 近事 Recent Events (最近6页) │
│ SkillPanel                   │                               │
│ NpcPanel → NpcChat           │                               │
│ TaskPanel                    │                               │
│ InjectPanel                  │                               │
│ StatBars                     │                               │
└──────────────────────────────┴──────────────────────────────┘
WorldDrawer (侧滑) → CivilizationDashboard
WakeBriefingModal (苏醒简报)
```

- 大屏：`lg:grid-cols-[minmax(0,1fr)_400px]`
- World3D 与 WorldAtlas **同高 520px**

### 2.2 组件树

```
PlayPage
├── WakeBriefingModal
├── World3D                    ← 见 3D 文档
├── ChoicePanel                ← 故事选项 + 自由输入
├── SkillPanel                 ← useSkill
├── NpcPanel
│   └── NpcChat                ← talkToNpc
├── TaskPanel                  ← createSelfTask, completeTask
├── InjectPanel                ← injectEvent, injectCharacter, skipToTick
├── StatBars                   ← WorldStats 五维条
├── WorldAtlas                 ← 2D 翻页地图册（非 3D）
└── WorldDrawer
    └── CivilizationDashboard
```

---

## 3. 前端状态与生命周期

### 3.1 状态

| 状态 | 类型 | 说明 |
|------|------|------|
| `session` | `Session \| null` | 完整会话 |
| `pages` | `Page[]` | 叙事页历史 |
| `stats` | `WorldStats?` | 五维统计 |
| `tensionCurve` | `number[]` | 最近 32 个 tension |
| `input` | string | 自由文本输入 |
| `loading` | boolean | step/skill 进行中 |
| `drawerOpen` | boolean | 关系抽屉 |
| `ttsOn` / `sfxOn` | boolean | 朗读 / 翻页音效 |
| `cameraMode` | `"third"\|"first"` | 3D 相机 |
| `briefing` | `WakeBriefing?` | 苏醒模态 |

### 3.2 缓存

| 键 | 内容 |
|----|------|
| `sessionStorage.sess_{sid}` | 完整 Session JSON（create/play 时写入，退出不清除策略见 onExit） |

### 3.3 轮询与 Presence

| 机制 | 间隔/触发 | API |
|------|----------|-----|
| 会话轮询 | **4s** | `GET /api/sessions/{sid}` |
| Heartbeat | **12s**（玩家 active 时） | `POST .../heartbeat` |
| Tab 隐藏 60s | 自动 sleep | `POST .../sleep` reason=`tab_hidden` |
| Tab 重新可见 | 若 dormant/proxy → wake | `POST .../wake` |
| pagehide | sendBeacon sleep | `POST .../sleep` reason=`unload` |

**presence 状态**：

| 值 | UI |
|----|-----|
| `active` | 正常操作 |
| `dormant` | 「苏醒」按钮；World3D `dormant=true` |
| `proxy` | 「收回控制」按钮；离线代理模式 |

---

## 4. 用户操作流程

### 4.1 叙事推进

```
输入文本或点击 ChoicePanel 选项
  → stepSession(sid, input)
  → applyStepResult(page, stats, session)
  → pages 追加 / 更新
  → TTS 朗读最新 narration（若 ttsOn）
  → 翻页音效（若 sfxOn）
```

**空输入**：trim 后为空字符串则不提交。

**Walk 提示**（无输入时）：`WALK_PROMPTS` 随机选一句作为 step input。

### 4.2 技能

```
SkillPanel.onUse(skill_id)
  → useSkill(sid, skill_id)
  → 同 applyStepResult
```

离线时 SkillPanel 不渲染。

### 4.3 NPC 对话

```
NpcChat → talkToNpc(sid, npc_id, text)
  → 显示 reply（不推进 page）
```

### 4.4 任务 / 注入

- `TaskPanel`：自建任务、完成任务
- `InjectPanel`：定时注入事件/角色、skip-to-tick

### 4.5 退出

```
onExit → sleepSession → router.push("/")
```

---

## 5. 组件规格

### 5.1 ChoicePanel

- 数据源：`pages[-1].choices`
- `normalizeChoices()` 处理后端 choices 格式
- 支持 `action` 字符串直接提交

### 5.2 WorldAtlas

- **2D 翻页 UI**，展示 stats、势力、历史摘要
- **不是** 3D 地图；3D 在左侧 World3D

### 5.3 NpcPanel

- 过滤当前 `sceneLocId` 的 NPC
- `genre` 传给 figure badge 解析
- 展开 NpcChat 对话

### 5.4 StatBars

五维：`politics`, `economy`, `livelihood`, `military`, `environment`  
含 `stats.summary` 文字说明。

### 5.5 WakeBriefingModal

`wakeSession` 返回 `briefing` 时展示：

- `narrative`, `shards[]`, `npc_shifts[]`, `world_stats_hint`
- `offline_mode`: sleep / proxy

---

## 6. 会话 API 规格

前缀：`/api/sessions/{sid}`  
**多数端点无认证**（持有 sid 即可）。

### 6.1 核心玩法

#### GET `/api/sessions/{sid}`

**Response**：`{ session: Session }`

Play 页初始加载 + 4s 轮询。

#### POST `/api/sessions`（创建）

**Auth**：必须  
**Body**：

```json
{
  "seed_key": "wuxia",
  "description": "",
  "category_key": "jianghu",
  "variant_key": "wanderer",
  "skin": "fair"
}
```

**Response**：`{ session, page }`

#### POST `/api/sessions/{sid}/step`

**Body**：`{ "input": string | null, "player_id"?: string }`

**Response**：`{ page, stats?, session? }`

#### POST `/api/sessions/{sid}/use-skill`

**Body**：`{ "skill_id": string, "player_id"?: string }`

**Response**：同 step。

### 6.2 Presence

| 方法 | 路径 | Body | Response 要点 |
|------|------|------|--------------|
| POST | `/heartbeat` | `{ player_id? }` | `{ player_id, presence, tick }` |
| POST | `/sleep` | `{ player_id?, reason? }` | `{ presence, offline_mode, session }` |
| POST | `/wake` | `{ player_id? }` | `{ already_awake, briefing?, session }` |

### 6.3 NPC

#### POST `/api/sessions/{sid}/talk`

**Body**：`{ npc_id, text, player_id? }`  
**Response**：`{ npc_id, npc_name, reply }`

#### GET `/api/sessions/{sid}/npcs`

**Query**：`location_id?`  
**Response**：`{ npcs: [...] }` — 含 schedule、economy、presence 等

### 6.4 注入与时间

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/injections` | 计划注入列表 |
| POST | `/inject/event` | `{ tick, summary, importance?, location_id? }` |
| POST | `/inject/character` | 新 NPC 注入 |
| POST | `/skip-to-tick` | `{ target_tick }` |

### 6.5 任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks` | `?player_id=` |
| POST | `/tasks/self` | 自建任务 |
| POST | `/tasks/{task_id}/complete` | 完成领奖 |

### 6.6 金融（Legacy API，Play UI 未挂载）

以下 API **存在**但 Play 页 **无 UI**；仅供 session 绑定实验或外部调用：

| 方法 | 路径 |
|------|------|
| GET | `/finance` |
| POST | `/finance/shock` |
| POST | `/finance/advance` |
| GET | `/finance/lab` |
| POST | `/finance/lab/{global\|city\|corporate}/forecast` |
| POST | `/finance/lab/{global\|city\|corporate}/event` |
| POST | `/finance/lab/retail/run` |

实验平台等价路径见 [金融文档 §11](./finance-lab-ui-api.md#11-后端-api-完整规格)。

### 6.7 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/clock` | `{ tick, hour, day, era, label }` |
| GET | `/replay?to_tick=` | 回放 snapshot |
| POST | `/join` | 多人加入 |

---

## 7. WebSocket

```
WS /ws/sessions/{sid}
```

**服务端 → 客户端**（推送类型）：

- `snapshot` — 初始 `{ type, session }`
- `finance_tick`, `finance_shock`, `wake`, `npc_dialogue`, `simulation_tick`, `simulation_error`, …

**客户端 → 服务端**：

```json
{ "type": "input", "input": "...", "player_id"?: "..." }
{ "type": "heartbeat", "player_id"?: "..." }
{ "type": "sleep", "player_id"?, "reason"?: "..." }
{ "type": "wake", "player_id"?: "..." }
{ "type": "ping" }  → { "type": "pong" }
```

**Play 页当前实现**：以 **HTTP 轮询** 为主，**未**在 `play/[sid]/page.tsx` 中连接 WebSocket。

断开连接时服务端可将玩家 auto-sleep（reason=`disconnect`）。

---

## 8. Session 对象结构

定义：`frontend/src/lib/api.ts` → `Session`

### 8.1 顶层字段

| 字段 | 说明 |
|------|------|
| `id` | session id (= sid) |
| `world` | 世界设定（genre, locations, clock, factions, …） |
| `agents` | 玩家 + NPC |
| `player_id` | 当前玩家 agent id |
| `pages` | 叙事页数组 |
| `stats` | WorldStats |
| `tension_curve` | number[] |
| `finance` | FinanceSnapshot?（市场引擎） |
| `finance_lab` | desk snapshot? |
| `simulation` | LLM 连续模拟状态 |
| `injections` | 计划注入 |
| `tasks` | 任务列表 |
| `seed_key` | 文明 seed |

### 8.2 Agent 关键字段（3D 相关）

| 字段 | 用途 |
|------|------|
| `location_id` | 叙事位置 |
| `world_x`, `world_z` | 3D 归一化坐标 |
| `appearance.figure` | 人物 preset id |
| `appearance.skin` | RoleSkinId |
| `presence` | active / dormant / proxy |
| `skills[]` | SkillPanel |
| `inventory`, `equipment`, `savings` | 经济/装备 |

### 8.3 Page 结构

```typescript
{
  page_no: number;
  chapter: string;
  scene: { location_id, location_name, summary, present_agent_ids };
  beats: { kind: "narration"|"speech"|"action"|"system", speaker, content }[];
  choices: { label, hint, action }[];
  tension?: number;
}
```

---

## 9. 已知限制

| 项 | 说明 |
|----|------|
| Play 无 WebSocket 客户端 | 依赖 4s HTTP 轮询 |
| 会话 API 无 auth | sid 泄露可被第三方操作 |
| 金融 UI 已剥离 | session finance API 仍可用 |
| military 等 seed 无 3D map | 见 [3D 文档 §12](./3d-world-and-characters.md#12-已知限制与缺口) |
| TTS | `GET /api/tts/info` → 浏览器 Speech Synthesis |

---

## 10. 源码索引

| 文件 | 职责 |
|------|------|
| `frontend/src/app/play/[sid]/page.tsx` | Play 主页面 |
| `frontend/src/app/create/[seedKey]/page.tsx` | 角色创建 |
| `frontend/src/components/ChoicePanel.tsx` | 选项 |
| `frontend/src/components/NpcPanel.tsx` | NPC 列表/聊天 |
| `frontend/src/components/TaskPanel.tsx` | 任务 |
| `frontend/src/components/InjectPanel.tsx` | 注入 |
| `frontend/src/components/WorldAtlas.tsx` | 2D 图册 |
| `frontend/src/components/WorldDrawer.tsx` | 侧滑 dashboard |
| `frontend/src/lib/api.ts` | API 客户端 |
| `frontend/src/lib/audio.ts` | TTS + SFX |
| `backend/app/main.py` | 会话路由 |

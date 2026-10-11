# CivilSimulator 架构解构与演进开发规格

> **文档版本：** 1.0  
> **基线版本：** `v0.5.0`（commit `d677885`）  
> **目标范围：** `v0.5.1` → `v1.0.0`  
> **用途：** 指导架构重构、算法优化、接口演进、用户体验改进、测试与发布验收  
> **相关文档：** [Release 开发文档](../wiki/v0.1-release-plan.md) · [全站 UI / API 规格](./ui-design-and-api-complete.md) · [Play 专题](./play-session-ui-api.md) · [金融实验室](./finance-lab-ui-api.md)

---

## 0. 阅读约定

本文把内容分为两类：

- **当前实现**：`v0.5.0` 已存在且可从代码验证。
- **目标设计**：建议在后续版本新增的契约；未实现前不得作为对外能力宣传。

本文重点覆盖核心闭环。现有 70+ REST 路由与所有实验室字段的完整清单继续以
[全站 UI / API 规格](./ui-design-and-api-complete.md) 为准；本文只重复会被改造或会影响架构边界的接口。

### 0.1 核心结论

CivilSimulator 已具备完整的邀测产品表面：

1. 本地 / OpenAI / Mock LLM；
2. Agent、记忆、反思、任务、技能与多人房间；
3. 确定性金融 ABM 和多类实验室；
4. 3D Play、叙事页、续档、WebSocket、Redis 事件中继；
5. 账户、备份、日志、指标、CI 和配额。

但从“可演示产品”进入“可信多智能体文明系统”，仍缺四个闭环：

1. **时间闭环**：世界、金融、日程、叙事不是同一个时间事务。
2. **Agent 闭环**：计划和信念会写入记忆，但未被稳定地读取并驱动后续行动。
3. **状态闭环**：运行态以单进程内存为权威，Redis 仅中继消息，多 worker 可能双写。
4. **产品闭环**：Play、Labs、Creator 功能丰富但互相割裂，关键能力仍停留在 API 或开发面板。

因此下一阶段不应继续横向增加实验室或生成能力，而应先统一：

```text
用户意图
  → TickCommand
  → 感知 / 计划 / 行动候选
  → WorldEffect 校验
  → 单写者事务提交
  → EventEnvelope
  → Agent 反思与记忆
  → WebSocket / UI 可解释反馈
  → 指标与评测
```

### 0.2 实现进度（strangler）

| 管线阶段 | 状态 | 代码入口 |
|----------|------|----------|
| TickCommand | ✅ | `backend/app/runtime/commands.py` |
| Perceive / Plan | ✅（启发式，无 LLM planner） | `runtime/perceive.py`, `runtime/plan.py` |
| Act（叙事） | ✅（封装原 `director.direct_page`） | `session._narrative_step_impl` |
| WorldEffect 校验 | ✅ | `runtime/effects.py` |
| 单写者（进程内 lease + `sess.lock`） | ✅ | `runtime/leases.py`, `TickCoordinator` |
| EventEnvelope | ✅（嵌套 `_envelope` 写入现有 EventStore） | `runtime/events.py` |
| Reflect / 记忆 | ✅（轻量同步反思记忆） | `runtime/reflect.py` |
| WS / UI 可解释字段 | ✅（step 响应 + fan-out 带 revision/plan） | `main.api_step`, `_fanout` |
| 指标 | ✅ | `runtime.tick.*` via `bump_metric` |
| 统一 WORLD_HOUR↔金融时钟 | ✅ | `runtime/world_hour.py`；后台 / finance.advance / skip_to_tick |
| Memory checkpoint MVP | ✅（快照 v2） | `MemoryStore.build_checkpoint`；`session_persist` |
| Redis lease / 多 worker 权威 | ⏳ 未做 | — |
| LLM Plan→Act 闭环 | ⏳ 未做 | — |

`session.step` 已默认走 `TickCoordinator`；Play 旧客户端不传 `command_id` 仍可用。
WORLD_HOUR 与 `MarketState.tick` 同事务推进；独立金融墙钟循环已移除。

---

## 1. 整体分层

### 1.1 当前代码映射

| 层级 | 当前代码 | 当前职责 | 主要问题 |
|------|----------|----------|----------|
| L1 基础层 | `layer1_foundation/` | LLM、Embedding、Qdrant、限流、配额、场景图 | 配额/限流进程内；调用成本与质量不可统一评测 |
| L2 文明层 | `layer2_civilization/` | 世界、时钟、金融、制度、统计、注入、连续模拟 | 金融 tick 与世界 tick 分离；Play 与 Labs 模型未完全统一 |
| L3 Agent 层 | `layer3_agents/` | Agent、社会关系、记忆、反思、任务、技能 | Plan/Belief 未形成稳定行动约束；恢复后记忆连续性不足 |
| L4 叙事层 | `layer4_narrative/` | 场景、Page、Director、Choice、张力、醒来简报 | 叙事结果主要是文本，缺少结构化状态效果 |
| 运行时 | `runtime/`、`session.py`、`session_persist.py`、`room_bus.py` | TickCoordinator；统一 WORLD_HOUR；记忆 checkpoint v2 | 权威仍在单 worker；lease 未上 Redis |
| L5 产品层 | `frontend/` | Next.js、3D、Play、Labs、Creator、Generator | 产品旅程割裂；移动端、错误恢复、分析与自动化薄弱 |
| L6 持久层 | `layer6_persistence/` | SQLite 用户、成员、事件、快照、自定义文明 | 事件与快照缺统一 envelope/revision；非完整事件重放 |

### 1.2 目标分层

```text
┌──────────────────────────────────────────────────────────────────┐
│ Product Surfaces                                                 │
│ Play · Labs · Creator · Generator · Ops                          │
├──────────────────────────────────────────────────────────────────┤
│ Application Contracts                                            │
│ REST · WebSocket · Error Envelope · Idempotency · Telemetry       │
├──────────────────────────────────────────────────────────────────┤
│ Session Runtime                                                   │
│ Command → Lease → Snapshot → Effects → Commit → Publish           │
├──────────────────────────────────────────────────────────────────┤
│ Agent & Narrative                                                 │
│ Perceive → Plan → Act → Reflect · Director · Tasks                │
├──────────────────────────────────────────────────────────────────┤
│ Civilization Model                                               │
│ World Clock · Places · Factions · Institutions · Finance ABM      │
├──────────────────────────────────────────────────────────────────┤
│ Foundation & Data                                                 │
│ LLM · Embedding · Qdrant · Redis · SQL · Object/Asset Storage     │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 全局不变量

后续实现必须满足：

1. 每个 Session 同一时刻只有一个合法写入者。
2. 每次提交只增加一次 `revision`。
3. `world_tick` 只能单调递增。
4. LLM 不直接修改世界，只产生候选意图或 `WorldEffect`。
5. 所有状态变化先持久化，再广播给客户端。
6. 相同 `command_id` / `Idempotency-Key` 重试不得产生重复状态变化。
7. 重放事件不得重新调用 LLM。
8. 活跃人类玩家不得被自治 Agent 强制移动、改目标或代替作重大决定。
9. 所有错误都带稳定 `code` 和 `request_id`。
10. 所有用户可感知能力必须有正式 UI、文档和自动化验收；否则标为内部能力。

---

## 2. L1 基础层：模型、记忆、配额与可观测性

## 2.1 LLM 抽象

### 当前实现

核心接口位于 `backend/app/layer1_foundation/base.py`：

```python
Message(role: str, content: str)
LLMResponse(content: str, model: str, raw: dict | None)
LLM.chat(messages, temperature, max_tokens) -> LLMResponse
```

Provider：

- `OllamaLLM`
- `OpenAILLM`
- `MockLLM`
- `QuotaAwareLLM` 装饰器

### 缺口

1. 没有统一记录 prompt 版本、token、耗时、重试与结果有效性。
2. 连续世界模拟仅允许 Ollama，Mock CI 无法覆盖真实状态推进路径。
3. LLM JSON 错误通常影响整个 tick，缺少逐 Agent 降级。
4. 没有 recorded response/replay 模式。

### 目标调用结果

```python
@dataclass(frozen=True)
class LlmCallResult:
    call_id: str
    provider: str
    model: str
    prompt_version: str
    content: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float
    retry_count: int
    finish_reason: str | None
    schema_valid: bool
    error_code: str | None
```

### 调用算法

```text
1. 根据 operation 选择模型策略。
2. 申请 quota reservation。
3. 记录 llm.request telemetry。
4. 调用 provider；仅对网络/限流错误指数退避。
5. 对结构化任务执行 schema 校验。
6. 校验失败时允许一次 repair prompt；禁止无限重试。
7. 结算实际 token；记录结果与延迟。
8. 返回 LlmCallResult，不在 Provider 内修改业务状态。
```

建议模型策略：

| 操作 | 策略 |
|------|------|
| NPC 近景对话 | 中等模型，低延迟 |
| 世界小时推进 | 强结构化模型；必须 schema 校验 |
| 远处 NPC | 规则/小模型批处理 |
| 报告叙事 enrich | 可降级；数值必须来自确定性内核 |
| 反思 | 异步低优先级；失败不回滚行动 |

## 2.2 当前记忆算法

`MemoryItem` 当前字段：

```text
id: str
ts: float
actor_id: str
kind: observation | dialogue | action | reflection | plan | belief
content: str
importance: float = 0.5
embedding: list[float] | null
```

`MemoryStore.recall(actor_id, query, k_relevant=6, m_recent=4, scope)`：

```text
1. 为尚未嵌入的 item 批量生成 embedding。
2. scope=self 时只取 actor；scope=world 时取全局。
3. 取最后 m_recent 条近期记忆。
4. 语义相关度：
   score = 0.7 × cosine_similarity
         + 0.2 × importance
         + 0.1 × recency
   recency = 0.5 ^ (age_hours / 6)
5. 语义 top-k 与近期集合并。
6. 按 id 去重，最后按 ts 排序。
```

### 当前问题

- ~~Scheme B 快照不包含 `MemoryStore`~~ → **v0.5.1 MVP**：快照 v2 含 memory checkpoint（recent K ∪ 高重要度 ∪ plan/belief）；
- 重启后本地 recent buffer 可从 checkpoint hydrate；embeddings 仍异步补齐；
- Qdrant 存在时可能找回语义记忆，但不能保证完整顺序与近期上下文；
- Plan/Belief 只是普通记忆种类，没有强制进入后续计划。

## 2.3 目标 MemoryItemV2

```json
{
  "id": "mem_uuid",
  "actor_id": "agent_x",
  "kind": "observation",
  "content": "看见城门关闭",
  "importance": 0.72,
  "created_at_ms": 1791734400000,
  "world_tick": 31,
  "revision": 84,
  "source_event_id": "evt_uuid",
  "visibility": "private",
  "tags": ["gate", "security"],
  "embedding": {
    "status": "ready",
    "model": "nomic-embed-text",
    "dimension": 768
  }
}
```

约束：

- `importance ∈ [0,1]`；
- `source_event_id` 指向已提交事件；
- 默认不在 SQLite 快照内保存向量，只保存模型和维度；
- `visibility`：`private | local | faction | public`；
- 内容长度必须有上限，建议 2,000 字符；
- 敏感信息不得写入全局/public memory。

## 2.4 记忆 checkpoint

快照 v2 增加：

```json
{
  "memory": {
    "schema_version": 1,
    "checkpoint_id": "memcp_uuid",
    "through_sequence": 1824,
    "items": [],
    "content_sha256": "..."
  }
}
```

写入算法：

```text
1. 在 session lock 内读取已提交 revision 和 sequence。
2. 每个 Agent 保留最近 K 条 + 高重要度记忆：
   keep = recent(K=100) ∪ importance>=0.8 ∪ open plan/belief
3. 以 (revision, created_at_ms, id) 稳定排序。
4. canonical JSON 后计算 SHA-256。
5. 在同一 SQL 事务写 checkpoint，并更新 session_heads.checkpoint_id。
6. SQL 提交后异步补写 Qdrant。
7. 每 Session 保留最近 3 个有效 checkpoint。
```

恢复算法：

```text
1. 从新到旧选择 schema 可识别且 checksum 正确的 checkpoint。
2. hydrate 世界、Agent、任务、市场和记忆。
3. 重放 through_sequence 之后的事件，不调用 LLM。
4. 校验 state.revision == session_head.revision。
5. 重建本地 memory index。
6. 缺失 embedding 进入异步队列。
7. Qdrant 不可达时降级为 local cosine，不得导致 Session 恢复失败。
```

## 2.5 共享配额

### 当前字段

```text
llm_quota_enabled: bool = true
llm_daily_quota_per_user: int = 200
llm_daily_quota_per_session: int = 800
```

当前 key：`(UTC day, kind, subject)`，只在进程内计数。

### 目标请求

```python
@dataclass(frozen=True)
class QuotaRequest:
    request_id: str
    day_utc: str
    user_id: str | None
    session_id: str | None
    operation: str
    units: int
    estimated_tokens: int = 0
```

Redis key：

```text
civsim:quota:{day}:user:{user_id}
civsim:quota:{day}:session:{session_id}
civsim:quota:{day}:request:{request_id}
```

Lua 原子算法：

```text
1. request key 已存在 → 返回原决策。
2. 读取 user/session 所有维度。
3. 任一 used + units > limit → 全部拒绝，不部分扣费。
4. 全部通过 → 同时 INCR。
5. TTL = 当日 UTC 结束 + 2 小时。
6. 保存 request 决策，确保重试幂等。
```

生产规则：

- 单 worker 开发可继续使用内存实现；
- 多 worker 且 quota 开启时 Redis 不可用 → `503 QUOTA_BACKEND_UNAVAILABLE`；
- 后台世界 tick 也必须绑定 owner user/session；
- v1.0 前“调用次数”是限制单位，token 只做遥测；计费另立设计。

## 2.6 可观测性

目标 telemetry envelope：

```json
{
  "schema_version": 1,
  "telemetry_id": "tel_uuid",
  "name": "tick.completed",
  "timestamp_ms": 1791734400130,
  "service": "backend",
  "service_version": "0.7.0",
  "environment": "production",
  "request_id": "req_x",
  "correlation_id": "corr_x",
  "session_hash": "hmac...",
  "user_hash": "hmac...",
  "attributes": {
    "tick_kind": "world_hour",
    "world_tick": 31,
    "revision": 85,
    "lease_fence": 42,
    "effect_count": 17,
    "model": "qwen..."
  },
  "measurements": {
    "duration_ms": 8420,
    "llm_ms": 7910,
    "lock_wait_ms": 4,
    "prompt_tokens": 2800,
    "completion_tokens": 730
  },
  "error": null
}
```

禁止采集：

- token、密码、邮箱原文；
- 用户名、Session ID 原文；
- 未脱敏 prompt、对话和记忆正文。

必须指标：

```text
command.received / command.deduplicated
lease.acquired / lease.contended / lease.lost
tick.started / tick.completed / tick.failed
effect.rejected
llm.request / quota.rejected
checkpoint.written
restore.completed / restore.failed
ws.connected / ws.reconnect_exhausted / ws.queue_drop
lab.exported / lab.run_completed / lab.proposal_applied
```

---

## 3. L2 文明层：世界、时间、市场与制度

## 3.1 当前 World 契约

```python
Location:
  id: str
  name: str
  description: str
  tags: list[str]

Faction:
  id: str
  name: str
  ideology: str
  relations: dict[str, float]

WorldClock:
  era: str
  tick: int
  start_hour: int = 6
  # 1 tick = 1 world hour

World:
  id: str
  name: str
  genre: str
  premise: str
  rules: list[str]
  clock: WorldClock
  locations: dict[str, Location]
  factions: dict[str, Faction]
  facts: list[str]
  agents: list[str]
```

### 当前时间问题（已修复，v0.5.1）

~~后台双时钟：`finance_tick_seconds=3` 与 `live_simulation_tick_seconds=15` 分叉。~~

现态：

- 仅 `TickKind.WORLD_HOUR` / `advance_world_hours` 推进时间；
- 每小时顺序：injections → schedules → `MarketState.advance` → `WorldClock.advance(1)`；
- 后台按 `live_simulation_tick_seconds` 调用 WORLD_HOUR，再可选跑 LLM act（不拥有时钟）；
- `finance/advance` 与 `skip_to_tick` 走同一路径；漂移会话 `align_finance_to_world` 愈合。

不变量：`world.clock.tick == finance.tick`（对齐后持续保持）。

## 3.2 统一时间模型

只允许 `TickCoordinator` 推进世界时间。

```python
class TickKind(str, Enum):
    WORLD_HOUR = "world_hour"
    NARRATIVE = "narrative"
    DIALOGUE = "dialogue"
    PRESENCE = "presence"
    INJECTION = "injection"
    LAB_IMPORT = "lab_import"
    RESTORE = "restore"
```

规则：

| TickKind | `advance_hours` | 是否运行市场 | 是否运行日程 | 是否运行 Agent |
|----------|-----------------|--------------|--------------|----------------|
| `world_hour` | 1 | 是 | 是 | 是 |
| `narrative` | 0（默认） | 否 | 否 | 只解释玩家行动 |
| `dialogue` | 0 | 否 | 否 | 对话双方 |
| `presence` | 0 | 否 | 否 | 否 |
| `injection` | 0 或配置 | 由效果决定 | 否 | 可触发感知 |
| `lab_import` | 0 | 仅应用批准的冲击 | 否 | 可触发感知 |

`world_hour` 内固定顺序：

```text
1. 应用到点 Injection
2. 读取上一 revision 快照
3. 更新日程目标与可见范围
4. 生产 / 消费 / 市场清算
5. 构建每 Agent Perception
6. 生成 Plan / ActionIntent
7. 校验 WorldEffect
8. 应用 Agent、关系、派系、统计、任务效果
9. world.clock.advance(1)
10. 生成 EventEnvelope 并原子提交
11. 广播
12. 异步反思
```

## 3.3 当前 MarketState

核心字段：

```text
seed, tick
goods: dict[str, GoodState]
shocks: list[FinanceShock]
history: deque(maxlen=256)
last_events
money_supply, price_index, inflation, velocity, gini, volume
```

`GoodState`：

```text
id, name, base, price, inventory
supply_tick, demand_tick, suppliers
change_pct（派生）
```

`FinanceShock`：

```text
id
kind: supply | demand | price
good_id: str | "*"
magnitude: float
remaining: int
note: str
```

### 当前市场算法

每个市场 step：

```text
1. 清零每个商品 supply_tick / demand_tick。
2. 应用 shock：
   - supply shock 改供应倍率；
   - demand shock 改需求并消耗库存；
   - price shock 直接形成价格压力；
   - remaining -= 1。
3. 生产：
   - 排除 dormant Agent；
   - 按职业、工作时间和 activity 找 suppliers；
   - 增加供给、库存、Agent 收入与 savings。
4. 消费：
   - 根据 daily_expenses、财富倍率、随机偏好计算 want；
   - 增加 demand、减少库存、增加 volume。
5. 价格发现：
   - inventory pressure；
   - flow pressure；
   - 合成 delta 并截断；
   - 向 base price 均值回归。
6. 更新 money_supply、price_index、inflation、velocity、gini、volume。
7. 写 history 和验证事件。
```

### 改造要求

1. 删除独立 wall-clock finance loop；市场成为 `world_hour` 的确定性子步骤。
2. RNG state 必须进入 checkpoint 或从 `(session_seed, world_tick)` 派生。
3. 每个价格变化输出可审计信息：

```json
{
  "good_id": "grain",
  "price_before": 1.04,
  "price_after": 1.09,
  "supply": 42.0,
  "demand": 51.0,
  "inventory_pressure": 0.08,
  "flow_pressure": 0.11,
  "shock_ids": ["shock_x"]
}
```

4. `Agent.savings` 只允许由一个经济 reducer 修改，避免日程收入、市场和 LLM
   `economy_delta` 三条路径重复计算。
5. LLM 可以提出经济事件，但不能直接给最终价格。

## 3.4 制度与派系

当前制度演化主要在 Finance Labs 中生效，Play 未形成完整闭环。目标：

```python
InstitutionState:
  id: str
  kind: str
  legitimacy: float       # 0..1
  capacity: float         # 0..1
  inclusiveness: float    # 0..1
  corruption: float       # 0..1
  policy_tags: list[str]
  revision: int
```

制度每 N 个世界 tick 演化一次，输入只能来自已提交指标：

```text
population pressure
price inflation
gini
faction relations
public opinion
recent policy/world events
```

输出必须转换为 `WorldEffect`，不允许直接修改 Play 状态。

派系关系：

- 取值 `[-1,1]`；
- 每 tick 最大变化建议 `0.1`；
- 大于 `0.1` 的变化必须有高重要度事件作为 causation；
- UI 必须能显示“为何变化”。

---

## 4. L3 Agent 层：角色状态与认知闭环

## 4.1 当前 Agent 字段

```text
身份：
  id, name, kind(player|npc), persona, goals[], traits[]

世界：
  location_id, relations{}, avatar, appearance{}

职业与经济：
  profession
  schedule[{from,to,location,activity}]
  economy{
    income_label, income_per_unit, unit,
    daily_capacity, daily_expenses,
    starting_savings, meal_tier
  }
  current_activity, savings, today_income,
  today_customers, last_meal_tier

在线状态：
  presence(active|dormant|proxy)
  dormant_since_tick, last_observed_tick,
  last_heartbeat_ts, offline_mode, offline_rationale

3D：
  world_x, world_z, target_x, target_z, behavior

玩法：
  inventory[], equipment{}, skills[]
```

## 4.2 当前 Agentic 程度

| 环节 | 当前实现 |
|------|----------|
| Perceive | 对话/think 会召回近期与语义记忆；live tick 使用压缩上下文 |
| Plan | `reflect()` 写入 plan，但不是显式执行对象 |
| Act | 对话、Page 文本、批量 live tick decision |
| Reflect | 每隔若干 world tick 对 NPC 反思，输出 beliefs/plans |

因此当前更准确的描述是：

```text
Recall → LLM response / batch decision → periodic reflection
```

而不是严格的：

```text
Perceive → Plan → Act → Observe outcome → Reflect → Replan
```

## 4.3 目标认知数据结构

```python
@dataclass(frozen=True)
class Perception:
    perception_id: str
    actor_id: str
    revision: int
    world_tick: int
    visible_event_ids: tuple[str, ...]
    nearby_actor_ids: tuple[str, ...]
    recalled_memory_ids: tuple[str, ...]
    state_digest: str

@dataclass(frozen=True)
class AgentPlan:
    plan_id: str
    actor_id: str
    perception_id: str
    goal: str
    steps: tuple[str, ...]
    horizon_ticks: int
    confidence: float

@dataclass(frozen=True)
class ActionIntent:
    intent_id: str
    actor_id: str
    plan_id: str
    action_type: str
    arguments: dict
    dialogue: str | None
    expected_effects: tuple["WorldEffect", ...]

@dataclass(frozen=True)
class ReflectionRecord:
    reflection_id: str
    actor_id: str
    transaction_id: str
    outcome: str  # success | partial | failed | unknown
    belief_updates: tuple[str, ...]
    plan_updates: tuple[str, ...]
    salience: float
```

## 4.4 Perceive 算法

输入：不可变 Session snapshot、actor、已提交事件。

```text
1. 确定 actor 的 location_id 和 visibility。
2. 过滤事件：
   public
   ∪ actor_id 在 visibility.actor_ids
   ∪ 同地点且允许观察
   ∪ 角色所属 faction 可见
3. 查询附近 Agent；不得把不在场角色塞入上下文。
4. 召回：
   - 最近记忆 m=4；
   - 语义记忆 k=6；
   - open plan 最多 2；
   - active belief 最多 2。
5. 构建 state_digest，确保 Plan 对应特定 revision。
6. 保存 Perception 事件，只存引用和摘要，不复制完整敏感内容。
```

## 4.5 Plan 算法

```text
1. 读取 Agent goals、traits、open plans、Perception。
2. 若旧计划仍满足：
   - horizon 未过期；
   - precondition 仍成立；
   - 无高重要度冲突事件；
   则继续，不调用 LLM 重做。
3. 否则生成一个主计划：
   goal、steps、horizon_ticks、confidence。
4. 确定性校验：
   - 每个 step 的 action_type 在允许集合；
   - 不引用未知 Agent/地点；
   - 不越权替玩家做决定。
5. 保存 `agent.plan_created`。
```

## 4.6 Act 算法

```text
1. 当前 plan 选择下一 step。
2. 生成 ActionIntent，不直接改状态。
3. 把 expected_effects 交给 WorldEffect Validator。
4. 校验通过后与其他 Agent intent 仲裁：
   - 同资源冲突：按制度/优先级/随机种子决定；
   - 双方关系动作：双方都必须可见；
   - 玩家动作优先于 NPC 自动动作；
   - dormant 玩家无动作；proxy 受更严格资源上限。
5. 提交实际 applied effects。
```

## 4.7 Reflect 算法

触发条件从单纯 `tick % N` 改为：

```text
salience 累计 >= threshold
OR 计划失败
OR 高重要度关系/世界事件
OR 距上次反思 >= N 个已提交 world_hour
```

反思输入：

- 原 Plan；
- 实际提交 Event IDs；
- 成功/失败差异；
- 最近相关记忆。

输出必须引用已提交事件，不得虚构结果。

反思作为**后续事务**写入；失败不能回滚已经提交的世界行动。

## 4.8 Agent 效果指标

| 指标 | 目标 |
|------|------|
| `valid_effect_rate` | ≥ 99.5% |
| 活跃 Agent 决策覆盖 | 100% |
| 无效对象引用率 | < 0.1% |
| 玩家自主权违规 | 0 |
| 计划→行动一致率 | ≥ 95%（确定性规则判定） |
| 反思引用真实事件率 | ≥ 98% |
| 重启前后 recall@5 重合 | ≥ 90% |
| 同人格场景稳定性 | 固定场景评分不低于基线 |

---

## 5. L4 叙事与 WorldEffect

## 5.1 当前 Page 契约

```text
Beat:
  kind: narration | speech | action | system
  speaker: str | null
  content: str

Scene:
  location_id: str
  location_name: str
  summary: str
  present_agent_ids: list[str]

Page:
  page_no: int
  chapter: str
  scene: Scene
  beats: list[Beat]
  choices: list[{label,hint,action}]
  tension: float
```

当前 `session.step` 大致流程：

```text
wake → lock → injections → Director.direct_page
→ task auto-complete → append page event
→ force snapshot → fanout page
```

叙事 Page 本身不推进世界时钟，这是合理的；问题是 Page 的“行动描述”通常没有
结构化地改变世界。

## 5.2 目标 WorldEffect

```python
class EffectSource:
    kind: player | agent | system | lab | injection
    actor_id: str | None
    model: str | None
    prompt_version: str | None

class EffectTarget:
    type: world | stats | agent | relation | faction | finance | task
    id: str | None
    secondary_id: str | None

class EffectPrecondition:
    path: str
    op: eq | ne | gte | lte | exists
    value: JSONValue | None

class WorldEffect:
    schema_version: 1
    effect_id: str
    ordinal: int
    op: set | increment | append_unique | move_agent |
        adjust_relation | emit_event | create_task | schedule_shock
    target: EffectTarget
    path: str
    value: JSONValue | None
    delta: float | None
    preconditions: list[EffectPrecondition]
    source: EffectSource
    reason: str
    confidence: float  # 0..1
```

### 初始 allowlist

| Target | 允许字段 |
|--------|----------|
| `world` | `facts` |
| `stats` | `politics/economy/livelihood/military/environment` |
| `agent` | `location_id/current_activity/behavior/savings/today_income/goals` |
| `relation` | `value` |
| `faction` | `relations.{faction_id}` |
| `finance` | 只允许批准的 shock，不允许 LLM 直接设 price |
| `task` | create / progress / complete |

禁止：

- 修改 ID、kind、用户成员、host、token、presence；
- 任意 dotted path；
- 删除世界对象；
- 自动移动 active 玩家；
- 非有限数；
- 一 tick 内大幅关系跳变；
- LLM 直接提交最终市场价格。

### Validator 算法

```text
1. Pydantic/schema 验证。
2. effect_id 唯一，ordinal 从 0 连续。
3. target 必须存在；create 操作除外。
4. 所有 precondition 在同一 base snapshot 上检查。
5. 数值必须 finite：
   stats ∈ [0,100]
   relation ∈ [-1,1]
   单 tick relation delta ∈ [-0.25,0.25]
6. 校验 actor 权限与玩家自主权。
7. 按 (ordinal, effect_id) 稳定排序。
8. 任一 effect 非法 → 整组拒绝，不做部分提交。
9. 在 state copy 上应用，并再次校验全局不变量。
```

### Page 与 Effect 的关系

目标响应：

```json
{
  "page": {
    "page_no": 12,
    "chapter": "第三章",
    "scene": {},
    "beats": [],
    "choices": [],
    "tension": 0.62
  },
  "effects": [],
  "command_id": "cmd_uuid",
  "revision": 85,
  "world_tick": 31
}
```

叙事必须根据**实际提交后的 effect/event**生成最终文本；如果先生成文本，提交时 effect
冲突，则必须重新生成简短校正文案，不能向用户展示未发生的结果。

---

## 6. Session Runtime：统一事务、幂等与单写者

## 6.1 当前 Session

```text
id
world
society
memory
director
events
injections
tasks
finance
finance_lab
player_ids
pages
subscribers
lock
user_id
seed_key
max_players
simulation_running
simulation_last_model/error/tick/reasoning
_loc_snapshot
```

当前 `_SESSIONS` 是 worker 内存字典，`asyncio.Lock` 只保护当前进程。

## 6.2 目标 TickCommand

```python
@dataclass(frozen=True)
class TickCommand:
    command_id: str
    session_id: str
    kind: TickKind
    actor_id: str | None
    user_id: str | None
    expected_revision: int | None
    advance_hours: int
    payload: dict
    requested_at_ms: int
    correlation_id: str
```

## 6.3 目标 TickTransaction

```python
@dataclass
class TickTransaction:
    transaction_id: str
    session_id: str
    command_id: str
    base_revision: int
    target_revision: int
    base_world_tick: int
    target_world_tick: int
    lease_fence: int
    phase: str
    attempt: int
    effects: list[WorldEffect]
    event_ids: list[str]
    error_code: str | None
```

状态机：

```text
RECEIVED
→ LEASED
→ SNAPSHOT
→ PERCEIVE
→ PLAN
→ ACT
→ VALIDATE
→ COMMIT
→ REFLECT
→ PUBLISH
→ COMPLETE

终态：REJECTED | CONFLICT | FAILED
```

## 6.4 执行算法

```python
async def execute(command):
    prior = event_store.result_for_command(command.session_id, command.command_id)
    if prior:
        return prior

    lease = await leases.acquire(command.session_id)
    try:
        async with session.lock:
            base = freeze_session(session)
            require_revision(command.expected_revision, base.revision)

        # 不持有 session lock 进行慢 LLM
        perceptions = perceive(base, command)
        plans = await plan_all(base, perceptions, command)
        intents = await act_all(base, plans, command)
        effects = validate_effects(normalize(intents), base)

        async with session.lock:
            await leases.assert_valid(lease)
            if session.revision != base.revision:
                raise RevisionConflict()

            post = apply_effects_to_copy(base, effects)
            post.revision = base.revision + 1
            post.world_tick = base.world_tick + command.advance_hours

            with sqlite_transaction():
                events = append_enveloped_events(command, effects, post, lease.fence)
                update_session_head_compare_and_swap(...)
                maybe_checkpoint(post)

            install_state(session, post)

        await publish(events)
        enqueue_reflection(post, events)
        return command_result(events, post)
    finally:
        await leases.release(lease)
```

关键点：

- LLM 调用不持有长锁；
- 提交前重新检查 revision 和 fence；
- 持久化成功后才替换内存状态和广播；
- 反思异步且独立；
- 所有现有 `step/talk/inject/finance` 最终都应成为 command wrapper。

## 6.5 Redis lease

Key：

```text
civsim:session:{sid}:lease
civsim:session:{sid}:fence
```

Lease value：

```json
{
  "owner_id": "worker_a",
  "token": "random_uuid",
  "fence": 42,
  "acquired_ms": 1791734400000
}
```

参数：

- TTL：15 秒；
- 每 5 秒续约；
- 交互命令获取超时：2 秒。

获取、续约、释放必须用 Lua 比较 token。每次成功获取执行 `INCR fence`。

持久层新增：

```sql
CREATE TABLE session_heads (
  session_id TEXT PRIMARY KEY,
  revision INTEGER NOT NULL,
  world_tick INTEGER NOT NULL,
  last_sequence INTEGER NOT NULL,
  writer_fence INTEGER NOT NULL,
  checkpoint_id TEXT,
  updated_at_ms INTEGER NOT NULL
);
```

提交 CAS：

```sql
UPDATE session_heads
SET revision = :next_revision,
    world_tick = :next_world_tick,
    last_sequence = :last_sequence,
    writer_fence = :fence,
    updated_at_ms = :now
WHERE session_id = :sid
  AND revision = :base_revision
  AND writer_fence <= :fence;
```

必须恰好更新 1 行；否则回滚并返回 conflict / lease lost。

## 6.6 EventEnvelope

```json
{
  "schema_version": 1,
  "event_id": "evt_uuid",
  "session_id": "sess_x",
  "sequence": 1825,
  "revision": 85,
  "world_tick": 31,
  "event_type": "world.effect_applied",
  "occurred_at_ms": 1791734400123,
  "recorded_at_ms": 1791734400130,
  "producer": "backend.tick-coordinator",
  "producer_version": "0.7.0",
  "actor": {
    "user_id": "user_x",
    "agent_id": "agent_x",
    "kind": "player"
  },
  "correlation_id": "corr_x",
  "causation_id": "cmd_or_event_x",
  "command_id": "cmd_uuid",
  "idempotency_key": "cmd_uuid",
  "lease_fence": 42,
  "visibility": {
    "scope": "session",
    "actor_ids": []
  },
  "payload_type": "WorldEffectAppliedV1",
  "payload": {},
  "metadata": {
    "request_id": "req_x",
    "model": null
  }
}
```

新增索引：

```sql
UNIQUE(event_id)
UNIQUE(session_id, sequence)
UNIQUE(session_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL
```

旧事件以 `schema_version=0` adapter 读取，不强行回填不可推断的 command 字段。

---

## 7. API 契约演进

## 7.1 通用错误 envelope

### 后端响应

```json
{
  "error": {
    "code": "SESSION_REVISION_CONFLICT",
    "category": "conflict",
    "message": "世界已更新，请刷新后重试",
    "retryable": true,
    "retry_after_ms": 300,
    "field_errors": null,
    "details": {
      "expected_revision": 81,
      "actual_revision": 82
    }
  },
  "request_id": "req_x",
  "correlation_id": "corr_x"
}
```

### 前端类型

```typescript
type ErrorCategory =
  | "auth"
  | "authorization"
  | "validation"
  | "conflict"
  | "quota"
  | "dependency"
  | "network"
  | "realtime"
  | "persistence"
  | "simulation"
  | "internal";

type AppError = {
  code: string;
  category: ErrorCategory;
  message: string;
  status: number;
  retryable: boolean;
  retryAfterMs?: number;
  requestId?: string;
  correlationId?: string;
  fieldErrors?: Record<string, string[]>;
  details?: Record<string, unknown>;
};
```

### 必须错误码

```text
AUTH_REQUIRED
TOKEN_EXPIRED
SESSION_FORBIDDEN
VALIDATION_FAILED
SESSION_BUSY
SESSION_LEASE_LOST
SESSION_REVISION_CONFLICT
IDEMPOTENCY_KEY_REUSED
LLM_QUOTA_EXCEEDED
QUOTA_BACKEND_UNAVAILABLE
LLM_UNAVAILABLE
SIMULATION_OUTPUT_INVALID
SNAPSHOT_CORRUPT
SNAPSHOT_VERSION_UNSUPPORTED
LAB_EXPORT_STALE
NETWORK_OFFLINE（前端）
WS_RECONNECT_EXHAUSTED（前端）
INTERNAL_ERROR
```

UI 策略：

| category | UI |
|----------|----|
| auth | 保留 `next` 并转登录 |
| validation | 字段级错误 |
| conflict | 刷新后重试 / 重新应用 |
| quota | 显示重置时间，不做自动重试 |
| dependency | 显示 Ollama/Redis 等依赖状态与重试 |
| realtime | 降级 HTTP poll，给手动重连 |
| persistence | 阻止覆盖，提供恢复/导出诊断 |
| simulation | 保留当前世界，显示降级横幅 |
| internal | 通用文案 + request ID |

## 7.2 幂等

所有 mutation REST 接口支持：

```http
Idempotency-Key: <client-generated UUID>
If-Match-Revision: <integer>
```

WebSocket mutation：

```json
{
  "type": "command",
  "command_id": "uuid",
  "expected_revision": 84,
  "kind": "narrative",
  "payload": {}
}
```

相同 key + 相同 body → 返回原结果。  
相同 key + 不同 body → `409 IDEMPOTENCY_KEY_REUSED`。

## 7.3 核心 REST：当前字段

### 创建 Session

```http
POST /api/sessions
Authorization: Bearer <token>
```

请求：

```json
{
  "seed_key": "ancient",
  "description": "角色描述，可选",
  "category_key": "scholar",
  "variant_key": "young",
  "skin": "default",
  "max_players": 8
}
```

响应：

```json
{
  "session": "Session",
  "page": "Page"
}
```

`max_players ∈ [2,16]`。

### Step

当前：

```http
POST /api/sessions/{sid}/step
```

```json
{
  "input": "向城门走去",
  "player_id": "agent_player"
}
```

目标响应增加：

```json
{
  "page": {},
  "stats": {},
  "session": {},
  "command_id": "cmd_uuid",
  "revision": 85,
  "world_tick": 31,
  "effects": [],
  "events": []
}
```

### Talk

```http
POST /api/sessions/{sid}/talk
```

```json
{
  "npc_id": "agent_npc",
  "text": "最近城里发生了什么？",
  "player_id": "agent_player"
}
```

响应：

```json
{
  "npc_id": "agent_npc",
  "npc_name": "守门人",
  "reply": "...",
  "command_id": "cmd_uuid",
  "revision": 86
}
```

### 注入事件

```http
POST /api/sessions/{sid}/inject/event
```

```json
{
  "tick": 36,
  "summary": "粮仓失火",
  "importance": 0.9,
  "location_id": "granary"
}
```

服务端必须验证：

- host 权限；
- `tick >= current_tick`；
- `importance ∈ [0,1]`；
- `location_id` 存在；
- summary 长度限制。

### 注入角色

```json
{
  "tick": 40,
  "name": "流浪医师",
  "persona": "谨慎而善良",
  "profession": "healer",
  "location_id": "market",
  "traits": ["谨慎", "仁慈"],
  "goals": ["寻找药材"],
  "agent_kind": "npc"
}
```

## 7.4 Session 响应字段

当前 `Session` 应保持兼容：

```text
id
world
agents[]
player_id
player_ids[]
roster[{
  player_id, user_id, name, presence, is_self, is_host
}]
user_id
host_user_id
max_players
seed_key
pages[]
tension_curve[]
stats
finance
finance_lab
simulation{
  provider, running, last_model, last_tick,
  last_error, last_reasoning, continuous
}
injections[]
tasks[]
```

目标新增：

```text
revision: int
writer: {
  mode: single | leased
  owner_hint?: str
  lease_healthy: bool
}
capabilities: {
  world_injection: bool
  lab_bridge: bool
  spectator: bool
  mobile_narrative: bool
}
quota?: {
  day_utc
  user_used, user_limit
  session_used, session_limit
  reset_at_ms
}
```

## 7.5 WebSocket

### 当前 Client → Server

```text
hello {token, player_id?}
heartbeat {player_id?}
pong
move {world_x, world_z, player_id}
input {input, player_id?}
sleep {reason?}
wake
ping
```

### 当前 Server → Client

```text
snapshot {session}
page {page, stats?}
npc_dialogue
presence
wake
finance_tick
finance_shock
simulation_tick
simulation_error
player_joined
player_kicked
host_transferred
agent_transform
agent_transforms
ping
error
```

### 目标统一 envelope

```json
{
  "type": "event",
  "event_id": "evt_uuid",
  "sequence": 1825,
  "revision": 85,
  "world_tick": 31,
  "event_type": "page.created",
  "correlation_id": "corr_x",
  "payload": {}
}
```

客户端保存最后 `sequence`，重连时：

```json
{
  "type": "hello",
  "token": "...",
  "player_id": "agent_x",
  "last_sequence": 1810,
  "client_version": "0.7.0"
}
```

服务端：

1. gap 可补 → 发送 `events[]`；
2. gap 过大或事件已压缩 → 发送完整 `snapshot`；
3. sequence 重复 → 客户端丢弃；
4. sequence 缺口 → 客户端请求 resync。

### 当前重连算法

```text
最大 8 次
delay = min(8000, 800 + (attempt - 1) × 1200) ms
fatal auth/member 错误不重试
close code 4001 = kicked
失败后允许手动 retry
WS 断开时每 4 秒 HTTP polling
```

建议改为带随机抖动：

```text
base = min(10000, 500 × 2^(attempt-1))
delay = base × random(0.8, 1.2)
```

浏览器离线时暂停重试；`online` 事件后恢复。后台 tab 降低 polling 频率。

---

## 8. Play ↔ Labs 数据桥

禁止 Labs 直接修改运行中的 Play。必须采用：

```text
导出快照 → 独立推演 → 生成提案 → Host 审批 → WorldEffect 校验 → 幂等提交
```

## 8.1 导出

```python
class PlayLabExport:
    bridge_version: 1
    export_id: str
    session_id: str
    source_revision: int
    source_world_tick: int
    civilization_key: str
    world: dict
    metrics: dict[str, float]
    finance: dict | None
    population: dict | None
    factions: list[dict]
    recent_events: list[EventEnvelope]
    state_digest: str
```

接口：

```http
POST /api/sessions/{sid}/lab-exports
```

请求：

```json
{
  "lab_key": "finance",
  "event_window": 48,
  "include_private_agent_memory": false
}
```

响应：

```json
{
  "export": "PlayLabExport",
  "workspace_url": "/labs/finance?export_id=..."
}
```

## 8.2 推演结果

```python
class LabBridgeResult:
    run_id: str
    export_id: str
    lab_key: str
    engine_version: str
    parameters: dict
    horizon: int
    metrics_before: dict[str, float]
    metrics_after: dict[str, float]
    proposed_effects: list[WorldEffect]
    assumptions: list[str]
    confidence: float
    reproducibility: dict
```

`reproducibility`：

```json
{
  "seed": "abc",
  "dataset_hashes": [],
  "config_hash": "...",
  "engine_version": "finance-v2"
}
```

## 8.3 审批应用

```http
POST /api/sessions/{sid}/lab-proposals
```

```json
{
  "run_id": "run_x",
  "export_id": "exp_x",
  "selected_effect_ids": ["eff_1", "eff_2"],
  "expected_revision": 84
}
```

若当前 revision 已变化：

```text
409 LAB_EXPORT_STALE
```

不得直接 rebase 旧 effects；必须重新导出并重新校验。

---

## 9. 顶层产品与用户体验

## 9.1 当前路由

```text
/                       三入口首页
/login                  登录/注册/重置/魔法链接/验证
/simulator              世界选择
/create/[seedKey]       角色创建
/play/[sid]             Play
/join/[sid]             加入房间
/worlds                 我的世界
/civilizations          自定义文明管理
/civilizations/new      新建文明
/civilizations/[id]/edit
/labs
/labs/[labKey]
/generator
/docs
/contact
```

## 9.2 当前 PlayMode

```typescript
type PlayMode =
  | "LOADING"
  | "EXPLORE"
  | "DIALOGUE"
  | "OVERLAY_MAP"
  | "OVERLAY_JOURNAL"
  | "OVERLAY_CHARACTER"
  | "OVERLAY_WORLD_STATE"
  | "SYSTEM_MENU"
  | "RECONNECTING"
  | "WAKE_BRIEFING";
```

优先级：

```text
LOADING
> RECONNECTING
> WAKE_BRIEFING
> SYSTEM_MENU
> OVERLAY
> DIALOGUE
> EXPLORE
```

目前 `playMode` 主要用于局部控制，没有成为完整 UI 状态机。后续必须：

- 每种模式定义允许的输入；
- modal/overlay 有 focus trap；
- RECONNECTING 禁止重复提交；
- WAKE_BRIEFING 阅读完再恢复行动；
- SYSTEM_MENU 打开时释放 pointer lock。

## 9.3 首次用户旅程

目标：

```text
访客预览
→ 注册/登录（保留 next）
→ 选择“玩故事 / 做实验 / 创文明”
→ 选择模板
→ 分阶段创建反馈
→ 60 秒内完成第一行动
→ 3 分钟内得到第一次有意义反馈
```

创建进度建议：

```text
validate_character
load_seed
spawn_society
create_market
generate_opening
save_snapshot
ready
```

前端展示真实阶段，禁止只有无限“正在召唤世界”。

## 9.4 v0.5.1 必修体验问题

1. 登录读取并安全验证 `?next=`，只允许站内路径。
2. `/civilizations/new` 未登录立即重定向，禁止无限 loading。
3. `TaskPanel` 接入 Journal，允许创建/完成 self task。
4. 将世界事件/NPC 注入从 dev panel 改为 host-only 正式“故事导演”。
5. `quality` 设置必须真正影响 LOD/后处理，否则删除。
6. 429 显示配额与 UTC 重置时间；503 显示模型依赖与重试。
7. 邀请用 Web Share API 或复制 toast，禁止 blocking `alert()`。
8. 修复 NPC 点击事件携带 `npcId` 后直接打开对应对话。
9. Footer、版本和 Tech Preview 文案使用单一版本源。

## 9.5 Labs 体验

每个 ready lab 提供：

- 一个“快速示例”模板；
- 一个“高级参数”折叠区；
- 输入假设摘要；
- 推演进度；
- 结果解释：“哪个变量导致哪个变化”；
- 可重复性信息；
- 导出 PDF/JSON；
- 从 Play 导入、向 Play 提案。

体验指标：

| 指标 | 目标 |
|------|------|
| 首次进入到第一张结果图 | < 3 分钟 |
| 首次进入到完整报告 | < 5 分钟 |
| 无文档辅助完成率 | ≥ 80%（5+ 人可用性测试） |
| 报告失败可恢复率 | 100% 有明确重试 |

## 9.6 Creator 体验

增加：

```text
draft_id
updated_at
schema_version
validation_errors[]
preview_status
test_run_id
```

能力：

1. 每 30 秒或字段 blur 自动保存本地草稿；
2. 返回时提示恢复；
3. 字段级校验，不把原始 422 直接扔给用户；
4. 地图、派系、角色即时预览；
5. 一键“试跑开场”，不直接创建正式世界；
6. schema 升级时迁移草稿。

## 9.7 移动端策略

不建议短期追求完整手机 3D。先提供“移动叙事模式”：

- `pointer: coarse` 时默认关闭 pointer lock；
- 位置卡 + NPC 列表；
- “前行 / 对话 / 选择 / 自由输入”触控操作；
- 地图和状态用全屏 sheet；
- 3D 作为可选预览；
- 桌面仍为完整探索模式。

## 9.8 产品分析

前端事件：

```text
onboarding_started/completed
session_create_started/succeeded/failed
first_step_succeeded
step_failed
ws_reconnect_started/exhausted
invite_copied/join_succeeded
world_restored
lab_opened/run_started/run_completed/report_exported
creator_draft_saved/test_run_completed/published
```

字段只允许：

```text
event_name
timestamp
app_version
anonymous_user_hash
session_hash
surface
outcome
duration_ms
error_code
```

禁止上传对话、prompt、角色背景和自定义文明正文。

---

## 10. 测试与评测

## 10.1 单元与属性测试

| 模块 | 必测内容 |
|------|----------|
| WorldEffect | range、reference、权限、排序、整组原子性 |
| Reducer | 同输入产生同 canonical hash |
| Lease | 获取、续约、过期、旧 fence 禁止提交 |
| Quota | 并发不超限、不部分扣费、重试幂等 |
| Memory | checkpoint checksum、恢复、Qdrant 降级 |
| Event | sequence 唯一、idempotency、legacy adapter |
| Market | 固定 seed 价格轨迹、shock 衰减、财富守恒约束 |
| Agent | visibility、计划复用、反思 grounded |

推荐 property-based tests：

```text
任意合法 effect 序列应用后：
stats 永远在 [0,100]
relations 永远在 [-1,1]
world_tick 单调
revision 严格 +1
active player 不被自治移动
所有引用 ID 存在
```

## 10.2 集成测试

### 单 worker

```text
register
→ create
→ step
→ talk
→ world_hour
→ checkpoint
→ kill
→ restore
→ continue
```

### 双 worker

```text
1. A 获取 lease，暂停超过 TTL。
2. B 获取新 fence 并提交。
3. A 恢复后提交必须失败。
4. 两端 WS 只能收到一次已提交事件。
5. 不得出现重复 revision 或 sequence。
```

### 配额

100 个并发请求跨两个 worker：

- 实际允许数不得超过 limit；
- user/session 任一超限时不部分扣费；
- 重复 request_id 不重复扣费。

### Play–Labs

```text
Play export
→ Lab run
→ proposal
→ host preview
→ apply once
→ stale revision rejects
```

## 10.3 Agent 评测集

至少固定：

- 3 个文明种子；
- 每个 24 个世界小时；
- 5 类情境：资源短缺、关系冲突、灾害、政策变化、多人协作；
- recorded LLM 响应；
- 真实模型 nightly 评测。

输出：

```text
schema_valid_rate
effect_valid_rate
plan_action_consistency
persona_consistency
causal_contradiction_rate
memory_recall_precision
world_state_hash
token_cost_per_world_hour
latency_p50/p95
```

## 10.4 前端自动化

PR 必跑：

```text
未登录 → login
register/login → 正确 next
create → first step
429 quota UI
503 dependency UI
WS reconnect + HTTP degrade
world restore
Labs quick template → report
Creator draft recovery
```

Nightly：

- 双浏览器多人 join / kick / transfer；
- 断 Redis；
- 杀 worker；
- 移动叙事模式；
- axe-core；
- 30 分钟 Play soak。

## 10.5 性能与可靠性门禁

| 指标 | 目标 |
|------|------|
| 非 LLM tick commit p95 | < 100 ms |
| 云模型 narrative p95 | < 8 秒（v1 目标；过渡期 < 15 秒） |
| lease acquisition p95 | < 100 ms |
| commit→WS p95 | < 250 ms |
| 10k events restore p95 | < 2 秒 |
| committed event 丢失 | 0 |
| duplicate event | 0 |
| checkpoint 恢复成功率 | ≥ 99.9% |
| Session create/step 成功率 | ≥ 99% |
| 72h soak | 0 个 split-brain / P0 |

---

## 11. 版本规划

## 11.1 `v0.5.1`：因果与体验修补

建议周期：2–3 周。

### 后端

- 统一 world/finance tick；
- Memory checkpoint MVP（最近 K 条）；
- Redis 共享 quota；
- 通用 error envelope；
- mutation 支持 Idempotency-Key；
- recorded live tick fixture；
- 修复或删除无效的 tension/background dead path。

### 前端

- 登录 `next`；
- creator auth；
- TaskPanel；
- host 故事导演；
- 429/503/reconnect UX；
- quality 真正接入；
- auth→create→step Playwright CI。

### 出口标准

- tick 对齐测试 24 小时零漂移；
- 重启前后 recent memory ≥ 90%；
- 双 worker quota 不超限；
- 主路径 E2E 绿；
- 不新增大功能。

## 11.2 `v0.6.0`：Agent 闭环与可评测

建议周期：4–6 周。

- TickCommand/TickTransaction 第一版；
- WorldEffect + validator + reducer；
- Plan/Belief 强制进入行动上下文；
- 每 Agent Perception；
- golden trace；
- Play→Labs 导出只读版；
- Creator 草稿与试跑。

出口：

- valid effect ≥ 99.5%；
- 玩家自主权违规 0；
- fixture replay 100% 一致；
- 第一批因果报告可查看。

## 11.3 `v0.7.0`：多人韧性与移动叙事

建议周期：4–6 周。

- Redis lease + durable fence；
- session_heads / revision；
- WS sequence/resync；
- 双 worker CI；
- spectator / 轻量房间社交；
- 移动叙事模式；
- a11y critical = 0。

## 11.4 `v0.8.0`：可运营运行时

建议周期：6–8 周。

- Snapshot v2 + tail replay；
- 完整 EventEnvelope；
- Qdrant/SQLite 一致恢复；
- Prometheus/OpenTelemetry；
- 备份一致性 checkpoint；
- chaos、恢复、长稳测试；
- Labs proposal apply。

## 11.5 `v0.9.0`：公开预览验收

- OAuth/邮箱策略；
- 产品分析和反馈；
- 负载测试；
- 依赖审计硬门禁；
- 操作手册、告警、RTO/RPO；
- staging 72h soak。

## 11.6 `v1.0.0`：公开多租户

必须具备：

- 租户/组织边界；
- 横向 Session Runtime；
- Redis required 的生产拓扑；
- Postgres 或明确的共享持久层；
- 完整数据迁移；
- SLA 与告警；
- 计费钩子或明确 self-hosted-only 定位；
- 零跨租户读写；
- 72 小时零 P0。

---

## 12. 建议代码落点

```text
backend/app/runtime/
  commands.py          TickCommand
  coordinator.py       TickTransaction state machine
  effects.py           WorldEffect + validator
  reducer.py           deterministic state reducer
  leases.py            in-memory / Redis lease
  idempotency.py

backend/app/contracts/
  errors.py
  events.py
  telemetry.py
  lab_bridge.py

backend/app/layer3_agents/
  perception.py
  planning.py
  actions.py
  reflection.py

backend/app/layer6_persistence/
  migrations.py
  session_heads.py
  checkpoints.py

frontend/src/lib/
  errors.ts
  commands.ts
  telemetry.ts

frontend/src/components/play/
  StoryDirectorPanel.tsx
  QuotaNotice.tsx
  DependencyStatus.tsx
  MobileNarrativeControls.tsx
```

迁移过程中不要一次性重写 `session.py`。采用 strangler：

```text
阶段 1：现有函数包装成 TickCommand          ✅（narrative step）
阶段 2：新命令走 coordinator，旧响应兼容    ✅（additive 字段）
阶段 3：WorldEffect 替代 direct mutation    ⏳（校验已上；多数 mutation 仍在旧路径）
阶段 4：持久化切到 EventEnvelope + session_heads  ⏳（_envelope 嵌套已上）
阶段 5：删除旧 mutation path                ⏳
```

---

## 13. 数据迁移与兼容

### Snapshot

- 继续读取 v0/v1；
- 首次成功恢复后写 v2；
- 不原地覆盖旧快照；
- 不认识的 required schema → 明确错误；
- 不认识的 optional 字段 → 忽略。

### Event

- 旧事件包装为 `schema_version=0`；
- synthetic sequence 仅用于读取，不宣称原始幂等；
- 新事件必须有 event_id、sequence、revision；
- migration 必须可重复执行。

### API

- 现有 response 字段至少保留两个小版本；
- 新字段 additive；
- 删除字段前先发 deprecation telemetry；
- WebSocket 新旧 message 可由 `client_version` 协商。

### 前端缓存

- `sess_{sid}` 增加 cache schema version；
- 版本不匹配时清空并重新拉 snapshot；
- `civsim_play_settings` 提供迁移函数；
- Creator draft 单独版本化。

---

## 14. 开发执行模板

每个架构任务必须包含：

```text
1. 问题与不变量
2. 当前代码证据
3. 数据结构
4. 算法/状态机
5. REST/WS 契约
6. 兼容与迁移
7. 失败与降级
8. 安全/隐私
9. 指标
10. 单元、集成、E2E
11. 文档更新
12. 发布门禁
```

PR 不得只写“实现 Redis / 优化 Agent”。必须写清：

- key；
- TTL；
- 原子性；
- owner；
- 幂等；
- 错误；
- 指标；
- 测试；
- 回滚。

---

## 15. Definition of Done

一个功能只有同时满足以下条件才算完成：

- [ ] 数据结构和字段已定义；
- [ ] 不变量和权限边界已定义；
- [ ] 正常算法和失败算法已实现；
- [ ] REST/WS 契约已更新；
- [ ] 幂等、重试、超时、降级已处理；
- [ ] 迁移和旧版本兼容已验证；
- [ ] 日志、指标和错误码可观察；
- [ ] 单元、集成、E2E 覆盖；
- [ ] 用户 UI 可发现且文案准确；
- [ ] 中英文 README / 专题文档同步；
- [ ] 冷启动与主路径门禁通过；
- [ ] 无 P0/P1 未解释风险。

---

## 16. 下一步建议

**已落地：** TickCoordinator 管线（§0.2）+ 统一 WORLD_HOUR/金融时钟 + Memory checkpoint MVP（快照 v2）。

`v0.5.1` 剩余优先序：

1. **共享 quota**：多 worker 邀测不绕过限制。
2. **Idempotency-Key header + 稳定 Error envelope**（HTTP 中间件级，不只 step）。
3. **登录深链、任务、故事导演、错误 UX**：修复最明显用户断点。
4. **Playwright PR smoke**：把当前手工主路径变成持续门禁。

进入 `v0.6` 前完成：Redis lease、session_heads、LLM Plan→Act 读取闭环；不要在
多 worker 权威未建立前直接尝试完整多租户或计费。

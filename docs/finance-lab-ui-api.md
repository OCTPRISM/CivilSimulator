# 金融实验室 — 前端 UI 设计与前后端接口技术规格

> **文档版本**：2026-08-30（三轮校验修订）  
> **适用范围**：CivilSimulator 实验平台中的「金融实验室」（`lab_key = finance`）  
> **读者**：前端 UI 设计师、前端/后端开发、QA  
> **定位**：本文档描述**当前已实现**的 UI 结构、交互行为、数据契约与 API，作为后续优化升级的**唯一基准**。若代码与文档冲突，以代码为准，并应同步更新本文档。  
> **关联文档**：[全站 UI/API 完整规格](./ui-design-and-api-complete.md) · [文档索引](./README.md) · [3D 世界与人物](./3d-world-and-characters.md) · [叙事 Play 会话](./play-session-ui-api.md)  
> **说明**：实验平台 `/labs/*` **不含 3D**；3D 仅用于 `/play/[sid]`，见 [3D 文档 §10](./3d-world-and-characters.md#10-与实验平台的关系)。

---

## 目录

0. [文档集索引](#0-文档集索引)
1. [产品边界与入口](#1-产品边界与入口)
2. [系统架构总览](#2-系统架构总览)
3. [前端路由与页面结构](#3-前端路由与页面结构)
4. [UI 设计规范](#4-ui-设计规范)
5. [金融实验室页面布局](#5-金融实验室页面布局)
6. [FinancePanel 组件规格](#6-financepanel-组件规格)
7. [子组件规格](#7-子组件规格)
8. [前端状态与数据流](#8-前端状态与数据流)
9. [用户操作流程](#9-用户操作流程)
10. [TypeScript 类型契约](#10-typescript-类型契约)
11. [后端 API 完整规格](#11-后端-api-完整规格)
12. [推演引擎与 simulation 对象](#12-推演引擎与-simulation-对象)
13. [报告（LabReport）结构](#13-报告labreport结构)
14. [错误处理与边界条件](#14-错误处理与边界条件)
15. [已知限制与废弃路径](#15-已知限制与废弃路径)
16. [源码索引](#16-源码索引)

---

## 0. 文档集索引

| 文档 | 内容 |
|------|------|
| [docs/README.md](./README.md) | 全项目文档地图、genre 对照、认证速查 |
| **本文** | 金融实验室 UI + API |
| [play-session-ui-api.md](./play-session-ui-api.md) | 叙事游戏 `/play/[sid]` |
| [3d-world-and-characters.md](./3d-world-and-characters.md) | 3D 地图 JSON、建筑 GLB、人物 GLTF |

---

## 1. 产品边界与入口

### 1.1 产品定位

金融实验室是**文明背景下的情景沙盘**：在可控、可复现的数值模型上，测试「若发生某事件，宏观 / 城市 / 企业 / 市场指标可能如何演化」。

- **不是**实盘投资建议、监管报送或专业计量模型。
- **数值**由 seed 驱动的确定性/半确定性引擎生成。
- **LLM（Ollama）** 仅用于：事件 NER 结构化、narrative 文案润色；**不参与生成数值**。

### 1.2 入口（当前实现）

| 入口 | 路径 | 是否挂载 FinancePanel | 说明 |
|------|------|----------------------|------|
| **实验平台（主入口）** | `/labs/finance` | ✅ 是 | 推荐路径；需登录 |
| 首页快捷卡片 | `/` → 实验平台区 → 金融实验室 | ✅ 是 | 同 `/labs/finance` |
| 游戏会话页 | `/play/[sid]` | ❌ **否** | 已移除金融实验室入口；`FinancePanel` 仍支持 session 模式但当前未挂载 |

### 1.3 认证要求

| 操作 | 认证 |
|------|------|
| 浏览首页、实验室列表 | 需登录（前端 gate → `/login`） |
| `GET /api/seeds` | **可选**认证（登录后响应含自定义文明） |
| `POST /api/labs/finance/open` 及所有 workspace 操作 | **必须** `Authorization: Bearer <token>` |
| 会话内 finance API（legacy） | **无**认证（持有 `sid` 即可调用） |

Token 格式：`user_id:exp:hmac_sig`，TTL 30 天，存于 `localStorage` 键 `civsim_token`。

---

## 2. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Next.js App Router)                                    │
│  /labs/finance → LabDetailPage → FinancePanel                    │
│       │                    │              │                      │
│       │ listSeeds/openLab  │              ├─ InstitutionsPanel   │
│       │                    │              ├─ AuditTrailPanel    │
│       │                    │              ├─ LabReportView       │
│       │                    │              └─ FanChart / Sparkline│
└───────┼────────────────────┼──────────────┼──────────────────────┘
        │ fetch /api/*       │              │
        ▼                    ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI (backend/app/main.py)                                   │
│  POST /api/labs/{lab_key}/open                                   │
│  POST /api/labs/workspace/{lab_id}/finance/simulate  ← 主路径    │
│  POST /api/labs/workspace/{lab_id}/events/manual                 │
│  POST /api/labs/workspace/{lab_id}/datasets/upload               │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  backend/app/labs/workspace.py :: lab_finance_simulate()         │
│    1. prepare_simulation() 重置 desk                             │
│    2. _apply_timeline_to_finance() 注入事件                      │
│    3. market warmup → macro closure（global/city/corporate/retail）│
│    4. desk.forecast() / retail.run() / market.advance()        │
│    5. build_report() + enrich_finance_report()                   │
│    6. build_pdf_bytes() → pdf_base64                             │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  数值引擎                                                         │
│  • structured_macro_v2 (finance_sim_core.py) — global/city/corp  │
│  • agent_based_market_v1 (finance.py) — market 模式              │
│  • GBM 合成路径 — retail 模式                                     │
│  • 长程融合 finance_longrun.py + finance_fusion_config.py        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 两种产品模式对比

| 维度 | 叙事模拟器（Play） | 实验平台（Labs） |
|------|-------------------|-----------------|
| 入口 | `/play/[sid]` | `/labs/[labKey]` |
| 状态 | `Session`（page state + sessionStorage） | `LabWorkspace`（page state） |
| 金融功能 | API 存在，UI **未挂载** | FinancePanel 完整功能 |
| 主推演 API | `/api/sessions/{sid}/finance/lab/*`（legacy） | `/api/labs/workspace/{id}/finance/simulate` |

---

## 3. 前端路由与页面结构

### 3.1 路由表

| 路由 | 文件 | 职责 |
|------|------|------|
| `/` | `frontend/src/app/page.tsx` | 首页：实验平台卡片 + 文明种子列表 |
| `/login` | `frontend/src/app/login/page.tsx` | 登录/注册 |
| `/labs` | `frontend/src/app/labs/page.tsx` | 实验室索引 |
| `/labs/finance` | `frontend/src/app/labs/[labKey]/page.tsx` | 金融实验室工作区 |
| `/labs/[labKey]` | 同上 | 其他实验室（policy、weather 等） |
| `/play/[sid]` | `frontend/src/app/play/[sid]/page.tsx` | 叙事游戏（**无**金融入口） |
| `/create/[seedKey]` | `frontend/src/app/create/[seedKey]/page.tsx` | 角色创建 |

### 3.2 `/labs/finance` 组件树

```
LabDetailPage (labs/[labKey]/page.tsx)
├── Link « 实验平台
├── h1 实验室名称 + blurb
├── CivilizationSelector          ← listSeeds()
├── CivilizationDashboard         ← getCivilizationDashboard(seedKey), compact 模式
└── FinancePanel                  ← 仅当 ws.civilization_key === civKey 时渲染
    ├── InstitutionsPanel
    ├── Tab 切换栏（5 tabs）
    ├── 事件输入区（standalone 专用）
    ├── Tab 内容区（global/city/corporate/retail/market）
    ├── AuditTrailPanel
    ├── 统一推演控制区
    └── LabReportView（推演完成后）
```

**渲染条件（必须同时满足）**：

1. 用户已登录（`authLoading === false && user` 存在，否则全页「载入中…」）
2. `ready === true`（`meta.status === "ready"` **或** `labKey ∈ READY_LABS`）
3. 外层 `{ready && (...)}` 包裹（`page.tsx:129`）
4. `labKey === "finance"`
5. `ws !== null`
6. `ws.civilization_key === civKey`（防止切换文明时的竞态闪烁）
7. `FinancePanel` 的 `key={ws.civilization_key}` 在文明切换时强制 remount

**CivilizationDashboard** 额外要求：`civKey && ws?.civilization_key === civKey`（`page.tsx:118`）。

**初始文明**：`LabDetailPage` 中 `civKey` 默认 `"modern"`（`page.tsx:33`），首次 `openLab` 使用该值直至 `ws` 返回后同步。

**last_report 未注入 FinancePanel**：`LabDetailPage` 将 `w.last_report` 存入页面 state，但**未**作为 prop 传给 `FinancePanel`；且 finance 属于 `UNIFIED_SIM_LABS`，页面级 `LabReportView` 被跳过。因此**重新打开工作区后，须再次推演才能看到报告**（已知 gap，§15.1）。

### 3.3 全局 Layout

`frontend/src/app/layout.tsx` 包裹 `AuthProvider`（`lib/auth.tsx`），无其他全局 UI 状态。

---

## 4. UI 设计规范

### 4.1 视觉语言

| 元素 | 规范 |
|------|------|
| 背景 | `bg-stone-900/50`、`bg-stone-950/40` 等深色半透明 |
| 主强调色（金融） | cyan：`border-cyan-800/40`、`text-cyan-300`、`bg-cyan-500`（主按钮） |
| 事件输入区 | violet：`border-violet-800/30`、`text-violet-300` |
| 报告区 | emerald：`border-emerald-800/40`、`text-emerald-300` |
| 机构面板 | violet 系 |
| 审计链 | amber 高亮步号 |
| 标题字体 | `font-serif` |
| 正文/控件 | 默认 sans，`text-[10px]` ~ `text-[13px]` 为主 |

### 4.2 间距与容器

- FinancePanel 默认 `max-w-3xl`（非 compact 模式）
- Lab 页面整体 `max-w-4xl mx-auto`
- 区块统一 `rounded-xl` 或 `rounded-lg`，`p-3` ~ `p-4`
- Tab 按钮：`px-2.5 py-1 rounded text-[11px] border`

### 4.3 交互反馈

| 状态 | 表现 |
|------|------|
| 加载中 | `busy === true` 时按钮 `disabled:opacity-40` |
| 成功消息 | `text-emerald-300/90`，显示在面板底部 |
| 错误消息 | `text-rose-300` |
| 推演进度 | `SimulationProgress` 组件：阶段文案 + 百分比条（前端模拟，非后端 SSE） |
| 报告动画 | `reportAnimate=true` 时 LabReportView 分阶段 reveal（0→0.2→0.5→0.8→1） |

### 4.4 图表配色（内置）

| 用途 | 颜色 |
|------|------|
| 全局指数 Sparkline / FanChart | `#38bdf8` |
| 城市指数 | `#c084fc` |
| 企业股价 | `#a3e635` |
| 量化路径 | `#fbbf24` |
| LabReportView 多序列 | `#a78bfa`, `#38bdf8`, `#fbbf24` 循环 |
| 直方图柱 | `bg-violet-500/70` |
| 散点 | `#fbbf24` |
| 雷达填充 | `#38bdf8` opacity 0.25 |

---

## 5. 金融实验室页面布局

### 5.1 自上而下区块顺序

```
┌──────────────────────────────────────────────┐
│ ← 实验平台                                    │
│ 金融实验室（h1）                               │
│ blurb 描述                                    │
├──────────────────────────────────────────────┤
│ [绑定文明 ▼ select]                           │
├──────────────────────────────────────────────┤
│ CivilizationDashboard (compact)               │
│  - 时代标签、人口、指标、历史事件摘要            │
├──────────────────────────────────────────────┤
│ FinancePanel                                  │
│ ┌──────────────────────────────────────────┐ │
│ │ 金融验证实验室                            │ │
│ │ 情景沙盘推演 · 数值可复现 · ...           │ │
│ ├──────────────────────────────────────────┤ │
│ │ InstitutionsPanel（有数据时）             │ │
│ ├──────────────────────────────────────────┤ │
│ │ [全局走势][城市金融][企业评估][量化][市场] │ │
│ ├──────────────────────────────────────────┤ │
│ │ 事件输入区（violet 边框）                  │ │
│ ├──────────────────────────────────────────┤ │
│ │ ← 当前 Tab 内容 →                         │ │
│ ├──────────────────────────────────────────┤ │
│ │ AuditTrailPanel（有 audit 时）            │ │
│ ├──────────────────────────────────────────┤ │
│ │ 推演步数 | 跳过LLM | [开始推演]            │ │
│ │ SimulationProgress（推演中）              │ │
│ ├──────────────────────────────────────────┤ │
│ │ LabReportView（推演完成后）                │ │
│ └──────────────────────────────────────────┘ │
├──────────────────────────────────────────────┤
│ [刷新沙盘状态]                                 │
└──────────────────────────────────────────────┘
```

### 5.2 CivilizationSelector 行为

- 数据源：`GET /api/seeds` → `listSeeds()`
- 切换文明：调用 `openLab(labKey, newCivKey)`（**不是** `rebindLab`；后者 API 存在但前端未调用）
- **`openLab` 每次均执行 `rebind_civilization`**（`main.py:640-641`），即使 civilization 相同也会：
  - 清空 `timeline_events`、`last_report`
  - 重新 `_init_lab_state`（finance / market 引擎重置）
- 切换时：`setBusy(true)`，完成后更新 `ws`、`civKey`、`report`（report 会被清空）
- 自定义文明选项前缀：`★`

---

## 6. FinancePanel 组件规格

**文件**：`frontend/src/components/FinancePanel.tsx`

### 6.1 Props

```typescript
type Props = {
  /** Session 模式（legacy，当前未在 play 页挂载） */
  sid?: string;
  session?: Session | null;
  onUpdate?: (s: Session) => void;

  /** 实验平台模式（当前主路径） */
  labId?: string;
  civilizationKey?: string;
  finance?: FinanceSnap | null;
  financeLab?: any;
  timelineEvents?: TimelineEvent[];
  onLabUpdate?: (patch: LabPatch) => void;

  compact?: boolean;
};

type LabPatch = {
  finance?: FinanceSnap | null;
  finance_lab?: any;
  timeline_events?: TimelineEvent[];
  last_report?: LabReport | null;
};
```

**模式判定**：`standalone = Boolean(labId)`。standalone 为 true 时启用：事件输入、统一推演、LabReportView。

### 6.2 Tab 定义

| Tab ID | UI 标签 | 后端 `mode` | 默认选中 |
|--------|---------|-------------|---------|
| `global` | 全局走势 | `global` | ✅ 是 |
| `city` | 城市金融 | `city` | |
| `corporate` | 企业评估 | `corporate` | |
| `retail` | 量化交易 | `retail` | |
| `market` | 市场清算 | `market` | |

Tab 切换**仅改变 UI 与下次推演的 `mode` 参数**，不会自动触发 API 调用。

### 6.3 事件输入区（仅 standalone）

**显示条件**：`standalone && labId`

| 控件 | 类型 | 默认值 | 行为 |
|------|------|--------|------|
| 上传数据集 | file input | — | accept: `.csv,.xlsx,.xls,.md,.markdown,.txt,.zip` → `labWsUploadDataset` |
| 时间 | text input | `T+8` | 传给 manual events 的 `time` 字段 |
| 类型 | select | `political` | 见 [6.3.1 事件类型枚举](#631-事件类型枚举) |
| 标题 | text input | 空 | 必填才能点「添加」 |
| 强度 | number | `0.25` | step=0.05，约 -1.0 ~ 1.0 |
| 添加 | button | — | `labWsAddManualEvents` |
| LLM 结构化 | checkbox | ✅ checked | 控制 `use_llm_ner`（仅手动添加；**上传数据集**后端固定开启 NER，无 UI 开关） |

**已录入事件摘要**：显示 `timelineEvents.length` 及最近 4 条 `time_label + title`。

#### 6.3.1 事件类型枚举

| value | 中文标签 |
|-------|---------|
| `political` | 政治 |
| `policy` | 政策 |
| `rate` | 利率 |
| `price` | 物价 |
| `property` | 地产 |
| `war` | 战争 |
| `plague` | 瘟疫 |
| `earthquake` | 灾害 |
| `earnings` | 财报 |
| `product` | 产品 |
| `scandal` | 舆情 |
| `custom` | 自定义 |

### 6.4 各 Tab 内容与控件

#### 6.4.1 全局走势（global）

**说明文案**：「基于文明宏观背景与输入事件，推演全局指数、风险及政策调整时间点。」

**结果展示**（`globalResult` 存在时）：

| 元素 | 数据路径 |
|------|---------|
| 展望 Metric | `globalResult.narrative.outlook` |
| 期末指数 Metric | `globalResult.forecast[-1].index` |
| 图表 | `ForecastViz(result, valueKey="index", stroke="#38bdf8")` |
| 摘要 | `globalResult.narrative.summary` |
| 政策日历列表 | `globalResult.policy_calendar[]` → `{when, urgency, action, reason}` |
| 政策备注 | `globalResult.narrative.policy_notes[]` |
| 免责声明 | `globalResult.disclaimer` |

#### 6.4.2 城市金融（city）

**控件**：

| 控件 | 绑定 state | API 参数 |
|------|-----------|---------|
| 城市 select | `cityKey` | `city_key` |

城市列表来源：`financeLab.available_cities[]` → `{ key, name, description? }`

**结果 Metric**：

| 标签 | 字段 |
|------|------|
| 展望 | `cityResult.narrative.outlook` |
| 城市指数 | `forecast[-1].city_index` |
| 地产指数 | `forecast[-1].property_index` |
| 就业率 | `forecast[-1].employment * 100` + `%` |

图表：`ForecastViz(..., valueKey="city_index", stroke="#c084fc")`

#### 6.4.3 企业评估（corporate）

**控件**：

| 控件 | 绑定 | API 参数 |
|------|------|---------|
| 评估对象 select | `companyKey` | `company_key` |
| 自定义名称 | `company` | `company_name`（可选覆盖） |
| 行业 | `sector` | `sector`（可选覆盖） |

企业列表：`financeLab.available_companies[]`，按 `entity_type` 分组：
- `enterprise` 或无 type → optgroup「企业」
- `unit` → optgroup「单位」

**结果 Metric**：企业名、预期收益%、期末价；融资建议列表 `narrative.financing[]`

#### 6.4.4 量化交易（retail）

**控件**：

| 控件 | state | 值域 | API 参数 |
|------|-------|------|---------|
| 风险偏好 | `risk` | `conservative` / `balanced` / `aggressive` | `risk` |
| 期限偏好 | `retailHorizon` | `auto` / `short` / `long` | `retail_horizon` |
| 本金 | `capital` | number, min 1000 | `capital` |

**结果展示**：建议卡片、四 Metric、Sparkline（短/长路径）、comparison 表格。

**注意**：retail 模式**不注入** timeline 事件；AuditTrailPanel 在 retail 且无 audit 时不显示。

#### 6.4.5 市场清算（market）

**前置条件**：`finance` snapshot 存在。否则显示「请新建会话以初始化市场清算引擎。」

**Metric 行**：物价指数、时序通胀%、货币存量、基尼

**商品表**：`finance.goods[]` → 商品名、现价、相对基价%、库存

**市场清算参数**：

| 控件 | state | 约束 |
|------|-------|------|
| 快进时数 | `steps` | 1–168，默认 24 |
| 冲击类型 | `kind` | `demand` / `supply` / `price` |
| 商品 | `goodId` | `*` 或具体 `good_id` |
| 强度 | `magnitude` | 0.05–1.5，默认 0.4 |

**增量操作按钮**（standalone）：
- 「注入冲击」→ `labWsFinanceShock(labId, { kind, good_id, magnitude })`
- 「快进 N 步」→ `labWsAdvanceFinance(labId, steps)`

**统一推演**：market 模式下 `market_steps` 取自 `steps`（若 tab 为 market）。

### 6.5 统一推演控制区（仅 standalone）

| 控件 | state | 约束 | 说明 |
|------|-------|------|------|
| 推演步数 | `horizon` | 4–120，默认 24 | 传给 API `horizon` |
| 快速推演 | `skipLlm` | checkbox | API `skip_llm: true` |
| 开始推演 | — | `disabled=busy` | 调用 `labWsFinanceSimulate` |

**按钮文案**：`开始推演 · 生成完整报告（{tabModeLabel}）`

**进度模拟**（纯前端，650ms 间隔切换阶段）：

1. 读取文明背景与时代金融机构
2. 市场预热与微观清算
3. 宏观传导方程逐步迭代
4. Monte Carlo 置信区间估计
5. 生成图表、数值表与 PDF 报告

完成后：`setSimPct(100)`，1.8s 后清除进度条。

### 6.6 推演 API 请求体映射

调用 `labWsFinanceSimulate(labId, body)` 时，body 由当前 tab 决定：

```typescript
{
  mode: tab,                           // "global"|"city"|"corporate"|"retail"|"market"
  horizon: number,                     // 4-120
  city_key?: string,                   // tab==="city" 时
  company_key?: string,                // tab==="corporate" 时
  company_name?: string,               // 非空时覆盖
  sector?: string,                     // 非空时覆盖
  risk: "conservative"|"balanced"|"aggressive",
  retail_horizon: "auto"|"short"|"long",
  capital: number,
  market_steps?: number,               // tab==="market" 时 = steps
  skip_llm: boolean,
}
```

### 6.7 响应处理

#### `applyResponse(j)` — 仅处理部分字段

| 响应字段 | 前端动作 |
|---------|---------|
| `j.session` | `onUpdate(j.session)`（session 模式） |
| `j.finance` | `setLocalFinance` + `onLabUpdate({ finance })` |
| `j.finance_lab` | `onLabUpdate({ finance_lab })` |

**不在 `applyResponse` 内处理**：`j.report`、`j.pdf_base64`、`j.simulation`（见下）。

#### `runUnifiedSimulate()` — 报告与 PDF

| 响应字段 | 前端动作 |
|---------|---------|
| `j.simulation` | 按 tab 写入 `globalResult` / `cityResult` / `corpResult` / `retailResult` |
| `j.report` | `setReport` + `setReportAnimate(true)` + `onLabUpdate({ last_report })` |
| `j.pdf_base64` | `setPdfBase64` + `setPdfFilename`（默认 `"finance_report.pdf"`） |
| `j.finance_lab?.institutions` | `onLabUpdate({ finance_lab })` |
| `j.lab` | **当前未合并**到 `ws` 状态（后端返回完整 snapshot，前端忽略） |

**LabReportView 渲染条件**：`report && standalone`（`FinancePanel.tsx:869`），即必须有 `labId` 且本地 `report` 非 null。

**PDF 下载**：**不自动下载**；用户点击 LabReportView 内「下载 PDF 报告」按钮触发。

---

## 7. 子组件规格

### 7.1 InstitutionsPanel

**文件**：`frontend/src/components/InstitutionsPanel.tsx`  
**API 调用**：无（纯展示）

**Props**：`institutions: FinanceInstitution[]`

**数据来源优先级**（FinancePanel 内）：
```
sim?.institutions ?? labSnap?.institutions ?? []
```
其中 `sim = activeTabResult(tab, globalResult, cityResult, corpResult, retailResult, finance)`

**单卡片字段**：

| 字段 | 展示 |
|------|------|
| `name` | 主标题 |
| `era_label` | 副标题 |
| `institution_type` | 映射为中文（见 TYPE_LABEL） |
| `influence` | 影响力 % |
| `health` | 健康 % |
| `capacity` | 容量 % |
| `throughput` | 吞吐 |
| `last_delta` | Δ inf / Δ hlth |
| `description` | 描述段落 |
| `roles[]` | tag 列表 |

**institution_type 中文映射**：

| key | 标签 |
|-----|------|
| fiscal_regulator | 财政监管 |
| central_bank | 中央银行 |
| exchange | 交易所 |
| guild | 行会/商帮 |
| clearing | 清算 |
| credit | 信贷 |
| monopoly | 专卖 |

> **注意**：前端 `TYPE_LABEL` 另有 `regulator → 监管` 作为 **fallback**，但后端 institution 定义**从不** emit `regulator` 类型。实际后端 type 仅：`fiscal_regulator`, `central_bank`, `exchange`, `guild`, `clearing`, `credit`, `monopoly`。  
> UI 显示的中文标签来自 **前端映射**，可能与后端字段 `institution_type_label`（如 backend `guild` →「行会/公会」）措辞略有差异。

**卡片额外字段**（后端可能返回）：`key`, `assets_index`, `transmission`, `base_transmission`, `institution_type_label`。

### 7.2 AuditTrailPanel

**文件**：`frontend/src/components/AuditTrailPanel.tsx`  
**API 调用**：无

**Props**：

```typescript
{
  auditTrail?: AuditStep[];
  eventLog?: AuditStep[];
  methodology?: Record<string, unknown>;
  calibration?: Record<string, unknown>;
  compact?: boolean;
}
```

**显示条件**（FinancePanel 内）：
- 存在 `audit_trail` 或 `event_log` 或 `methodology`
- retail tab 且无 audit 时不显示

**交互**：点击步号行展开/折叠详情（方程、输入输出、长程融合校正、机构演化、事件通道）

**长程融合展示**：`fusion.corrections` 每项格式 `{param}: {markov} + {weight_longrun}×长程({longrun}) → {fused}`

### 7.3 LabReportView

**文件**：`frontend/src/components/LabReportView.tsx`

**Props**：

```typescript
{
  report: LabReport | null;
  animate?: boolean;        // 默认 false
  pdfBase64?: string | null;
  pdfFilename?: string;     // FinancePanel 传入，默认 "finance_report.pdf"
}
```

**区块顺序**：

1. 标题区 + PDF 下载按钮（仅 `pdfBase64` 存在时）
2. 终结性结论（`report.conclusion`）
3. 预测卡片网格（`report.predictions[]`）
4. 结果图表（支持 type: `fan` | `histogram` | `scatter` | `radar` | `line`）
5. 数值表格（`reveal > 0.4` 后显示）
6. 事件影响（`reveal > 0.6`）
7. 综合分析（`reveal > 0.8`，过滤 heading !== "终结性结论"）
8. disclaimer

**图表 type 与渲染组件**：

| type | 组件 |
|------|------|
| `fan` | FanChart（series 含 p10/p50/p90） |
| `histogram` | HistogramChart |
| `scatter` | ScatterChart |
| `radar` | RadarChart |
| 其他 | MiniChart（多 polyline） |

### 7.4 FanChart

**文件**：`frontend/src/components/charts/FanChart.tsx`

**Props**：`bands: { p10, p50, p90 }[]`, `history?: number[]`, 可选 width/height/stroke/fill

**图例**：p10–p90 区间、 p50 中位、历史虚线、期末区间数值

### 7.5 内联组件（FinancePanel 内）

| 组件 | 职责 |
|------|------|
| `Sparkline` | 单序列折线，values < 2 时显示「等待序列…」 |
| `ForecastViz` | 有 confidence_bands 时用 FanChart，否则 Sparkline |
| `SimulationProgress` | 推演进度条 |
| `Metric` | 标签 + 数值卡片 |

---

## 8. 前端状态与数据流

### 8.1 状态分层

| 层级 | 位置 | 内容 |
|------|------|------|
| 全局认证 | `AuthProvider` | user, token, login/logout |
| Lab 页面 | `LabDetailPage` useState | ws, civKey, report, busy, err |
| FinancePanel | 组件内 useState | tab, 各表单, 各 result, report, pdf, simPhase |
| 无 Redux/Zustand | — | — |

### 8.2 LabDetailPage 数据流

```
用户登录
  → openLab("finance", civKey) → setWs
  → FinancePanel 接收 ws.finance, ws.finance_lab, ws.timeline_events

用户切换文明
  → onCivChange → openLab → 新 ws → FinancePanel remount (key=civilization_key)

用户推演
  → FinancePanel.runUnifiedSimulate()
  → onLabUpdate(patch) → setWs(prev => ({...prev, ...patch}))
  → patch.last_report → setReport

用户刷新
  → getLabWorkspace(ws.id) → setWs
```

### 8.3 API 客户端

**文件**：`frontend/src/lib/api.ts`

- Base URL：空字符串（同源，Next.js rewrite 到后端）
- 认证：`authHeaders()` 从 localStorage 读 token
- 错误：`!r.ok` 时解析 `detail` / `error` / `message` 并 `throw new Error`

### 8.4 前端实际使用的 API（金融实验室）

| 函数 | HTTP | 调用方 |
|------|------|--------|
| `listSeeds` | GET /api/seeds | CivilizationSelector |
| `getCivilizationDashboard` | GET /api/seeds/{key}/dashboard | CivilizationDashboard |
| `listLabs` | GET /api/labs | LabDetailPage |
| `openLab` | POST /api/labs/{labKey}/open | LabDetailPage |
| `getLabWorkspace` | GET /api/labs/workspace/{id} | 刷新按钮 |
| `labWsFinanceSimulate` | POST .../finance/simulate | FinancePanel 主推演 |
| `labWsUploadDataset` | POST .../datasets/upload | FinancePanel |
| `labWsAddManualEvents` | POST .../events/manual | FinancePanel |
| `labWsFinanceShock` | POST .../finance/shock | FinancePanel market tab |
| `labWsAdvanceFinance` | POST .../finance/advance | FinancePanel market tab |

**已定义但 FinancePanel 未使用的 API**（legacy / 细粒度）：
`labWsGlobalForecast`, `labWsCityForecast`, `labWsCorporateForecast`, `labWsRetailRun`, 以及 session 版 `labGlobal*` 等。统一推演路径已取代单独 forecast 调用。

---

## 9. 用户操作流程

### 9.1 标准推演流程

```
1. 登录 → /labs/finance
2. （可选）切换「绑定文明」
3. （可选）上传数据集 或 手动添加事件
4. 选择 Tab（全局/城市/企业/量化/市场）
5. 配置 Tab 专属参数（城市、企业、风险偏好等）
6. 设置推演步数（4-120）
7. （可选）勾选「快速推演（跳过 LLM 润色）」
8. 点击「开始推演 · 生成完整报告」
9. 等待进度条完成
10. 查看 Tab 内即时结果 + LabReportView 完整报告
11. （可选）点击「下载 PDF 报告」
```

### 9.2 市场增量实验流程

```
1. Tab → 市场清算
2. 配置冲击类型 / 商品 / 强度
3. 「注入冲击」或「快进 N 步」（可多次）
4. 观察 Metric、Sparkline、商品表变化
5. 需要正式报告时 → 设置步数 → 「开始推演」
```

### 9.3 文明切换行为

- 调用 `openLab` → 后端 `rebind_civilization`（**总是**清空 timeline 与 last_report，见 §5.2）
- FinancePanel `useEffect` 依赖 `activeCivKey` 重置：`cityKey`, `companyKey`, 各 result, `report`
- **`timeline_events` 不会跨 open 保留**

---

## 10. TypeScript 类型契约

定义于 `frontend/src/lib/api.ts`，以下为金融相关核心类型。

### 10.1 LabWorkspace

```typescript
type LabWorkspace = {
  id: string;
  lab_key: string;
  civilization_key?: string;
  civilization_name?: string;
  genre: string;
  meta: LabMeta;
  finance: FinanceSnapshot | null;
  finance_lab: FinanceLabSnapshot;  // 见 10.2
  timeline_events?: TimelineEvent[];
  last_report?: LabReport | null;
  status: string;
};
```

### 10.2 FinanceLabSnapshot（后端 snapshot()）

```typescript
// 后端 finance_lab.snapshot() 结构
{
  seed: string;
  genre: string;
  civilization_key: string;
  available_cities: { key: string; name: string; description?: string }[];
  available_companies: {
    key: string; name: string; sector?: string; description?: string;
    entity_type?: "enterprise" | "unit"; entity_type_label?: string;
  }[];
  institutions: FinanceInstitution[];
  calibration: Record<string, unknown>;  // rho, kappa, beta, method 等
  global: { history; events; last_forecast };
  city: { city_key; city_name; history; events; last_forecast };
  corporate: { company: { key, name, sector, base_price }; history; events; last_forecast };
  retail: { capital; last_result };
}
```

### 10.3 TimelineEvent

```typescript
type TimelineEvent = {
  id?: string;
  time_label?: string;       // 如 "T+8"
  at_step: number;           // 解析后的步号
  title: string;
  description?: string;
  magnitude?: number;
  kind?: string;
  source?: string;
  channel_preview?: Record<string, number>;
  entities?: string[];
  rationale?: string;        // LLM NER 解释
};
```

### 10.4 LabReport

```typescript
type LabReport = {
  title: string;
  lab_key: string;
  civilization_key: string;
  civilization_name: string;
  horizon: number;
  dimensions: string[];
  mode?: string;
  mode_label?: string;
  conclusion?: string;
  charts: ChartSpec[];
  tables: { title: string; columns: string[]; rows: (string|number)[][] }[];
  event_impacts: { time: string; title: string; magnitude: number; effect: string }[];
  predictions: {
    dimension: string; horizon: number;
    from_value: number; to_value: number;
    change_pct: number; trend: string;  // "上行"|"下行"|其他
  }[];
  analysis: { heading: string; body: string }[];
  disclaimer: string;
  chart_analyses?: { chart_id: string; title: string; body: string }[];
  dashboard?: { era_label; population_explanation; current_state };
  simulation?: Record<string, unknown>;  // 嵌入完整 simulation
};
```

### 10.5 ChartSpec

```typescript
type ChartSpec = {
  id: string;
  title: string;
  type: "line" | "fan" | "histogram" | "scatter" | "radar" | string;
  x_key?: string;
  x_label?: string;
  y_label?: string;
  series?: { key: string; label: string; values: number[] }[];
  labels?: string[];
  bins?: { label: string; count: number; start?: number; end?: number }[];
  points?: { x: number; y: number; label?: string }[];
  axes?: { label: string; value: number; raw?: number }[];
  analysis?: string;
};
```

### 10.6 FinanceSnapshot（market）

```typescript
type FinanceSnapshot = {
  seed: string;
  tick: number;
  price_index: number;
  inflation: number;
  money_supply: number;
  velocity: number;
  gini: number;
  volume: number;
  goods: FinanceGood[];
  shocks: { id; kind; good_id; magnitude; remaining; note }[];
  history: { tick; price_index; inflation; money_supply; velocity; gini; volume; prices }[];
  engine?: string;
};
```

---

## 11. 后端 API 完整规格

所有 lab workspace API 前缀：`/api/labs/workspace/{lab_id}`  
认证：`Authorization: Bearer <token>`，且 `ws.user_id === user.id`，否则 **404** `lab workspace not found`。

### 11.1 打开工作区

```
POST /api/labs/finance/open
Content-Type: application/json
```

**Request**：

```json
{
  "civilization_key": "ancient"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| civilization_key | string | 否 | 默认 `"modern"` |
| genre | string | 否 | legacy 兼容字段，默认 `"modern"`；通常可省略，由 civilization 推断 |

**Response**：`LabWorkspace` 完整快照（见 §10.1、`lab_snapshot()`）

**副作用**：每次 open 调用 `rebind_civilization`，**清空** `timeline_events` 与 `last_report` 并重建引擎。

**错误**：
- 401 未认证
- 404 `lab not found` 或 `lab or civilization not found`

---

### 11.2 统一推演（主路径）

```
POST /api/labs/workspace/{lab_id}/finance/simulate
```

**Request body**（`FinanceSimulateReq`）：

```json
{
  "mode": "global",
  "horizon": 24,
  "city_key": null,
  "company_key": null,
  "company_name": null,
  "sector": null,
  "risk": "balanced",
  "retail_horizon": "auto",
  "capital": 100000,
  "market_steps": null,
  "skip_llm": false
}
```

| 字段 | 类型 | 默认 | 约束 | 说明 |
|------|------|------|------|------|
| mode | string | `"global"` | 见 mode 枚举 | 非法值回退 global |
| horizon | int | 24 | 4–120（后端 clamp） | 推演步数 |
| city_key | string? | null | city 模式 | 城市 key |
| company_key | string? | null | corporate 模式 | 企业 key |
| company_name | string? | null | max 40 字符 | 覆盖企业名 |
| sector | string? | null | max 24 字符 | 覆盖行业 |
| risk | string | `"balanced"` | conservative/balanced/aggressive | retail 模式 |
| retail_horizon | string | `"auto"` | auto/short/long | retail 模式 |
| capital | float? | null | — | retail 本金 |
| market_steps | int? | null | 1–168 | market 模式步数；默认用 horizon |
| skip_llm | bool | false | — | true 时不调用 LLM 润色 |

**mode 枚举**：

| mode | 中文 | 引擎 |
|------|------|------|
| `global` | 全局走势 | structured_macro_v2 + Monte Carlo |
| `city` | 城市金融 | structured_macro_v2（城市映射） |
| `corporate` | 企业评估 | macro β + 特质冲击 |
| `retail` | 量化交易 | GBM 合成路径 |
| `market` | 市场清算 | agent_based_market_v1 |

**Response 200**：

```json
{
  "report": { /* LabReport，见 §13 */ },
  "simulation": { /* 见 §12 */ },
  "mode": "global",
  "pdf_base64": "<base64>",
  "pdf_filename": "ancient_global_report.pdf",
  "finance": { /* FinanceSnapshot，market 模式有值 */ },
  "finance_lab": { /* FinanceLabSnapshot */ },
  "lab": { /* LabWorkspace 快照 */ }
}
```

**错误**：
- 404 workspace 不存在或非 owner
- 400 `not a finance workspace`（lab_key ≠ finance）
- 400 `finance lab not initialized` / `market engine not initialized` / `unknown finance mode`

---

### 11.3 手动添加事件

```
POST /api/labs/workspace/{lab_id}/events/manual
```

**Request**：

```json
{
  "use_llm_ner": true,
  "events": [
    {
      "time": "T+8",
      "title": "意外加息",
      "magnitude": -0.3,
      "kind": "rate",
      "description": ""
    }
  ]
}
```

**Response**：

```json
{
  "added": 1,
  "timeline_events": [ /* 完整列表 ws.timeline_events，非仅新增 */ ],
  "lab": { /* LabWorkspace 快照 */ }
}
```

**时间解析**：`T+8` → `at_step=8`；无法解析时使用顺序默认步号。

**LLM NER**：由请求体 `use_llm_ner` 控制（与手动事件表单 checkbox 对应）。

---

### 11.4 上传数据集

```
POST /api/labs/workspace/{lab_id}/datasets/upload
Content-Type: multipart/form-data
```

| 字段 | 说明 |
|------|------|
| file | 单文件，max **8MB** |

**支持格式**：`.csv`, `.xlsx`, `.xls`, `.md`, `.markdown`, `.txt`, `.zip`（解压后递归解析）

**LLM NER**：后端 `lab_upload_dataset` 默认 `use_llm_ner=True`，**前端无开关**（与手动事件的 checkbox 不同）。

**Response**：

```json
{
  "imported": 12,
  "events": [ /* 本次导入事件 */ ],
  "lab": { /* LabWorkspace */ }
}
```

---

### 11.5 市场增量 API

#### 注入冲击

```
POST /api/labs/workspace/{lab_id}/finance/shock
```

```json
{
  "kind": "demand",
  "good_id": "*",
  "magnitude": 0.4,
  "note": ""
}
```

| 字段 | 默认 | 说明 |
|------|------|------|
| kind | `"demand"` | demand / supply / price |
| good_id | `"*"` | 商品 id 或全部 |
| magnitude | `0.35` | 冲击强度 |
| duration | `12` | 持续 tick 数（前端未暴露控件，使用默认） |
| note | `""` | 备注 |

**Response**：`{ shock, finance, finance_lab?, lab }`；session 模式下含 `session`

#### 市场快进

```
POST /api/labs/workspace/{lab_id}/finance/advance
```

```json
{ "steps": 24 }
```

**steps 约束**：1–168

**Response**：`{ steps, events, finance, finance_lab, lab }`  
（`events` 为最近 20 条市场事件摘要）

---

### 11.6 获取 / 刷新工作区

```
GET /api/labs/workspace/{lab_id}
```

**Response**：`LabWorkspace` 快照（`timeline_events` 仅最近 50 条）

---

### 11.7 细粒度 forecast API（Legacy，前端未使用）

以下接口仍可用，但 **FinancePanel 已统一走 `/finance/simulate`**：

| 方法 | 路径 |
|------|------|
| POST | `/api/labs/workspace/{id}/finance/lab/global/forecast` |
| POST | `/api/labs/workspace/{id}/finance/lab/global/event` |
| POST | `/api/labs/workspace/{id}/finance/lab/city/forecast` |
| POST | `/api/labs/workspace/{id}/finance/lab/city/event` |
| POST | `/api/labs/workspace/{id}/finance/lab/corporate/forecast` |
| POST | `/api/labs/workspace/{id}/finance/lab/corporate/event` |
| POST | `/api/labs/workspace/{id}/finance/lab/retail/run` |

Session 版路径前缀：`/api/sessions/{sid}/finance/lab/...`

---

### 11.8 事件注入与转换规则

#### 11.8.1 Desk 注入（`_apply_timeline_to_finance`）

| 当前 mode | timeline 注入目标 |
|-----------|------------------|
| global | 仅 `global_desk` |
| city | 仅 `city_desk` |
| corporate | 仅 `corporate_desk`（见 kind 重映射） |
| market | `global_desk` + `city_desk` + `corporate_desk` + ABM shock |
| retail | **不注入各 desk** |

**重要**：事件在点击「开始推演」时注入；手动添加/上传**不会**即时改变已展示曲线。

#### 11.8.2 retail 模式与 timeline

- `_apply_timeline_to_finance` 对 retail **无分支**（不 insert_event 到 desk）
- 但 `lab_finance_simulate` 调用 `retail.run(..., events=ws.timeline_events)`  
- timeline 用于 **`calibrate_vol()`** → 内部 `simulate_macro_path` 估计波动率，**不**改变 retail 主路径数值的逐步 desk 状态

#### 11.8.3 corporate kind 重映射

注入 corporate_desk 时（`workspace.py:526-527`）：

| 原始 kind | corporate desk kind |
|-----------|---------------------|
| `earnings`, `product`, `scandal`, `policy` | 保持原值 |
| 其他全部 | `"custom"` |

#### 11.8.4 market 模式：timeline → ABM shock

函数 `_shock_kind_from_event(kind, magnitude)`（`workspace.py:540-547`）：

| 条件 | ABM shock kind |
|------|----------------|
| kind ∈ `war`, `plague`, `earthquake` | `demand` |
| kind ∈ `rate`, `price`, `property` | `price` |
| magnitude < 0 | `demand` |
| 其他 | `supply` |

每个 timeline 事件转为 `finance.schedule_shock(kind, good_id="*", magnitude=abs(mag), duration=max(3, int(abs(mag)*20)), note=title)`。

#### 11.8.5 UI kind → 宏观通道（引擎内部）

UI 下拉 **kind**（§6.3.1）传入 desk；引擎 `finance_sim_core.py` 的 `TRANSMISSION` 矩阵将其映射到内部通道，例如：

| UI kind | 主要影响通道（概念） |
|---------|---------------------|
| political, war | output_gap, risk_premium |
| policy, rate | policy_rate, liquidity |
| price, property | inflation, index |
| earnings, product | index（corporate 路径） |
| plague, earthquake | supply_shock, output_gap |
| scandal | risk_premium |
| custom | 默认混合通道 |

精确系数见 `backend/app/layer2_civilization/finance_sim_core.py` → `TRANSMISSION`。

---

## 12. 推演引擎与 simulation 对象

### 12.1 递推方法论

**Markov 逐步递推**：第 N 步状态基于第 N−1 步 + 当期事件冲击 + 噪声。

**长程融合（v2）**：在 Markov 输出基础上，用历史序列估计 AR(1)/EWMA/对数趋势，按 `genre × mode` 策略表加权融合。

配置文件：`backend/app/layer2_civilization/finance_fusion_config.py`

**9 文明（genre）**：
`ancient`, `wuxia`, `modern`, `scifi`, `mystery`, `enterprise`, `securities`, `military`, `xuanhuan`

**4 宏观模式（fusion_mode）**：
`global`, `city`, `corporate`, `retail`

**retail 模式**：融合 **disabled**，仅用 macro ensemble 校准 GBM 波动率。

**统一推演锁内流程**（`lab_finance_simulate`）：

1. `prepare_simulation(city_key, company_key)` — 重置各 desk、机构至基线（`finance_lab.py:1077-1090`）
2. `_apply_timeline_to_finance(mode)`
3. market warmup（global/city/corporate/retail，最多 min(24, horizon) 步）→ macro closure
4. desk.forecast / retail.run / market loop
5. `build_report` → `enrich_finance_report` → PDF

### 12.2 simulation 对象公共字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `engine` | string | 如 `structured_macro_v2`, `agent_based_market_v1` |
| `methodology` | object | paradigm, references, disclaimer |
| `history` | array | 历史步序列 |
| `forecast` | array | 预测步序列（retail 可能无） |
| `confidence_bands` | array | `{ step, p10, p50, p90 }` Monte Carlo |
| `audit_trail` | array | 逐步方程、输入输出、融合校正 |
| `event_log` | array | 事件→通道映射 |
| `fusion_strategy` | object | 当前 genre×mode 策略快照 |
| `fusion_log` | array | 逐步融合日志 |
| `longrun_fusion` | object | 长程估计摘要 |
| `institutions` | array | 推演结束时机构状态 |
| `calibration` | object | ρ, κ, β 等 |
| `narrative` | object | outlook, summary, policy_notes, financing 等 |
| `disclaimer` | string | 模式免责声明 |

### 12.3 各 mode 的 forecast 点结构

**global** 每点：

```typescript
{ step, label?, index, growth, risk, inflation?, output_gap?, policy_rate?, liquidity? }
```

**city** 每点：

```typescript
{ step, city_index, property_index, employment, liquidity, ... }
```

**corporate** 每点：

```typescript
{ step, price, ... }
```

**retail** 返回结构不同：

```typescript
{
  recommendation: { horizon, horizon_label, rationale, expected_return_pct, expected_end_value, max_drawdown_pct, vol_pct },
  paths: { short: number[], long: number[] },
  comparison: Record<string, { label, short_return_pct, long_return_pct, short_mdd_pct, long_mdd_pct }>,
  disclaimer: string
}
```

**market** 返回 `FinanceSnapshot` 扩展 + `institution_evolution`, `audit_trail`

### 12.4 LLM 参与点

| 环节 | skip_llm=false | skip_llm=true |
|------|----------------|---------------|
| desk.forecast narrative | ✅ Ollama 润色 | 规则模板文案 |
| 事件 manual NER | 由 `use_llm_ner` 单独控制 | 结构化规则 |
| 数值计算 | ❌ 不参与 | ❌ 不参与 |

---

## 13. 报告（LabReport）结构

构建链路：
1. `build_report()` — 基础图表、predictions、event_impacts
2. `analysis_from_simulation()` — 模式解读段落
3. `enrich_finance_report()` — 逐步数值表、多类图表、图释、**终结性结论**

### 13.1 enrich 追加的图表

| id | type | 条件 |
|----|------|------|
| `curve_{dim}` | line | 各维度时序 ≥2 点 |
| `hist_returns` | histogram | 指数收益率分布 |
| `scatter_risk_index` | scatter | 风险-指数散点 |
| `radar_terminal` | radar | 期末多维 ≥3 轴 |
| 置信区间 | fan | simulation.confidence_bands 存在 |

### 13.2 逐步数值表

插入 `tables[0]`，列随 mode 变化（由 `_mode_dim_map` 决定）。

### 13.3 PDF

- 生成：`backend/app/labs/report_pdf.py :: build_pdf_bytes(report)`
- 传输：Response 中 `pdf_base64` + `pdf_filename`
- 前端：**手动**点击下载，文件名默认 `{civilization_key}_{mode}_report.pdf`

---

## 14. 错误处理与边界条件

### 14.1 HTTP 错误码

| 码 | 场景 |
|----|------|
| 401 | 未登录 / token 无效 |
| 404 | lab_id 不存在或非当前用户 |
| 400 | 参数非法、引擎未初始化、文件过大 |

前端统一：`apiFetch` 抛 `Error(message)`，FinancePanel `wrap()` 捕获显示为 `err` 状态。

### 14.2 前端边界

| 场景 | 行为 |
|------|------|
| 文明切换竞态 | `latestCivRef` 丢弃过期 openLab 响应 |
| market 无 finance | 显示提示文案，不显示商品表 |
| institutions 空数组 | InstitutionsPanel 不渲染 |
| report 为 null | LabReportView 不渲染 |
| pdfBase64 为 null | 隐藏 PDF 下载按钮 |
| busy 中 | 所有操作按钮 disabled |

### 14.3 后端边界

| 场景 | 行为 |
|------|------|
| horizon 超出范围 | clamp 到 [4, 120] |
| market_steps 超出 | clamp 到 [1, 168] |
| 非法 mode | 回退 `global` |
| 工作区锁 | `async with ws.lock` 防止并发推演 |

---

## 15. 已知限制与废弃路径

### 15.1 已知限制

| 项 | 说明 |
|----|------|
| 工作区持久化 | 内存存储，**服务重启丢失** |
| 预测精度 | 启发式系数，非真实宏观校准 |
| magnitude 语义 | 模型内部 shock 权重，≠ 百分比涨跌幅 |
| 进度条 | 前端模拟，**不反映**后端真实进度 |
| rebindLab | API 存在，前端**未使用**（`openLab` 内部仍调 `rebind_civilization`） |
| market 无 finance 文案 | Tab 显示「请新建会话以初始化…」为 legacy session 措辞；实验平台 open 后通常已有 `finance` |
| getFinance | API 存在，前端**未使用** |
| last_report 未 hydrate | 重开 workspace 后不显示旧报告（§3.2） |
| simulate 响应 `lab` 未合并 | 前端忽略完整 workspace 快照 |
| openLab 清空事件 | 每次 open/rebind 清空 timeline 与 report（§5.2） |
| 实验平台无 3D | 金融沙盘与 World3D 无联动，见 [3D 文档 §10](./3d-world-and-characters.md#10-与实验平台的关系) |

### 15.2 故意移除/废弃

| 项 | 状态 |
|----|------|
| `/play/[sid]` 金融实验室入口 | **已移除** |
| PDF 自动下载 | **已改为手动** |
| 细粒度 forecast 按钮 | UI **已移除**，统一推演取代 |
| FinancePanel session 模式 | 组件仍支持 `sid`+ shock/advance（`FinancePanel.tsx:793-814`），Play 页**未挂载** |

### 15.3 后续 UI 优化建议入口

本文档 §6 FinancePanel 为组件改造基准。常见优化方向：

- 推演进度改 SSE/WebSocket 真实进度
- Tab 间联动对比视图
- 报告区与 Tab 预览的布局重构
- 移动端响应式（当前 sm: 断点部分适配）
- 启用 `rebindLab` 避免切换文明时重建工作区

---

## 16. 源码索引

### 16.1 前端

| 文件 | 职责 |
|------|------|
| `frontend/src/app/labs/[labKey]/page.tsx` | 实验室页面容器 |
| `frontend/src/components/FinancePanel.tsx` | 金融主面板 |
| `frontend/src/components/LabReportView.tsx` | 报告渲染 |
| `frontend/src/components/InstitutionsPanel.tsx` | 机构卡片 |
| `frontend/src/components/AuditTrailPanel.tsx` | 审计链 |
| `frontend/src/components/charts/FanChart.tsx` | 置信区间图 |
| `frontend/src/components/CivilizationSelector.tsx` | 文明选择 |
| `frontend/src/components/CivilizationDashboard.tsx` | 文明仪表盘 |
| `frontend/src/lib/api.ts` | API 客户端与类型 |
| `frontend/src/lib/auth.tsx` | 认证上下文 |
| [3D 世界与人物](./3d-world-and-characters.md) | World3D、地图、角色（实验平台不用） |
| [Play 会话](./play-session-ui-api.md) | 叙事游戏 UI/API |

### 16.2 后端

| 文件 | 职责 |
|------|------|
| `backend/app/main.py` | HTTP 路由、Pydantic 模型 |
| `backend/app/labs/workspace.py` | LabWorkspace、`lab_finance_simulate` |
| `backend/app/labs/report.py` | 报告构建与 enrich |
| `backend/app/labs/report_pdf.py` | PDF 生成 |
| `backend/app/labs/report_charts.py` | PDF 内 matplotlib 图表 |
| `backend/app/labs/datasets.py` | 数据集解析 |
| `backend/app/labs/event_ner.py` | LLM 事件结构化 |
| `backend/app/layer2_civilization/finance_lab.py` | Global/City/Corporate/Retail desk |
| `backend/app/layer2_civilization/finance_sim_core.py` | structured_macro_v2 |
| `backend/app/layer2_civilization/finance_longrun.py` | 长程估计与融合 |
| `backend/app/layer2_civilization/finance_fusion_config.py` | 9×4 策略表 |
| `backend/app/layer2_civilization/finance_institutions.py` | 时代机构定义 |
| `backend/app/layer2_civilization/finance.py` | MarketState ABM |

### 16.3 测试与验证脚本

| 文件 | 用途 |
|------|------|
| `backend/tests/test_finance_fusion_config.py` | 融合策略单测 |
| `backend/tests/test_finance_lab_integration.py` | 集成推演 |
| `backend/tests/test_report_enrichment.py` | 报告 enrich |
| `scripts/e2e_finance_lab_check.py` | E2E 冒烟 |
| `scripts/verify_all_civilizations.py` | 9 文明验证 |

---

## 附录 A：文明 seed_key 与 genre 对照

前端 `listSeeds()` 返回的每个 seed 含 `{ key, name, genre, premise }`。  
`openLab` 使用 `civilization_key = seed.key`；后端据此加载 genre 专属模板、机构、商品目录。

具体 seed 列表以运行时 `GET /api/seeds` 为准（含用户自定义文明，标记 `is_custom: true`）。

---

## 附录 B：HTTP 错误响应格式

FastAPI 默认：

```json
{ "detail": "错误描述字符串" }
```

或验证错误：

```json
{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }
```

前端 `apiFetch` 优先取 `detail` → `error` → `message`。

---

*文档维护：UI 或 API 变更时，请同步更新本文档对应章节，并在 PR 描述中注明「已更新 docs/finance-lab-ui-api.md」。*

# CivilSimulator — 全站 UI 设计与前后端接口完整规格

> **文档版本**：2026-08-31  
> **定位**：本文档为 **全站唯一完整基准**，覆盖当前所有 UI 页面、共享组件、前后端 API 契约。  
> **专题深读**：[金融实验室](./finance-lab-ui-api.md) · [Play 会话](./play-session-ui-api.md) · [3D 世界与人物](./3d-world-and-characters.md)

---

## 目录

- [A. 总览](#a-总览)
- [B. 全局 UI 设计规范](#b-全局-ui-设计规范)
- [C. 路由与页面规格（9 页）](#c-路由与页面规格9-页)
- [D. 共享组件规格](#d-共享组件规格)
- [E. 前端 API 客户端映射表](#e-前端-api-客户端映射表)
- [F. 后端 API 完整清单](#f-后端-api-完整清单)
- [G. 核心数据类型](#g-核心数据类型)
- [H. WebSocket](#h-websocket)
- [I. 静态资产](#i-静态资产)
- [J. 源码索引](#j-源码索引)

---

## A. 总览

### A.1 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js App Router、React、TypeScript、Tailwind CSS |
| 3D | Three.js + `@react-three/fiber` + `@react-three/drei` |
| 后端 | FastAPI（`backend/app/main.py`） |
| 认证 | Bearer Token → `localStorage.civsim_token` |
| 状态 | `AuthProvider` 全局 + 页面级 `useState`（无 Redux） |

### A.2 产品双模式

| 模式 | 入口 | 3D | 认证 |
|------|------|-----|------|
| **叙事模拟器** | `/` → `/create/[seed]` → `/play/[sid]` | ✅ World3D | 创建会话需登录 |
| **实验平台** | `/` 或 `/labs` → `/labs/[labKey]` | ❌ | 全部需登录 |

### A.3 全部路由一览

| # | 路由 | 文件 | 需登录 | 3D |
|---|------|------|--------|-----|
| 1 | `/` | `app/page.tsx` | ✅ | ❌ |
| 2 | `/login` | `app/login/page.tsx` | ❌（已登录跳转 `/`） | ❌ |
| 3 | `/create/[seedKey]` | `app/create/[seedKey]/page.tsx` | ✅ | 预览 |
| 4 | `/play/[sid]` | `app/play/[sid]/page.tsx` | ❌ | ✅ |
| 5 | `/civilizations/new` | `app/civilizations/new/page.tsx` | ✅ | ❌ |
| 6 | `/labs` | `app/labs/page.tsx` | ✅ | ❌ |
| 7 | `/labs/[labKey]` | `app/labs/[labKey]/page.tsx` | ✅ | ❌ |
| 8 | `/dev/maps` | `app/dev/maps/page.tsx` | ❌ | ✅ |
| 9 | `/dev/figures` | `app/dev/figures/page.tsx` | ❌ | 预览 |

### A.4 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│ AuthProvider (lib/auth.tsx)                                       │
│   token → localStorage.civsim_token                               │
├──────────────────────────────────────────────────────────────────┤
│ 叙事流          │ 实验平台流           │ 开发预览                │
│ / → /create     │ /labs → /labs/[key] │ /dev/maps, /dev/figures │
│ → /play/[sid]   │ FinancePanel 等      │                         │
└────────┬────────┴──────────┬──────────┴─────────────────────────┘
         │ fetch /api/*      │
         ▼                   ▼
   backend/app/main.py  (FastAPI)
```

---

## B. 全局 UI 设计规范

### B.1 色彩语义

| 语义 | Tailwind 典型类 | 使用场景 |
|------|----------------|---------|
| 背景 | `bg-stone-950`, `bg-stone-900/50` | 页面/卡片底 |
| 叙事/文明 | `amber-400`, `amber-500` | 首页文明卡、登录按钮、创建页 |
| 实验平台 | `cyan-400`, `cyan-500` | 实验室卡片、金融面板 |
| 事件输入 | `violet-300`, `violet-800/30` | 各 Lab 事件区 |
| 报告 | `emerald-300`, `emerald-800/40` | LabReportView |
| 错误 | `rose-300`, `rose-400` | err 文案 |
| 成功 | `emerald-300/90` | msg 文案 |

### B.2 字体与字号

| 元素 | 规范 |
|------|------|
| 大标题 | `font-serif text-3xl~4xl tracking-wider` |
| 区块标题 | `font-serif text-lg~2xl` |
| 标签 | `text-[10px] uppercase tracking-widest opacity-50~70` |
| 正文/控件 | `text-[11px]` ~ `text-sm` |
| Metric 数值 | `font-serif text-sm` |

### B.3 布局惯例

- 内容区最大宽度：`max-w-6xl`（首页）/ `max-w-4xl`（Lab）/ `max-w-3xl`（FinancePanel）
- 卡片：`rounded-xl border border-stone-700/800 p-3~4`
- 按钮 disabled：`disabled:opacity-40`
- 栅格：`sm:grid-cols-2 lg:grid-cols-3`

### B.4 认证与错误

- Token：`Authorization: Bearer {user_id}:{exp}:{hmac}`，TTL 30 天
- 前端 `apiFetch`（`lib/api.ts`）失败时解析 `detail` / `error` / `message` → `throw Error`
- 需登录页：`useEffect` 检测 `!user` → `router.replace("/login")`

---

## C. 路由与页面规格（9 页）

---

### C.1 首页 `/`

**文件**：`frontend/src/app/page.tsx`  
**认证**：必须登录，否则 → `/login`

#### 布局结构

```
Header: CivilSimulator + 用户名 + [退出登录]
Section 1: 实验平台
  - 标题 + 描述 + Link「进入全部实验室 →」
  - Grid: lab 卡片 (listLabs)
Section 2: 文明模拟器
  - Grid: [自定义文明 Link] + seed 卡片 (listSeeds)
Footer
```

#### UI 控件

| 控件 | 行为 | API |
|------|------|-----|
| 退出登录 | `logout()` | — |
| 实验室卡片 | `Link → /labs/{key}` | `GET /api/labs` |
| 自定义文明 | `Link → /civilizations/new` | — |
| 文明卡片 | `router.push(/create/{key})` | `GET /api/seeds` |
| 文明缩略图 | `img /maps/{seedKey}.png` | 静态资产 |

#### Lab 卡片状态

- `status === "ready"` → 标签「可用」cyan 边框
- 否则 → 「建设中」stone 边框
- `listLabs` 失败时使用 `FALLBACK_LABS` 常量

---

### C.2 登录/注册 `/login`

**文件**：`frontend/src/app/login/page.tsx`

#### UI 控件

| 控件 | 类型 | 约束 | API |
|------|------|------|-----|
| 模式切换 | login / register | — | — |
| 显示名 | input | 仅 register，可选 | — |
| 用户名 | input | minLength 3 | — |
| 密码 | password | minLength 6 | — |
| 提交 | button | disabled=loading | `POST /api/auth/login` 或 `register` |

已登录用户自动 `router.replace("/")`。

---

### C.3 角色创建 `/create/[seedKey]`

**文件**：`frontend/src/app/create/[seedKey]/page.tsx`  
**认证**：必须

#### 布局

```
← 返回文明选择
地图 banner (/maps/{seedKey}.png)
CivilizationDashboard (compact)
CharacterPicker
```

#### 流程

```
listSeeds + getPlayerCatalog(seedKey)
  → CharacterPicker 选 category / variant / skin (RoleSkinId)
  → createSession({ seed_key, category_key, variant_key, skin })
  → sessionStorage.sess_{id} = session
  → router.push(/play/{id})
```

#### API

| 函数 | 端点 |
|------|------|
| `listSeeds` | `GET /api/seeds` |
| `getPlayerCatalog` | `GET /api/seeds/{seedKey}/characters` |
| `createSession` | `POST /api/sessions` |
| `getCivilizationDashboard` | `GET /api/seeds/{seedKey}/dashboard`（CivilizationDashboard 内） |

---

### C.4 叙事游戏 `/play/[sid]`

**文件**：`frontend/src/app/play/[sid]/page.tsx`  
**深读**：[play-session-ui-api.md](./play-session-ui-api.md)

#### 布局（lg 双栏）

| 左栏 | 右栏 |
|------|------|
| World3D (520px) | WorldAtlas (520px) |
| ChoicePanel + 输入 | Recent Events (最近 6 页) |
| SkillPanel | |
| NpcPanel | |
| TaskPanel | |
| InjectPanel | |
| StatBars | |

#### Header 控件

| 按钮 | API / 行为 |
|------|-----------|
| 离线 / 苏醒 / 收回控制 | `sleepSession` / `wakeSession` |
| 朗读 Toggle | `useTTS`（浏览器 Speech Synthesis） |
| 音效 Toggle | `usePageTurnSound` |
| ☰ 关系 | 打开 WorldDrawer |
| 退出 | sleep + `router.push("/")` |

#### 后台机制

| 机制 | 间隔 | API |
|------|------|-----|
| 会话轮询 | 4s | `GET /api/sessions/{sid}`（直接 fetch） |
| Heartbeat | 12s | `POST .../heartbeat` |
| Tab 隐藏 60s | 一次 | `POST .../sleep` reason=tab_hidden |
| pagehide | sendBeacon | `POST .../sleep` reason=unload |

#### 组件 → API 映射

| 组件 | API |
|------|-----|
| ChoicePanel / 输入框 | `stepSession` |
| SkillPanel | `useSkill` |
| NpcPanel → NpcChat | `talkToNpc` |
| TaskPanel | `createSelfTask`, `completeTask` |
| InjectPanel | `injectEvent`, `injectCharacter`, `skipToTick` |
| WorldDrawer | `getCivilizationDashboard` |

**注意**：Play 页 **无** FinancePanel；session finance API 存在但 UI 未挂载。

---

### C.5 自定义文明 `/civilizations/new`

**文件**：`frontend/src/app/civilizations/new/page.tsx`  
**认证**：必须

#### 表单区块

| 区块 | 字段 | 类型 |
|------|------|------|
| 基本信息 | name, government_form, current_stage, operating_logic* | text/textarea |
| 阶层比例 | class_structure | 4 滑块 (ruling/middle/labor/marginal) |
| 年龄比例 | age_structure | 5 滑块 (child/youth/adult/middle_aged/elder) |
| 可操作职业 | professions[] | name, description, playable checkbox |
| 可选角色 | roles[] | name, profession, persona |
| 历史事件 | historical_events[] | era, title, description |

提交 → `createCustomCivilization` → `router.push(/create/{civilization.key})`

#### API

`POST /api/civilizations/custom`（见 [F.4](#f4-文明与种子)）

---

### C.6 实验室索引 `/labs`

**文件**：`frontend/src/app/labs/page.tsx`  
**认证**：必须

- Grid 卡片 → `/labs/{lab.key}`
- 数据源：`GET /api/labs`
- 卡片显示 name、blurb、status（可用/建设中）

---

### C.7 实验室详情 `/labs/[labKey]`

**文件**：`frontend/src/app/labs/[labKey]/page.tsx`  
**认证**：必须

#### 公共结构（所有 lab）

```
← 实验平台
h1 实验室名 + blurb
CivilizationSelector (listSeeds → openLab)
CivilizationDashboard (compact, seedKey=civKey)
[lab 专属 Panel]
[刷新沙盘状态] → getLabWorkspace
```

#### READY_LABS 与 Panel 映射

| labKey | Panel 组件 | 统一推演+PDF | 事件输入 |
|--------|-----------|-------------|---------|
| `finance` | FinancePanel | ✅ labWsFinanceSimulate | ✅ 内置 |
| `policy` | PolicyPanel | ✅ labWsPolicySimulate | ✅ EventBar |
| `weather` | WeatherPanel | ✅ labWsWeatherSimulate | ✅ 简化 |
| `environment` | EnvironmentPanel | ✅ labWsEnvironmentSimulate | ❌ |
| `military` | MilitaryPanel | ✅ labWsMilitarySimulate | ✅ |
| `population` | PopulationPanel | ✅ labWsPopulationSimulate | ✅ |
| `opinion` | OpinionPanel | ❌（无 PDF） | ❌ |

#### UNIFIED_SIM_LABS

`finance, military, policy, weather, environment, population` — 这些 lab 的 Panel **内置** LabReportView；页面级不再重复渲染。

`opinion` 不在此集合；无统一 PDF 报告 UI。

#### 文明切换

- `openLab(labKey, civKey)` — **非** `rebindLab`
- 每次 open 后端 `rebind_civilization`：清空 timeline、last_report，重建引擎
- `FinancePanel` 等以 `key={ws.civilization_key}` remount

#### 渲染条件

1. `user` 已登录
2. `ready`（meta.status=ready 或 labKey∈READY_LABS）
3. `ws.civilization_key === civKey`

---

#### C.7.1 FinancePanel

**深读**：[finance-lab-ui-api.md](./finance-lab-ui-api.md)

5 Tab：global / city / corporate / retail / market  
主 API：`POST .../finance/simulate`

---

#### C.7.2 PolicyPanel

**文件**：`components/PolicyPanel.tsx`  
**边框色**：amber

| 控件 | 默认 | API 参数 |
|------|------|---------|
| 主政部门 | agencies[0] | `agency_key` |
| 政令工具 | instruments[0] | `instrument_key` |
| 推演周期 | 24 (4–120) | `steps` |
| 开始推演 | — | `labWsPolicySimulate` |

事件：EventBar（upload + manual，kinds: policy/protest/decree）  
PDF：**自动下载**（`downloadPdfBase64`）

响应：`{ report, policy, pdf_base64, pdf_filename, lab }`

---

#### C.7.3 WeatherPanel

**文件**：`components/WeatherPanel.tsx`  
**边框色**：sky

| 控件 | 选项 | API 参数 |
|------|------|---------|
| 推演视角 | farmer/herder/government/transport | `role_key` |
| 气候模式 | weather.patterns[] | `pattern_key` |
| 推演周期 | 24 | `steps` |

极端事件：manual kind=flood  
API：`labWsWeatherSimulate`  
PDF：自动下载

---

#### C.7.4 EnvironmentPanel

**文件**：`components/EnvironmentPanel.tsx`  
**边框色**：lime

| 控件 | API 参数 |
|------|---------|
| 地区类型 regionKey | `region_key` |
| 治理措施 measureKey | `measure_key` |
| 排放企业 | `enterprise_name` |
| 排放强度 slider 0.05–1 | `emission_intensity` |
| 推演周期 默认 36 | `steps` |

API：`labWsEnvironmentSimulate`  
无事件输入 UI

---

#### C.7.5 MilitaryPanel

**文件**：`components/MilitaryPanel.tsx`  
**边框色**：rose

| 控件 | API 参数 |
|------|---------|
| 战役场景 | `scenario_key` |
| 战场地形 | `battlefield_key` |
| 推演步数 默认 12 | `steps` |

事件：upload + manual（kind 默认 war）  
API：`labWsMilitarySimulate`  
响应含 `result`, `simulation`, `report`, `pdf_base64`

---

#### C.7.6 PopulationPanel

**文件**：`components/PopulationPanel.tsx`  
**边框色**：emerald

| 控件 | API 参数 |
|------|---------|
| 推演范围 global/city/region | `scope` |
| 城市/地区 select | `region_key`, `city_key` |
| 推演年数 默认 10 | `years` |

Metric 行：总人口、范围人口、生育率、认知指数  
事件：upload + manual  
API：`labWsPopulationSimulate`

后端另有 `population/shock`, `population/policy`, `population/cognition` — **前端未调用**。

---

#### C.7.7 OpinionPanel

**文件**：`components/OpinionPanel.tsx`  
**边框色**：violet

| 控件 | API |
|------|-----|
| 议题 topic | `labWsOpinionSimulate({ steps, topic })` |
| 推演步数 8–120 | |
| 干预按钮组 | `labWsOpinionIntervene(labId, key)` |

显示：heat / sentiment / polarization；result.phase  
**无** LabReportView、**无** PDF

---

#### C.7.8 LabDatasetPanel（非 UNIFIED_SIM_LABS 时）

**文件**：`components/LabDatasetPanel.tsx`  
用于 `labKey ∉ UNIFIED_SIM_LABS` 的 lab（当前基本不用，opinion 无此 panel）

- upload + manual events
- `labWsRunReport({ horizon, mode })` — mode: auto/global/city
- 页面级 LabReportView 展示报告

---

### C.8 3D 地图预览 `/dev/maps`

**文件**：`app/dev/maps/page.tsx`  
**认证**：无

| 控件 | 行为 |
|------|------|
| Genre 按钮组 | ancient/wuxia/xuanhuan/mystery/modern/scifi |
| 时辰 slider 0–23 | 传给 World3D hour |
| World3D | agents=[], 全屏高度 |

`preloadKitUrls(genreKitUrls(genre))` 预加载 GLB。

---

### C.9 角色形象预览 `/dev/figures`

**文件**：`app/dev/figures/page.tsx`  
**认证**：无

| 控件 | 行为 |
|------|------|
| Genre 切换 | wuxia/ancient/scifi/xuanhuan/mystery |
| 4 套皮肤 | fair/tan/warm/pale |
| preset 网格 | CharacterFigureThumb |
| 主预览 | CharacterFigurePreview |

---

## D. 共享组件规格

### D.1 布局与认证

| 组件 | 文件 | 职责 |
|------|------|------|
| AuthProvider | `lib/auth.tsx` | user, token, login, register, logout, getMe |
| RootLayout | `app/layout.tsx` | 包裹 AuthProvider |

### D.2 文明与角色

| 组件 | Props 要点 | API |
|------|-----------|-----|
| CivilizationSelector | value, onChange | `listSeeds` |
| CivilizationDashboard | seedKey, compact? | `getCivilizationDashboard` |
| CharacterPicker | categories, onConfirm(category, variant, skin) | — |
| CharacterFigurePreview | preset, genre | — |
| CharacterFigureThumb | preset | — |

### D.3 叙事 Play 组件

| 组件 | 关键 Props | API |
|------|-----------|-----|
| World3D | genre, agents, playerId, hour, cameraMode, dormant | 见 [3D 文档](./3d-world-and-characters.md) |
| WorldAtlas | session, stats | — |
| WorldDrawer | session, onClose | dashboard |
| ChoicePanel | choices, onChoose, input, onSubmit | — |
| SkillPanel | skills, onUse | — |
| NpcPanel | sid, agents, genre | — |
| NpcChat | sid, npc_id | `talkToNpc` |
| TaskPanel | sid, session, onUpdate | tasks API |
| InjectPanel | sid, session, onUpdate | inject API |
| StatBars | stats | — |
| WakeBriefingModal | briefing | — |

### D.4 实验平台组件

| 组件 | 说明 |
|------|------|
| FinancePanel | 见专题文档 |
| PolicyPanel / WeatherPanel / … | 见 C.7 |
| LabReportView | report, animate?, pdfBase64?, pdfFilename? |
| LabDatasetPanel | 通用数据集+report |
| InstitutionsPanel | institutions[] 只读 |
| AuditTrailPanel | auditTrail, methodology, calibration |
| FanChart | confidence bands |

### D.5 LabReportView 区块顺序

1. 标题 + PDF 下载（manual，Finance；其他 lab 多 auto-download）
2. conclusion
3. predictions 网格
4. charts（line/fan/histogram/scatter/radar）
5. tables（animate reveal > 0.4）
6. event_impacts（> 0.6）
7. analysis（> 0.8）
8. disclaimer

---

## E. 前端 API 客户端映射表

**文件**：`frontend/src/lib/api.ts`  
**Base URL**：`""`（同源）

### E.1 页面 → 函数 → 端点

| 页面/组件 | api.ts 函数 | HTTP |
|-----------|------------|------|
| login | register, login | POST /api/auth/* |
| auth init | getMe | GET /api/auth/me |
| 首页 | listSeeds, listLabs | GET /api/seeds, /api/labs |
| create | getPlayerCatalog, createSession | GET .../characters, POST /api/sessions |
| civilizations/new | createCustomCivilization | POST /api/civilizations/custom |
| play | stepSession, useSkill, talkToNpc, sendHeartbeat, sleepSession, wakeSession, inject*, skipToTick, createSelfTask, completeTask | 见 F.5 |
| play poll | — | GET /api/sessions/{sid} |
| labs | openLab, getLabWorkspace, listLabs | POST .../open, GET workspace |
| FinancePanel | labWsFinanceSimulate, labWsUploadDataset, labWsAddManualEvents, labWsFinanceShock, labWsAdvanceFinance | 见 F.6 |
| PolicyPanel | labWsPolicySimulate, labWsUploadDataset, labWsAddManualEvents | 见 F.6 |
| WeatherPanel | labWsWeatherSimulate, labWsAddManualEvents | 见 F.6 |
| EnvironmentPanel | labWsEnvironmentSimulate | 见 F.6 |
| MilitaryPanel | labWsMilitarySimulate, labWsUploadDataset, labWsAddManualEvents | 见 F.6 |
| PopulationPanel | labWsPopulationSimulate, labWsUploadDataset, labWsAddManualEvents | 见 F.6 |
| OpinionPanel | labWsOpinionSimulate, labWsOpinionIntervene | 见 F.6 |
| CivilizationDashboard | getCivilizationDashboard | GET .../dashboard |

### E.2 已定义但前端未使用的函数

| 函数 | 说明 |
|------|------|
| listCustomCivilizations | GET /api/civilizations/custom |
| rebindLab | POST .../rebind |
| getFinance | GET .../finance |
| labGlobalForecast 等 session 版 | legacy session finance |
| labWsGlobalForecast 等 workspace 细粒度 | 被 simulate 统一取代 |
| labWsMilitaryConfigure | POST .../military/configure |
| labWsPopulationShock/Policy/Cognition | POST population 子端点 |
| labWsOpinionNode | POST .../opinion/node |
| labWsRunReport | 仅 LabDatasetPanel（当前极少挂载） |

---

## F. 后端 API 完整清单

**源文件**：`backend/app/main.py`  
**通用错误**：401 未认证；404 资源不存在；400 参数/业务错误；500 未捕获异常 `{ error }`

**Lab workspace 通用规则**：需 `get_current_user` 且 `ws.user_id == user.id`，否则 404 `lab workspace not found`。

---

### F.1 认证

| 方法 | 路径 | Body | Response | Auth |
|------|------|------|----------|------|
| POST | `/api/auth/register` | `{ username, password, display_name? }` | `{ token, user }` | 无 |
| POST | `/api/auth/login` | `{ username, password }` | `{ token, user }` | 无 |
| GET | `/api/auth/me` | — | `{ user, sessions[] }` | 必须 |

`user`: `{ id, username, display_name, created_at }`

---

### F.2 种子与仪表盘

| 方法 | 路径 | Response | Auth |
|------|------|----------|------|
| GET | `/api/seeds` | `{ seeds: Seed[] }` | 可选（登录含自定义） |
| GET | `/api/seeds/{seed_key}/characters` | `PlayerCatalog` | 可选 |
| GET | `/api/seeds/{seed_key}/dashboard` | `{ dashboard: CivilizationDashboard }` | 可选 |

---

### F.3 自定义文明

| 方法 | 路径 | Body | Response | Auth |
|------|------|------|----------|------|
| GET | `/api/civilizations/custom` | — | `{ civilizations[] }` | 必须 |
| POST | `/api/civilizations/custom` | CustomCivilizationReq | `{ civilization }` | 必须 |
| GET | `/api/civilizations/custom/{civ_id}` | — | `{ civilization }` | 必须 |

**CustomCivilizationReq**：

```json
{
  "name": "未命名文明",
  "class_structure": { "ruling": 0.05, "middle": 0.35, "labor": 0.5, "marginal": 0.1 },
  "age_structure": { "child": 0.18, "youth": 0.22, "adult": 0.4, "middle_aged": 0.12, "elder": 0.08 },
  "operating_logic": "必填",
  "government_form": "",
  "professions": [{ "name", "description", "playable" }],
  "roles": [{ "name", "persona", "profession", "goals", "traits" }],
  "historical_events": [{ "era", "title", "description" }],
  "current_stage": ""
}
```

---

### F.4 文明与种子

（F.2、F.3 已覆盖）

---

### F.5 会话（叙事）

| 方法 | 路径 | Body | Response 要点 | Auth |
|------|------|------|--------------|------|
| GET | `/api/sessions` | — | `{ sessions[] }` | 可选 |
| POST | `/api/sessions` | CreateSessionReq | `{ session, page }` | 必须 |
| GET | `/api/sessions/{sid}` | — | `{ session }` | 无 |
| POST | `/api/sessions/{sid}/join` | `{ description }` | `{ session, player_id }` | 无 |
| POST | `/api/sessions/{sid}/step` | `{ input?, player_id? }` | `{ page, stats?, session? }` | 无 |
| POST | `/api/sessions/{sid}/use-skill` | `{ skill_id, player_id? }` | 同 step | 无 |
| GET | `/api/sessions/{sid}/replay` | `?to_tick=` | `{ session }` | 无 |
| POST | `/api/sessions/{sid}/heartbeat` | `{ player_id?, reason? }` | `{ player_id, presence, tick }` | 无 |
| POST | `/api/sessions/{sid}/sleep` | `{ player_id?, reason? }` | `{ presence, offline_mode, session }` | 无 |
| POST | `/api/sessions/{sid}/wake` | `{ player_id? }` | `{ already_awake, briefing?, session }` | 无 |
| GET | `/api/sessions/{sid}/clock` | — | `{ tick, hour, day, era, label }` | 无 |
| GET | `/api/sessions/{sid}/npcs` | `?location_id=` | `{ npcs[] }` | 无 |
| POST | `/api/sessions/{sid}/talk` | `{ npc_id, text, player_id? }` | `{ npc_id, npc_name, reply }` | 无 |
| GET | `/api/sessions/{sid}/injections` | — | `{ injections, tick }` | 无 |
| POST | `/api/sessions/{sid}/inject/event` | `{ tick, summary, importance?, location_id? }` | `{ injection, session }` | 无 |
| POST | `/api/sessions/{sid}/inject/character` | InjectCharacterReq | `{ injection, session }` | 无 |
| POST | `/api/sessions/{sid}/skip-to-tick` | `{ target_tick }` | `{ tick, steps, session }` | 无 |
| GET | `/api/sessions/{sid}/tasks` | `?player_id=` | `{ tasks, tick }` | 无 |
| POST | `/api/sessions/{sid}/tasks/self` | `{ title, description?, rewards?, player_id? }` | `{ task, session }` | 无 |
| POST | `/api/sessions/{sid}/tasks/{task_id}/complete` | `{ player_id? }` | `{ task, pay, session }` | 无 |

**CreateSessionReq**：`{ seed_key, description?, category_key?, variant_key?, skin? }`

---

### F.6 会话金融（Legacy，Play UI 未挂载）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions/{sid}/finance` | `?format=json\|csv` |
| POST | `/api/sessions/{sid}/finance/shock` | FinanceShockReq |
| POST | `/api/sessions/{sid}/finance/advance` | `{ steps }` |
| GET | `/api/sessions/{sid}/finance/lab` | finance_lab snapshot |
| POST | `/api/sessions/{sid}/finance/lab/global/forecast` | `{ horizon }` |
| POST | `/api/sessions/{sid}/finance/lab/global/event` | LabEventReq |
| POST | `/api/sessions/{sid}/finance/lab/city/forecast` | `{ horizon, city_key? }` |
| POST | `/api/sessions/{sid}/finance/lab/city/event` | LabEventReq |
| POST | `/api/sessions/{sid}/finance/lab/corporate/forecast` | corporate body |
| POST | `/api/sessions/{sid}/finance/lab/corporate/event` | LabEventReq |
| POST | `/api/sessions/{sid}/finance/lab/retail/run` | LabRetailReq |

Workspace 等价路径前缀：`/api/labs/workspace/{lab_id}/finance/...`

**FinanceShockReq**：`{ kind="demand", good_id="*", magnitude=0.35, duration=12, note="" }`

---

### F.7 实验平台 — 工作区

| 方法 | 路径 | Body | Response 要点 | Auth |
|------|------|------|--------------|------|
| GET | `/api/labs` | — | `{ labs: LabMeta[] }` | 无 |
| POST | `/api/labs/{lab_key}/open` | `{ civilization_key?, genre? }` | LabWorkspace | 必须 |
| GET | `/api/labs/workspace/{lab_id}` | — | LabWorkspace | 必须+owner |
| POST | `/api/labs/workspace/{lab_id}/rebind` | `{ civilization_key }` | LabWorkspace | 必须+owner |

**LabWorkspace**（lab_snapshot）：

```typescript
{
  id, lab_key, civilization_key, civilization_name, genre,
  meta: { key, name, blurb, status, accent? },
  finance, finance_lab, opinion, military, policy, weather, environment, population,
  timeline_events,  // 最近 50 条
  last_report,
  status
}
```

---

### F.8 实验平台 — 统一推演与各 Lab

#### 金融

| 方法 | 路径 | Body | 特殊 |
|------|------|------|------|
| POST | `.../finance/simulate` | FinanceSimulateReq | lab_key=finance |

**FinanceSimulateReq**：`{ mode, horizon, city_key?, company_key?, company_name?, sector?, risk, retail_horizon, capital?, market_steps?, skip_llm }`

→ `{ report, simulation, mode, pdf_base64, pdf_filename, finance, finance_lab, lab }`

#### 政策 / 气象 / 环保

| Lab | 路径 | Body | lab_key 校验 |
|-----|------|------|-------------|
| policy | `.../policy/simulate` | `{ steps, agency_key?, instrument_key? }` | policy |
| weather | `.../weather/simulate` | `{ steps, role_key?, pattern_key? }` | weather |
| environment | `.../environment/simulate` | `{ steps, region_key?, measure_key?, emission_intensity?, enterprise_name? }` | environment |

共同响应：`{ report, result, simulation, pdf_base64, pdf_filename, {lab_state}, lab }`

#### 军事

| 方法 | 路径 | Body |
|------|------|------|
| POST | `.../military/configure` | `{ scenario_key, battlefield_key }` |
| POST | `.../military/simulate` | `{ steps, scenario_key?, battlefield_key? }` |

#### 人口

| 方法 | 路径 | Body |
|------|------|------|
| POST | `.../population/simulate` | `{ years, scope, region_key?, city_key? }` |
| POST | `.../population/shock` | `{ kind, magnitude?, note? }` |
| POST | `.../population/policy` | `{ kind, magnitude? }` |
| POST | `.../population/cognition` | `{ kind, magnitude? }` |

#### 舆情

| 方法 | 路径 | Body | Response |
|------|------|------|----------|
| POST | `.../opinion/simulate` | `{ steps, topic? }` | `{ result, opinion, lab }` |
| POST | `.../opinion/intervene` | `{ key, note? }` | `{ intervention, opinion, lab }` |
| POST | `.../opinion/node` | `{ at_step, title, kind?, magnitude? }` | `{ node, opinion, lab }` |

---

### F.9 实验平台 — 共享数据操作

| 方法 | 路径 | Body | Response |
|------|------|------|----------|
| POST | `.../datasets/upload` | multipart `file` (max 8MB) | `{ imported, events, lab }` |
| POST | `.../events/manual` | `{ events[], use_llm_ner? }` | `{ added, timeline_events, lab }` |
| POST | `.../report/run` | `{ horizon?, mode? }` | `{ report, lab }` |

**manual event 单条**：`{ time?, title, magnitude?, kind?, description? }`

**upload 格式**：`.csv .xlsx .xls .md .markdown .txt .zip`

#### 金融市场增量（workspace）

| 方法 | 路径 | Body |
|------|------|------|
| POST | `.../finance/advance` | `{ steps }` → `{ steps, events, finance, finance_lab, lab }` |
| POST | `.../finance/shock` | FinanceShockReq |

#### 金融细粒度 forecast（Legacy，前端未用）

`.../finance/lab/{global|city|corporate}/forecast|event`, `.../retail/run`

---

### F.10 其他

| 方法 | 路径 | Response |
|------|------|----------|
| GET | `/api/tts/info` | `{ backend_tts: false, use_browser_speech_synthesis: true }` |
| GET | `/` | `{ name, version }` |

---

## G. 核心数据类型

定义于 `frontend/src/lib/api.ts`。

| 类型 | 用途 |
|------|------|
| Seed | 文明种子卡片 |
| Session | 叙事会话全貌 |
| Page, Beat, StoryChoice | 叙事页 |
| Agent, AgentSkill | 玩家/NPC |
| WorldStats | 五维统计 |
| GameTask | 任务 |
| WakeBriefing | 苏醒简报 |
| LabMeta, LabWorkspace | 实验平台 |
| LabReport | 推演报告 |
| TimelineEvent | 实验室事件 |
| CivilizationDashboard | 文明仪表盘 |
| CustomCivilizationConfig | 自定义文明表单 |
| FinanceSnapshot | 市场清算快照 |

**LabReport** 字段：`title, lab_key, civilization_key, horizon, dimensions, charts[], tables[], event_impacts[], predictions[], analysis[], conclusion?, disclaimer, mode?, mode_label?, dashboard?, simulation?`

---

## H. WebSocket

```
WS /ws/sessions/{sid}
```

| 方向 | 消息 |
|------|------|
| S→C 初始 | `{ type: "snapshot", session }` |
| S→C 推送 | finance_tick, finance_shock, wake, npc_dialogue, simulation_tick, … |
| C→S | `{ type: "input\|heartbeat\|sleep\|wake\|ping", ... }` |

**Play 页当前未连接 WebSocket**；使用 HTTP 4s 轮询。

---

## I. 静态资产

| 类型 | URL | 文档 |
|------|-----|------|
| 3D 地图 JSON | `/maps/{genre}.json` | [3D 文档](./3d-world-and-characters.md) |
| 2D 地图 PNG | `/maps/{seedKey}.png` | 同上 |
| 建筑 GLB | `/models/buildings/{genre}/*.glb` | 同上 |
| 角色 GLTF | `/models/characters/roles/{id}/body.glb` | 同上 |
| 地面贴图 | `/textures/ground/{dirt\|asphalt\|neon}.png` | 同上 |

---

## J. 源码索引

### 前端页面

| 路径 | 文件 |
|------|------|
| `/` | `app/page.tsx` |
| `/login` | `app/login/page.tsx` |
| `/create/[seedKey]` | `app/create/[seedKey]/page.tsx` |
| `/play/[sid]` | `app/play/[sid]/page.tsx` |
| `/civilizations/new` | `app/civilizations/new/page.tsx` |
| `/labs` | `app/labs/page.tsx` |
| `/labs/[labKey]` | `app/labs/[labKey]/page.tsx` |
| `/dev/maps` | `app/dev/maps/page.tsx` |
| `/dev/figures` | `app/dev/figures/page.tsx` |

### 前端 lib

| 文件 | 职责 |
|------|------|
| `lib/api.ts` | 全部 API 函数与类型 |
| `lib/auth.tsx` | 认证上下文 |
| `lib/audio.ts` | TTS + 翻页音效 |
| `lib/characterFigures.ts` | 人物 preset |
| `lib/buildingKits.ts` | 建筑 GLB 注册 |
| `lib/gltfCharacters.ts` | PBR 与材质槽 |

### 后端

| 文件 | 职责 |
|------|------|
| `app/main.py` | 全部 HTTP + WS 路由 |
| `app/labs/workspace.py` | Lab 工作区与推演 |
| `app/layer2_civilization/*` | 各数值引擎 |

---

## 附录：Lab key 与 status

| lab_key | 中文名 | 前端 status | Panel |
|---------|--------|------------|-------|
| finance | 金融实验室 | ready | FinancePanel |
| weather | 气象演化实验室 | ready | WeatherPanel |
| policy | 政令推演实验室 | ready | PolicyPanel |
| environment | 环保演化实验室 | ready | EnvironmentPanel |
| opinion | 舆情发酵实验室 | ready | OpinionPanel |
| military | 军事推演实验室 | ready | MilitaryPanel |
| population | 人口发展实验室 | ready | PopulationPanel |

以运行时 `GET /api/labs` 返回为准。

---

*维护：新增页面或 API 时必须同步更新本文档对应章节。*

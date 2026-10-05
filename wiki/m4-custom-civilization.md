# M4：玩家创造文明（自定义 Seed + 规则编辑器）

状态：**已完成（Phase A — 规则编辑深化）**

---

## 目标

玩家可自建文明种子：编辑世界规则、地点、势力、人口与角色，并直接开局进入 Play / 实验室。

---

## 能力

| 能力 | 说明 |
|------|------|
| 创建 | `/civilizations/new` 完整规则编辑器 |
| 列表管理 | `/civilizations`：进入 / 编辑 / 删除 |
| 编辑 | `/civilizations/{id}/edit` |
| Seed 物化 | `custom_to_seed` → 与内建种子同一 Session 管线 |
| 气质 genre | 可选 ancient / wuxia / scifi…，影响氛围音画 |

未填地点 / 势力 / 规则时，仍按运行逻辑与阶层自动补全。

---

## 配置字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `operating_logic` | ✓ | 文明运行逻辑 |
| `name` / `genre` / `premise` | | 基本信息 |
| `rules[]` | | 硬约束（最多 12） |
| `locations[]` | | 地点名 / 描述 / 标签 |
| `factions[]` | | 势力名 / 意识形态 |
| `opening_scene` | | 开场旁白 |
| `class_structure` / `age_structure` | | 人口比例 |
| `professions` / `roles` / `historical_events` | | 职业、可玩角色、史事 |
| `government_form` / `current_stage` | | 政权与阶段 |

---

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/civilizations/custom` | 我的文明列表 |
| POST | `/api/civilizations/custom` | 创建 |
| GET | `/api/civilizations/custom/{id}` | 详情（含 config） |
| PUT | `/api/civilizations/custom/{id}` | 更新 |
| DELETE | `/api/civilizations/custom/{id}` | 删除 |
| GET | `/api/seeds` | 内建 + 自定义（`is_custom`） |

种子 key 形如 `custom_{id}`。

---

## 相关代码

| 模块 | 路径 |
|------|------|
| 持久化 | `backend/app/layer6_persistence/custom_civilizations.py` |
| Seed 解析 | `backend/app/layer2_civilization/civilization_resolver.py` |
| 规则编辑器 UI | `frontend/src/components/CivilizationRuleEditor.tsx` |
| 创建 / 列表 / 编辑 | `frontend/src/app/civilizations/` |

---

## 验证

```bash
cd backend && source .venv/bin/activate
QDRANT_ENABLED=false LLM_PROVIDER=mock pytest tests/test_custom_civilization.py -q
```

手测：登录 → 文明模拟器 → 自定义文明 → 填规则与地点 → 选角开局 → 「我的文明」可编辑删除。

# 金融实验室

金融实验室是**文明背景下的情景沙盘**：在可控、可复现的数值模型上，测试「若发生某事件，宏观 / 城市 / 企业 / 市场指标可能如何演化」。

> **定位**：沙盘推演与教学演示，**非实盘投资建议**。  
> 数值由 seed 驱动的确定性模型生成；LLM 仅润色 narrative 文案，**不参与生成数字**。

---

## 开发者文档（首选）

**全站 UI 页面与前后端接口**：

👉 **[docs/ui-design-and-api-complete.md](../docs/ui-design-and-api-complete.md)**

| 专题 | 文档 |
|------|------|
| **全站 UI + 全部 API** | [ui-design-and-api-complete.md](../docs/ui-design-and-api-complete.md) |
| 金融实验室深入 | [docs/finance-lab-ui-api.md](../docs/finance-lab-ui-api.md) |
| 叙事 Play 会话 | [docs/play-session-ui-api.md](../docs/play-session-ui-api.md) |
| 3D 地图与人物模型 | [docs/3d-world-and-characters.md](../docs/3d-world-and-characters.md) |

---

## 快速入口

| 入口 | 路径 | 说明 |
|------|------|------|
| **实验平台（推荐）** | `/labs/finance` | 需登录；完整 FinancePanel |
| 游戏会话 | `/play/[sid]` | **无**金融实验室入口（已移除） |

---

## 五种推演模式

| Tab | `mode` | 引擎 |
|-----|--------|------|
| 全局走势 | `global` | structured_macro_v2 + Monte Carlo + 长程融合 |
| 城市金融 | `city` | 同上（城市指标映射） |
| 企业评估 | `corporate` | macro β + 特质冲击 |
| 量化交易 | `retail` | GBM 合成路径（融合关闭） |
| 市场清算 | `market` | agent_based_market_v1（多 Agent ABM） |

主推演 API：

```
POST /api/labs/workspace/{lab_id}/finance/simulate
```

---

## 架构要点（v2）

### 推演递推

- **Markov 链**：第 N 步基于 N−1 步 + 事件冲击
- **长程融合**：AR(1)/EWMA/对数趋势估计，按 **9 文明 × 4 模式** 策略表加权校正（`finance_fusion_config.py`）
- **retail 模式**：融合关闭，仅用 macro 校准波动率

### multi-agent？

| 模式 | 是否 multi-agent |
|------|------------------|
| global / city / corporate / retail | 否 |
| market | **是** — 合成商户 Agent 供需清算 |

### 输出物

| 输出 | 说明 |
|------|------|
| `simulation` | history/forecast、audit_trail、confidence_bands、institutions |
| `report` | 图表、表格、终结性结论、事件影响 |
| `pdf_base64` | PDF（前端**手动**下载） |

---

## 推荐工作流

```
登录 → /labs/finance → 选文明 → 录事件（可选）
→ 选 Tab → 设步数 → 开始推演 → 查看报告 → 下载 PDF
```

---

## 相关代码

| 模块 | 路径 |
|------|------|
| 前端主面板 | `frontend/src/components/FinancePanel.tsx` |
| 报告视图 | `frontend/src/components/LabReportView.tsx` |
| API 类型 | `frontend/src/lib/api.ts` |
| 实验室页面 | `frontend/src/app/labs/[labKey]/page.tsx` |
| 统一推演 | `backend/app/labs/workspace.py` |
| 宏观核心 | `backend/app/layer2_civilization/finance_sim_core.py` |
| 长程融合 | `backend/app/layer2_civilization/finance_longrun.py` |
| 融合策略表 | `backend/app/layer2_civilization/finance_fusion_config.py` |
| 市场 ABM | `backend/app/layer2_civilization/finance.py` |
| 报告 enrich | `backend/app/labs/report.py` |

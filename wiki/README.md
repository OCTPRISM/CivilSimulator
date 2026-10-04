# CivilSimulator Wiki

项目文档索引。

## 开发者技术规格

### 全站完整文档（首选）

👉 **[docs/ui-design-and-api-complete.md](../docs/ui-design-and-api-complete.md)**

- 全部 9 个 UI 页面
- 全部前后端 API（70+ 路由）
- 全部 Lab Panel 与 Play 组件
- 全局 UI 设计规范

### 文档索引

👉 **[docs/README.md](../docs/README.md)**

| 专题 | 文档 |
|------|------|
| **全站 UI + API** | [ui-design-and-api-complete.md](../docs/ui-design-and-api-complete.md) |
| 金融实验室 | [finance-lab-ui-api.md](../docs/finance-lab-ui-api.md) |
| 叙事 Play | [play-session-ui-api.md](../docs/play-session-ui-api.md) |
| 3D 地图与人物 | [3d-world-and-characters.md](../docs/3d-world-and-characters.md) |

## 实验室概览

| 文档 | 说明 |
|------|------|
| [金融实验室](./finance-lab.md) | 产品定位（链接至 docs） |

## 相关代码

| 模块 | 路径 |
|------|------|
| 全站 API 路由 | `backend/app/main.py` |
| 前端 API 客户端 | `frontend/src/lib/api.ts` |
| 全部页面 | `frontend/src/app/**/page.tsx` |
| 3D 世界 | `frontend/src/components/World3D.tsx` |
| 实验室工作区 | `backend/app/labs/workspace.py` |
| 金融面板 | `frontend/src/components/FinancePanel.tsx` |

# CivilSimulator 技术文档索引

> **维护约定**：代码变更时同步更新对应文档。  
> **版本基准**：2026-10-05（含 M1 Ollama/Qdrant、M2 多人房间）

---

## 主文档（全站完整规格）

👉 **[全站 UI 设计与前后端接口完整规格](./ui-design-and-api-complete.md)**

涵盖：

- **全部 9 个 UI 页面**（布局、控件、交互、API 映射）
- **全部 7 个实验室 Panel** + Play 页组件
- **全部后端 API**（70+ 路由，请求/响应/认证）
- **前端 api.ts 函数 ↔ 端点对照表**
- 全局 UI 设计规范、数据类型、WebSocket、静态资产索引

---

## 专题深读

| 文档 | 适用场景 |
|------|---------|
| [deploy-tech-preview.md](./deploy-tech-preview.md) | Tech Preview 单机 / 邀测起服 |
| [backup-restore.md](./backup-restore.md) | `data/runtime` 备份与恢复演练（v0.5 P-3） |
| [ops-secrets.md](./ops-secrets.md) | AUTH_SECRET 轮换与依赖审计（v0.5 P-6） |
| [multimodal-scene-art.md](./multimodal-scene-art.md) | 生产多模态主路径：场景插画（v0.5 P-5） |
| [ui-design-and-api-complete.md](./ui-design-and-api-complete.md) | **首选** — 全站 UI + API |
| [finance-lab-ui-api.md](./finance-lab-ui-api.md) | 金融实验室推演引擎、audit、fusion、报告 enrich 细节 |
| [play-session-ui-api.md](./play-session-ui-api.md) | Play 页 Presence、轮询、Session 对象详解 |
| [3d-world-and-characters.md](./3d-world-and-characters.md) | World3D、地图 JSON、GLB/GLTF 资产管线 |

---

## 文档关系

```
ui-design-and-api-complete.md  ← 全站基准（页面 + 全部 API）
    ├── finance-lab-ui-api.md    ← 金融专题加深
    ├── play-session-ui-api.md   ← 叙事 Play 加深
    └── 3d-world-and-characters.md ← 3D 渲染加深
```

---

## 产品模块速查

| 模块 | 路由 | 3D | 主文档章节 |
|------|------|-----|-----------|
| 首页 | `/` | ❌ | [C.1](./ui-design-and-api-complete.md#c1-首页-) |
| 登录 | `/login` | ❌ | [C.2](./ui-design-and-api-complete.md#c2-登录注册-login) |
| 角色创建 | `/create/[seedKey]` | 预览 | [C.3](./ui-design-and-api-complete.md#c3-角色创建-seedkey) |
| 叙事游戏 | `/play/[sid]` | ✅ | [C.4](./ui-design-and-api-complete.md#c4-叙事游戏-playsid) |
| 加入房间 | `/join/[sid]` | ❌ | [wiki/m2-multiplayer.md](../wiki/m2-multiplayer.md) |
| 自定义文明 | `/civilizations/new` | ❌ | [C.5](./ui-design-and-api-complete.md#c5-自定义文明-civilizationsnew) |
| 实验室索引 | `/labs` | ❌ | [C.6](./ui-design-and-api-complete.md#c6-实验室索引-labs) |
| 实验室详情 | `/labs/[labKey]` | ❌ | [C.7](./ui-design-and-api-complete.md#c7-实验室详情-labkey) |
| 3D 地图预览 | `/dev/maps` | ✅ | [C.8](./ui-design-and-api-complete.md#c8-3d-地图预览-devmaps) |
| 角色预览 | `/dev/figures` | 预览 | [C.9](./ui-design-and-api-complete.md#c9-角色形象预览-devfigures) |

---

## 技术栈

Next.js App Router · React · TypeScript · Tailwind · Three.js · FastAPI

认证：`localStorage.civsim_token` → `Authorization: Bearer ...`

---

## Wiki

[wiki/README.md](../wiki/README.md) — 里程碑、M1/M2 指南与代码路径索引

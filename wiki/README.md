# CivilSimulator Wiki

项目文档索引（与代码同步维护）。

**开发者：** Zhongjiang Yao

---

## 里程碑

| 阶段 | 状态 | Wiki |
|------|------|------|
| M0 六层骨架 + Mock LLM | 完成 | — |
| M1 本地 LLM + Qdrant 记忆 | 完成 | [m1-llm-qdrant.md](./m1-llm-qdrant.md) |
| M2 多人同世界 | 完成 | [m2-multiplayer.md](./m2-multiplayer.md) |
| M3 多模态 | 完成（Phase A） | [m3-multimodal.md](./m3-multimodal.md) |
| M4 自定义文明 | 完成（Phase A） | [m4-custom-civilization.md](./m4-custom-civilization.md) |
| **首发 v0.1 计划** | **评估：尚未可公开发布** | [v0.1-release-plan.md](./v0.1-release-plan.md) |

---

## 开发者技术规格

### 全站完整文档（首选）

👉 **[docs/ui-design-and-api-complete.md](../docs/ui-design-and-api-complete.md)**

- UI 页面、前后端 API、Lab / Play 组件、设计规范

### 文档索引

👉 **[docs/README.md](../docs/README.md)**

| 专题 | 文档 |
|------|------|
| **全站 UI + API** | [ui-design-and-api-complete.md](../docs/ui-design-and-api-complete.md) |
| 金融实验室 | [finance-lab-ui-api.md](../docs/finance-lab-ui-api.md) |
| 叙事 Play | [play-session-ui-api.md](../docs/play-session-ui-api.md) |
| 3D 地图与人物 | [3d-world-and-characters.md](../docs/3d-world-and-characters.md) |
| Hunyuan3D 安装 | [hunyuan3d-setup.md](../docs/hunyuan3d-setup.md) |

---

## 实验室 / 产品 Wiki

| 文档 | 说明 |
|------|------|
| [金融实验室](./finance-lab.md) | 产品定位与入口 |
| [M1 LLM / Qdrant](./m1-llm-qdrant.md) | Ollama 模型、嵌入、向量记忆 |
| [M2 多人同世界](./m2-multiplayer.md) | 房间、邀请、身份绑定、WebSocket |
| [M3 多模态](./m3-multimodal.md) | 场景插画、浏览器 TTS、程序化 BGM |
| [M4 自定义文明](./m4-custom-civilization.md) | Seed 规则编辑、地点/势力、CRUD |
| [首发 v0.1 开发计划](./v0.1-release-plan.md) | 是否可发布、P0/P1 缺口、版本线 |

---

## 相关代码

| 模块 | 路径 |
|------|------|
| HTTP + WebSocket | `backend/app/main.py` |
| 世界房间 Session | `backend/app/session.py` |
| Ollama / Embedding | `backend/app/layer1_foundation/` |
| Qdrant 记忆索引 | `backend/app/layer1_foundation/qdrant_memory.py` |
| Agent 记忆 | `backend/app/layer3_agents/memory.py` |
| 用户 / 房间成员 | `backend/app/layer6_persistence/users.py` |
| 前端 API 客户端 | `frontend/src/lib/api.ts` |
| 玩家身份绑定 | `frontend/src/lib/playIdentity.ts` |
| Play WebSocket | `frontend/src/hooks/useSessionWebSocket.ts` |
| 游玩页 | `frontend/src/app/play/[sid]/page.tsx` |
| 加入房间 | `frontend/src/app/join/[sid]/page.tsx` |
| 场景插画 (Pillow) | `backend/app/layer1_foundation/scene_art.py` |
| 场景板 UI | `frontend/src/components/ScenePlate.tsx` |
| TTS / BGM | `frontend/src/lib/audio.ts` |
| Play 本地设置 | `frontend/src/lib/playSettings.ts` |
| 自定义文明持久化 | `backend/app/layer6_persistence/custom_civilizations.py` |
| 文明 Seed 解析 | `backend/app/layer2_civilization/civilization_resolver.py` |
| 规则编辑器 | `frontend/src/components/CivilizationRuleEditor.tsx` |
| 我的文明 | `frontend/src/app/civilizations/` |
| 3D 世界 | `frontend/src/components/World3D.tsx` |
| 实验室工作区 | `backend/app/labs/workspace.py` |

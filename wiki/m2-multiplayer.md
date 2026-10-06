# M2：多人同世界

状态：**已完成（单进程 MVP）**

---

## 目标

多个登录用户进入**同一个 Session（世界房间）**，各自控制自己的玩家 Agent；共享世界时钟、NPC、位置同步，互不串号。

---

## 概念

| 概念 | 说明 |
|------|------|
| 房间 | 一个 `session_id`（`sess_…`） |
| 玩家身份 | `player_id`（Agent id）；浏览器用 `sessionStorage` + 可选 `?pid=` 绑定 |
| 共享状态 | World / Society / Memory / Finance / Pages |
| 传输 | HTTP API + `WS /ws/sessions/{sid}` |

Redis 多 worker **未接线**（配置项 `REDIS_URL` 仅为 v0.4 预留）。当前必须单 uvicorn 进程内共享房间。

---

## 怎么玩

1. 用户 A 创建世界，进入 `/play/{sid}`  
2. 点 HUD **邀请**，复制链接（形如 `https://…/join/{sid}`）  
3. 用户 B 登录后打开该链接，填写角色描述，加入  
4. 双方各自行动；断线只休眠**自己的**角色  

---

## API 要点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions` | 开房（需登录） |
| POST | `/api/sessions/{sid}/join` | 加入（需登录；`description` 或目录选角字段） |
| GET | `/api/sessions/{sid}?player_id=` | 视角敏感快照（`player_id` / `tasks` / `roster`） |
| POST | `/api/sessions/{sid}/step` | `{ input, player_id }` |
| POST | `/api/sessions/{sid}/sleep` / `wake` / `heartbeat` | 必须带对应 `player_id` |
| WS | `/ws/sessions/{sid}?token=&player_id=` | 需登录 token + 成员；首包 `snapshot`；可再发 `{type:"hello", token, player_id}` |

### WebSocket 客户端消息

```json
{ "type": "hello", "token": "…", "player_id": "agent_…" }
{ "type": "input", "input": "…", "player_id": "agent_…" }
{ "type": "move", "world_x": 0.1, "world_z": -0.2, "player_id": "agent_…" }
{ "type": "heartbeat" | "sleep" | "wake" | "ping", "player_id": "…" }
```

### 服务端推送（节选）

- `snapshot` / `hello_ack`
- `page`、`presence`、`agent_transform(s)`
- `player_joined`（新人入房）
- `finance_tick` / `simulation_tick` 等

断开时仅对**本连接绑定的** `player_id` 执行 sleep（`reason=disconnect`）。

---

## 前端

| 文件 | 职责 |
|------|------|
| `frontend/src/lib/playIdentity.ts` | 绑定 / 保留本地 `player_id` |
| `frontend/src/hooks/useSessionWebSocket.ts` | WS 连接、自动附带 `player_id`、处理 `player_joined` |
| `frontend/src/app/play/[sid]/page.tsx` | 游玩 + 邀请 |
| `frontend/src/app/join/[sid]/page.tsx` | 加入页 |
| `frontend/src/lib/api.ts` | `joinSession` / `getSession` / step·sleep·wake 传 `player_id` |

房间成员持久化：`session_members` 表（`backend/app/layer6_persistence/users.py`）。

---

## 验证

单元测试：

```bash
cd backend && source .venv/bin/activate
LLM_PROVIDER=mock QDRANT_ENABLED=false pytest tests/test_multiplayer_room.py -q
```

覆盖：双玩家加入、视角字典、休眠隔离、移动隔离。

联调清单：

- [ ] 两浏览器两账号，同一 `sid`  
- [ ] 各自 `player_id` 不同，HUD 显示「N 人同世」  
- [ ] 一方离线，另一方仍为 active  
- [ ] WS 连接后 snapshot 的 `player_id` 是自己  

---

## 非目标（后续）

- Redis / 多 worker 房间广播  
- 每人独立叙事频道（当前页面流仍共享，标注 POV）  
- 踢人 / 房主转让 / 硬性人数 UI  

---

## 相关

- 根 [README.md](../README.md)  
- [M1 LLM / Qdrant](./m1-llm-qdrant.md)  
- Play 专题：[docs/play-session-ui-api.md](../docs/play-session-ui-api.md)

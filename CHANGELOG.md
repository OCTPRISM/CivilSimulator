# Changelog

## v0.3.0 — 2026-10-06 (WIP)

方案 B 续档：重启后端后可从快照恢复可玩房间。

### Persist / restore (B-1…B-5)

- `session_persist`：`persistable_snapshot` + `force_save` / `maybe_save`；`snapshot_version=1`
- 写入时机：创建后、**每幕 step**、周期 tick、玩家 sleep/退出、进程 lifespan 退出 flush
- `POST /api/sessions/{sid}/restore`；Play HTTP/WS / **join** 对成员自动 hydrate
- 「我的世界」：死房间若有兼容快照显示「续玩」；文案改为方案 B
- 单测：create → step → clear `_SESSIONS` → restore → step；损坏 / 版本不兼容不拖垮进程
- 健壮性：等 tick 取最新快照、跳过损坏 JSON、并发 restore 锁、退出 keepalive+鉴权、进房自动 wake、续玩保留坐标

### Honesty

- 续玩承诺为 **可玩优先**（player / 库存 / 地点 / 时钟大致连续）；MemoryStore / 金融子状态 / RNG 可能降级
- 不兼容或损坏快照返回明确错误，提示新建世界
- README 中英双版（[`README.md`](./README.md) / [`README.zh-CN.md`](./README.zh-CN.md)），强调游戏与仿真，可手动切换语言

## v0.2.0 — 2026-10-06

可信预览体验（R1）+ R0 硬化补丁。面向**受控邀测**。

Git tag: `v0.2.0`

### Experience (R1)

- 「我的世界」：登录后列出创建/加入过的房间；`live` 可继续；死房间无主按钮；字段含文明名 / 短 sid / 角色
- 首登引导：三步说明（选文明 → 行动 → 邀请），`civsim_onboarded`
- LLM 错误：`LLMServiceError` 穿透叙事层；创建 / step / 技能返回明确中文 **503**；开场失败清理孤儿房间；Play HUD toast
- 生产关闭 `/dev/*`（Next middleware）
- 邀测：生产强制注册码；`INVITE_ONLY` / `MIN_PASSWORD_LENGTH`；`GET /api/auth/config`
- 验收脚本补 R1 用例；移动端明确 SKIP（非门禁）
- Redis：文档与配置标明 reserved for v0.4，未接线

### Hardening (R0 follow-ups)

- 限流默认不信任伪造 `X-Forwarded-For`（需 `TRUST_PROXY_HEADERS`）
- WS `input` 与 HTTP play 共享按用户限流
- Join 幂等 + session 锁；邀请预览 `/api/sessions/{sid}/invite`
- WS 鉴权优先 hello（前端不再把 token 放进 URL）
- 生产禁止 `CORS_ORIGINS=*`；非 development 环境拒绝默认 `AUTH_SECRET`

## v0.1.0-tech-preview — 2026-10-06

Tech Preview for **local / invite-only** use. Not a public multi-tenant release.

Git tag: `v0.1.0-tech-preview`

### Security (R0)

- Play HTTP APIs require login + session membership (`require_session_member`)
- WebSocket requires `token` (query or hello) + membership before `snapshot`
- Non-development `ENV` refuses default `AUTH_SECRET` at startup
- CORS origins from `CORS_ORIGINS` (no default `*`)
- Rate limits on register + step/talk/join

### Ops / honesty

- Default ports unified: backend `:8000`, frontend `:3000` (see `.env.example`)
- Ephemeral worlds (方案 A): UI states worlds end with the server process
- Generator offline banner; Redis marked as not wired
- Deploy guide: `docs/deploy-tech-preview.md`
- Release roadmap: progress + five-version plan in `wiki/v0.1-release-plan.md`

### Prior milestones (included)

- M1 Ollama + Qdrant memory
- M2 multiplayer room (single process)
- M3 scene art / TTS / BGM (Phase A)
- M4 custom civilization seeds

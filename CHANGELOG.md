# Changelog

## v0.5.0 — WIP

生产硬化（P）。

### Done

- P-4：GitHub Actions CI（`backend` pytest mock + `frontend` `tsc --noEmit`）
- P-3：`backend/scripts/backup_runtime.sh` / `restore_runtime.sh` + [备份演练](./docs/backup-restore.md)
- P-7：按用户 / 房间的 LLM 日配额（UTC，进程内计数；Play step/talk/WS input 绑定）；超限 429
- P-6（起步）：[密钥轮换与依赖审计说明](./docs/ops-secrets.md)

### Still open

- P-1：邮箱验证或魔法链接 + 重置密码
- P-2：结构化日志 + 关键路径指标（可选 Sentry）
- P-5：生产多模态一条路径做透
- P-6 余量：pip-audit / npm audit 进 CI、双 secret 宽限期
- P-7 余量：多 worker 共享配额存储

## v0.4.0 — 2026-10-07

多人房间可运营：人数上限、房主踢人/转让、断线重连；可选 Redis 房间事件中继（不可达自动单机降级）。

Git tag: `v0.4.0`

### Done

- MP-1：创建可配置 `max_players`（2–16，默认 8）；join 按房间上限强制；创建页 / HUD / 邀请预览显示 `人数/上限`
- MP-2：房主 `POST .../kick`、`POST .../transfer-host`；踢人后解除成员、广播 `player_kicked`、关闭被踢者 WS；Play「同世」面板可踢人 / 转让
- MP-3：断线提示与有限次自动重连（8 次）；失败后可手动重连；hello 恢复绑定；WS 心跳；被踢停止重连
- MP-4：单机 drop-oldest 背压 + 服务端 ping；可选 `REDIS_URL` 房间事件 pub/sub（不可达时自动单机降级）；`GET /api/health` 报告 room_bus 状态

### Audit fixes (post MP-1…MP-4)

- 被踢者不再因 `player_kicked` 后 `onSession` 复活 Play 状态；`kickedOut` 屏蔽迟到更新
- 踢人投递：受害者队列保证 `player_kicked` + 不可丢的 `_close`；断线不再对已移出玩家 `sleep`
- 创建 `max_players` API 校验 2–16（422）；成员/鉴权 WS 错误停止空转重连
- Redis 连不上时关闭泄漏客户端；listener 崩溃后禁用 bus 并降级单机

### Known follow-ups (not blocking this tag)

- MP-5（可选）：旁观席
- 多 worker 下 session 状态仍需粘滞路由；Redis 仅中继已序列化的房间事件


## v0.3.0 — 2026-10-06

方案 B 续档：重启后端后可从快照恢复可玩房间。

Git tag: `v0.3.0`

### Persist / restore (B-1…B-5)

- `session_persist`：`persistable_snapshot` + `force_save` / `maybe_save`；`snapshot_version=1`
- 写入时机：创建后、**每幕 step**、周期 tick、玩家 sleep/退出、进程 lifespan 退出 flush
- `POST /api/sessions/{sid}/restore`；Play HTTP/WS / **join** 对成员自动 hydrate
- 「我的世界」：死房间若有兼容快照显示「续玩」；文案改为方案 B
- 单测：create → step → clear `_SESSIONS` → restore → step；损坏 / 版本不兼容不拖垮进程
- 健壮性：等 tick 取最新快照、跳过损坏 JSON、并发 restore 锁、退出 keepalive+鉴权、进房自动 wake、续玩保留坐标；WS **先鉴权再 hydrate**

### Honesty

- 续玩承诺为 **可玩优先**（player / 库存 / 地点 / 时钟大致连续）；MemoryStore / 金融子状态 / RNG 可能降级
- 不兼容或损坏快照返回明确错误，提示新建世界
- README 中英分文件（[`README.md`](./README.md) / [`README.zh-CN.md`](./README.zh-CN.md)），文首左上角 English \| 中文 开关；贡献者仅 Zhongjiang Yao

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

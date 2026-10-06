# Changelog

## Unreleased — v0.2.0 (in progress)

可信预览体验（R1）+ R0 硬化补丁：

- **R1-1** 「我的世界」：`GET /api/sessions` 需登录；字段含文明名 / 短 sid / 角色 / live；死房间无「继续」
- **R1-2** 首登引导：`OnboardingModal` + `localStorage civsim_onboarded`
- **R1-3** LLM 错误：`LLMServiceError` 穿透 Director；创建/step/技能 **503**；开场失败清理孤儿房间；Play HUD toast
- **R1-4** 生产关闭 `/dev/*`（Next middleware）
- **R1-5** 生产强制邀测码；`INVITE_ONLY` / 密码下限；`GET /api/auth/config`；注册策略 fail-closed
- **R1-6** 验收脚本补 R1 用例；移动端明确为 SKIP（非门禁）
- **R1-7** Redis：文档与 `session.py` 声明改为「reserved for v0.4，未接线」
- **R0 补丁** 限流不信任伪造 `X-Forwarded-For`；WS `input` 共享 play 限流；join 幂等 + 锁；WS token 仅 hello；invite preview；生产禁 CORS `*`；`ENV=test` 亦需自定义 `AUTH_SECRET`

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

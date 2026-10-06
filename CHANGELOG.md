# Changelog

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

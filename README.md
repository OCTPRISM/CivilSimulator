<p align="center">
  <img src="docs/brand/stone-axe.svg" alt="CivilSimulator" width="96" height="96" />
</p>

<p align="center">
  <strong>English</strong> · <a href="./README.zh-CN.md">中文</a>
</p>

<h1 align="center">CivilSimulator</h1>

<p align="center">
  <em>A playable civilization game — and a hands-on society simulation sandbox.</em>
</p>

<p align="center">
  Pick a world, step into a character, explore in 3D, and act with friends.<br />
  Or open the labs and run controllable experiments on population, markets, and public opinion.<br />
  Local LLM · walkable 3D · same-machine multiplayer.
</p>

<p align="center">
  <a href="https://github.com/OCTPRISM/CivilSimulator/releases/tag/v0.2.0"><img alt="release" src="https://img.shields.io/badge/release-v0.2.0-amber?style=flat-square" /></a>
  <img alt="audience" src="https://img.shields.io/badge/audience-local%20%2F%20invite--only-lightgrey?style=flat-square" />
  <img alt="status" src="https://img.shields.io/badge/status-Tech%20Preview-blue?style=flat-square" />
</p>

<p align="center">
  <a href="./docs/deploy-tech-preview.md">30-min setup</a>
  ·
  <a href="./CHANGELOG.md">Changelog</a>
  ·
  <a href="./README.zh-CN.md">中文说明</a>
</p>

<!-- Uniform 16:9 crops (960×540) — identical aspect for GitHub rendering -->
<p align="center">
  <img src="docs/brand/readme-heroes/hero-ancient.png" alt="Jiuzhou · Yonghe" width="270" height="152" />
  &nbsp;
  <img src="docs/brand/readme-heroes/hero-wuxia.png" alt="Jianghu · Wind Ferry" width="270" height="152" />
  &nbsp;
  <img src="docs/brand/readme-heroes/hero-scifi.png" alt="Ringbelt · 2387" width="270" height="152" />
</p>
<p align="center">
  <sub>Ancient · Wuxia · Sci-fi — same frame, different worlds</sub>
</p>

---

## Play it as a game

CivilSimulator is built first as a **free-roam narrative RPG**, not a chat demo:

| Gameplay | What you do |
|----------|-------------|
| **Choose a world / create a character** | Built-in ancient, wuxia, sci-fi seeds — or design custom civilization rules and start |
| **Walk the 3D scene** | WASD movement, talk to nearby NPCs, advance with choices or free-text actions |
| **Grow through skills & quests** | Skills, inventory, and task lines unfold as you play; system menu toggles TTS / BGM / scene art |
| **Co-op the same world** | Copy an invite link; friends join the same room and control their own characters |
| **Shape the situation** | Schedule world events or new NPCs, jump to a tick, rewrite the state of play |

Best for players who want immersion, sandbox exploration, and co-op in a living world.  
Power users can open the **Labs** for numeric what-if experiments on society.

---

## Run it as a society simulation

The home **Labs** surface (`/labs`) turns civilization into a **reproducible sandbox**. Shared loop: set background & events → simulate paths → export reports.

| Lab | What you simulate |
|-----|-------------------|
| **Population** | Disasters, migration, cognition, and long-run structural change |
| **Finance / economy** | Macro paths, city finance, firm valuation, retail scenarios |
| **Public opinion** | Issue spread, polarization, and feedback loops |
| **Weather / environment** | Climate shocks, regional emissions, and policy effects |

### How you intervene

You are not limited to watching charts — inject variables and rewrite trajectories:

| Method | Where | How |
|--------|-------|-----|
| **Timeline events** | Labs | Upload or write events (shock, scandal, market hit, viral issue…), set step, re-run |
| **Controlled contrasts** | Labs | Same civilization, different event sets — compare outcomes and export reports |
| **Shocks & levers** | Finance labs | Apply market or scenario shocks; watch indicators respond |
| **In-world injection** | Play | Schedule a **world event** or **new NPC** at a tick; narrative and society shift together |
| **Time skip / sleep** | Play | Jump ahead; or sleep your character while the world keeps evolving, then wake for a briefing |
| **Character actions** | Play | Dialogue, skills, quests, free input — first-person pressure on relationships and outcomes |

One line: **tune parameters in the labs; change destinies in the game** — research, teaching, or play.

---

## What else you get

- **Local intelligence**: Ollama by default; Mock mode for offline flow demos  
- **Create civilizations**: Edit rules, places, and factions; start from your own setup (M4)  
- **Atmosphere layer**: Scene art, browser TTS, procedural BGM  
- **Optional 3D generation**: Local Hunyuan3D pipeline; browse static assets when offline  
- **Continue after restart (Scheme B preview)**: Snapshots on exit / periodic ticks; resume from **My Worlds**

---

## 30-minute setup

Full steps: [Tech Preview deploy guide](./docs/deploy-tech-preview.md).

```bash
# Backend (:8000)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# Frontend (:3000) — separate terminal
cd frontend
cp .env.example .env.local
npm install && npm run dev
```

Open http://localhost:3000 → register / sign in → start **Civil Simulator**, or open **Labs** for society simulation.

| Goal | How |
|------|-----|
| Full local LLM | Install [Ollama](https://ollama.com), pull `qwen3.8:27b` and `nomic-embed-text` |
| No GPU / flow first | Set `LLM_PROVIDER=mock` in backend `.env` |
| Production-like | `ENV=production` and a custom `AUTH_SECRET` |

Env templates: [`backend/.env.example`](./backend/.env.example), [`frontend/.env.example`](./frontend/.env.example). Ports: **8000 / 3000**.

### Invite a second player

1. In Play, click **Invite** and copy the link  
2. They sign in, open `/join/{sessionId}`, and create a character  
3. Each acts independently; disconnect only affects their own character  

---

## Known limits (read first)

This is a **Tech Preview**:

| Limit | Notes |
|-------|-------|
| Continue (Scheme B) | Exit / periodic / shutdown writes snapshots; resume from **My Worlds** after restart (MVP: **playable**, not bit-perfect; very old / corrupt snapshots may fail) |
| Single process | Same-world multiplayer needs one uvicorn; **Redis / multi-worker not wired** (target v0.4) |
| Not a public GA | Local / invite-only; not open internet registration |
| Generator optional | Hunyuan3D offline is labeled; does not block core play |
| Hardware | Real LLM prefers a desktop; Mock is fine for light demos |

Roadmap: [Release plan](./wiki/v0.1-release-plan.md).

---

## Versions

| Version | Status | One-liner |
|---------|--------|-----------|
| **[v0.1.0-tech-preview](https://github.com/OCTPRISM/CivilSimulator/releases/tag/v0.1.0-tech-preview)** | Released | Playable + auth gates + honest ephemeral worlds |
| **[v0.2.0](https://github.com/OCTPRISM/CivilSimulator/releases/tag/v0.2.0)** | Released | My Worlds, onboarding, clearer errors |
| **v0.3.0** | In progress | Resume after restart (Scheme B snapshots) |
| **v0.4.0+** | Planned | Multiplayer ops + production hardening → v1.0 |

Done: M0 skeleton · M1 local LLM/Qdrant · M2 multiplayer room · M3 atmosphere media · M4 custom civilizations.

---

## Stack

- **Backend** FastAPI + WebSocket (Play / rooms require login + membership)  
- **Frontend** Next.js 14 + React Three Fiber  
- **Intelligence** Ollama (or OpenAI / Mock) + optional Qdrant  

```
CivilSimulator/
├── backend/     # API, world rooms, civilizations, labs
├── frontend/    # Play / create / invite / Labs / Generator
├── docs/        # Deploy & tech specs
└── wiki/        # Milestones & release roadmap
```

---

## Docs & verification

| Doc | Purpose |
|-----|---------|
| [Deploy guide](./docs/deploy-tech-preview.md) | Start + smoke |
| [Finance lab](./wiki/finance-lab.md) | Economic sandbox entry |
| [Release plan](./wiki/v0.1-release-plan.md) | Progress & five-version plan |
| [CHANGELOG](./CHANGELOG.md) | Version history |
| [Wiki index](./wiki/README.md) | M1–M4 topics |
| [Tech docs index](./docs/README.md) | UI / API specs |
| [中文 README](./README.zh-CN.md) | Chinese version |

```bash
cd backend && source .venv/bin/activate
QDRANT_ENABLED=false LLM_PROVIDER=mock pytest tests/ -q
```

---

<p align="center">
  <sub>Tech Preview · local-first · game + simulation still evolving</sub>
</p>

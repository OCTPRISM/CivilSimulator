"""Scheme B (v0.3) — persistable session snapshots + restore.

MVP goal: after process restart, a member can restore a playable room from
SQLite (player_id / inventory / location / clock roughly continuous).
Not bit-perfect (MemoryStore / finance_lab / RNG may degrade).
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any

from .layer2_civilization import World, InjectionQueue, MarketState
from .layer2_civilization.finance import FinanceShock, GoodState
from .layer2_civilization.finance_lab import FinanceLab
from .layer2_civilization.injections import InjectionKind, ScheduledInjection
from .layer2_civilization.stats import WorldStats
from .layer2_civilization.world import Faction, Location, WorldClock
from .layer3_agents import Agent, AgentKind, MemoryStore, PresenceState, Society, TaskBoard
from .layer3_agents.inventory import Item, ItemKind
from .layer3_agents.skills import Skill
from .layer3_agents.tasks import Task, TaskSource, TaskStatus
from .layer4_narrative import Director
from .layer4_narrative.scene import Beat, Page, Scene
from .layer4_narrative.tension import TensionTracker
from .layer6_persistence import EventStore

log = logging.getLogger(__name__)

SNAPSHOT_VERSION = 1
_RESTORE_LOCK = threading.Lock()


class RestoreError(ValueError):
    """User-facing restore failure (corrupt / incompatible / missing)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _snapshot_compatible(state: dict[str, Any]) -> bool:
    """True if restore_session would attempt hydrate (incl. legacy ver=0)."""
    ver = int(state.get("snapshot_version") or 0)
    if ver == SNAPSHOT_VERSION:
        return True
    if ver == 0 and state.get("world") and state.get("agents"):
        return True
    return False


def persistable_snapshot(sess: Any) -> dict[str, Any]:
    """Round-trippable state for Scheme B (superset of UI session_dict fields)."""
    from .session import page_dict, _agent_dict  # local import avoids cycles

    tick = sess.world.clock.tick
    agents_out = []
    for a in sess.society.all():
        a.ensure_skills(sess.world.genre)
        d = _agent_dict(a)
        # Persist raw skill cooldown clocks (UI ready flag is tick-relative).
        d["skills"] = [
            {
                "id": sk.id,
                "name": sk.name,
                "kind": sk.kind,
                "description": sk.description,
                "cooldown": sk.cooldown,
                "last_used_tick": sk.last_used_tick,
                "action_prompt": sk.action_prompt,
            }
            for sk in (a.skills or [])
        ]
        agents_out.append(d)

    tasks_by_player: dict[str, list[dict]] = {}
    for pid, tasks in getattr(sess.tasks, "_tasks", {}).items():
        tasks_by_player[pid] = [t.as_dict() for t in tasks]

    world = sess.world
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "id": sess.id,
        "seed_key": sess.seed_key or "",
        "user_id": sess.user_id,
        "player_ids": list(sess.player_ids),
        "world": {
            "id": world.id,
            "name": world.name,
            "genre": world.genre,
            "premise": world.premise,
            "rules": list(world.rules),
            "facts": list(world.facts),
            "agents": list(world.agents),
            "clock": {
                "era": world.clock.era,
                "tick": world.clock.tick,
                "start_hour": world.clock.start_hour,
            },
            "locations": [dict(loc.__dict__) for loc in world.locations.values()],
            "factions": [dict(fac.__dict__) for fac in world.factions.values()],
        },
        "agents": agents_out,
        "director": {
            "page_no": sess.director.page_no,
            "chapter": sess.director.chapter,
            "stats": sess.director.stats.snapshot(),
            "tension_curve": sess.director.tension.to_curve(),
            "pending_injection": sess.director.pending_injection,
        },
        "finance": sess.finance.snapshot() if sess.finance else None,
        "injections": sess.injections.snapshot(),
        "tasks_by_player": tasks_by_player,
        "pages": [page_dict(p) for p in sess.pages[-80:]],
        "tick": tick,
        "page_no": int(getattr(sess.director, "page_no", 0) or 0),
    }


def force_save_snapshot(sess: Any) -> None:
    """Always write a snapshot (sleep / exit / shutdown / step)."""
    state = persistable_snapshot(sess)
    sess.events.save_snapshot(sess.world.clock.tick, state)


def maybe_save_snapshot(sess: Any) -> bool:
    """Periodic snapshot: every N world ticks **or** after narrative pages.

    Narrative ``step`` often leaves ``clock.tick`` at 0 under mock / quiet sims;
    saving after pages keeps Scheme B progress durable without requiring sleep.
    """
    every = EventStore.SNAPSHOT_EVERY
    tick = int(sess.world.clock.tick or 0)
    page_no = int(getattr(sess.director, "page_no", 0) or 0)
    # Page progress is the main play signal — always persist after a page.
    if page_no > 0:
        force_save_snapshot(sess)
        return True
    if tick > 0 and tick % every == 0:
        force_save_snapshot(sess)
        return True
    return False


def snapshot_exists(session_id: str) -> bool:
    return EventStore(session_id).latest_snapshot() is not None


def latest_snapshot_meta(session_id: str) -> dict[str, Any] | None:
    hit = EventStore(session_id).latest_snapshot()
    if not hit:
        return None
    tick, state = hit
    ver = int(state.get("snapshot_version") or 0)
    agents = state.get("agents") or []
    player_ids = list(state.get("player_ids") or [])
    # Best-effort character name for My Worlds when room is not live.
    character_name = None
    if player_ids and isinstance(agents, list):
        for ad in agents:
            if isinstance(ad, dict) and ad.get("id") == player_ids[0]:
                character_name = ad.get("name")
                break
    return {
        "tick": tick,
        "snapshot_version": ver,
        "compatible": _snapshot_compatible(state),
        "world_name": (state.get("world") or {}).get("name"),
        "seed_key": state.get("seed_key") or "",
        "player_ids": player_ids,
        "character_name": character_name,
        "page_no": state.get("page_no") or (state.get("director") or {}).get("page_no"),
        "genre": (state.get("world") or {}).get("genre"),
    }


def _item_from_dict(d: dict) -> Item:
    kind_raw = d.get("kind") or "misc"
    try:
        kind = ItemKind(kind_raw)
    except ValueError:
        kind = ItemKind.MISC
    return Item(
        id=str(d.get("id") or "item_x"),
        name=str(d.get("name") or "物"),
        kind=kind,
        qty=float(d.get("qty") or 1),
        meta=dict(d.get("meta") or {}),
    )


def _skill_from_dict(d: dict) -> Skill:
    return Skill(
        id=str(d.get("id") or "skill_x"),
        name=str(d.get("name") or "技能"),
        kind=str(d.get("kind") or "basic"),
        description=str(d.get("description") or ""),
        cooldown=int(d.get("cooldown") or 0),
        last_used_tick=int(d["last_used_tick"]) if d.get("last_used_tick") is not None else -999,
        action_prompt=str(d.get("action_prompt") or d.get("name") or ""),
    )


def _agent_from_dict(d: dict) -> Agent:
    kind_raw = d.get("kind") or "npc"
    try:
        kind = AgentKind(kind_raw)
    except ValueError:
        kind = AgentKind.NPC
    presence_raw = d.get("presence") or "active"
    try:
        presence = PresenceState(presence_raw)
    except ValueError:
        presence = PresenceState.ACTIVE
    inv = [_item_from_dict(x) for x in (d.get("inventory") or []) if isinstance(x, dict)]
    skills = [_skill_from_dict(x) for x in (d.get("skills") or []) if isinstance(x, dict)]
    return Agent(
        id=str(d["id"]),
        name=str(d.get("name") or "无名"),
        kind=kind,
        persona=str(d.get("persona") or ""),
        goals=list(d.get("goals") or []),
        traits=list(d.get("traits") or []),
        location_id=d.get("location_id"),
        relations=dict(d.get("relations") or {}),
        avatar=str(d.get("avatar") or ""),
        appearance=dict(d.get("appearance") or {}),
        profession=str(d.get("profession") or ""),
        schedule=list(d.get("schedule") or []),
        economy=dict(d.get("economy") or {}),
        current_activity=str(d.get("current_activity") or ""),
        savings=float(d.get("savings") or 0),
        today_income=float(d.get("today_income") or 0),
        today_customers=int(d.get("today_customers") or 0),
        last_meal_tier=str(d.get("last_meal_tier") or ""),
        presence=presence,
        dormant_since_tick=d.get("dormant_since_tick"),
        last_observed_tick=int(d.get("last_observed_tick") or 0),
        offline_mode=str(d.get("offline_mode") or ""),
        offline_rationale=str(d.get("offline_rationale") or ""),
        world_x=float(d.get("world_x") or 0),
        world_z=float(d.get("world_z") or 0),
        behavior=str(d.get("behavior") or "idle"),
        inventory=inv,
        equipment=dict(d.get("equipment") or {}),
        skills=skills,
    )


def _world_from_dict(d: dict) -> World:
    clock_d = d.get("clock") or {}
    start_hour = int(clock_d["start_hour"]) if clock_d.get("start_hour") is not None else 6
    # Legacy UI snapshots stored hour/day without start_hour — approximate.
    if "start_hour" not in clock_d and "hour" in clock_d and "tick" in clock_d:
        tick = int(clock_d.get("tick") or 0)
        hour = int(clock_d.get("hour") or 6)
        start_hour = (hour - (tick % 24)) % 24
    clock = WorldClock(
        era=str(clock_d.get("era") or "起始"),
        tick=int(clock_d.get("tick") or 0),
        start_hour=start_hour,
    )
    world = World(
        id=str(d.get("id") or "world_x"),
        name=str(d.get("name") or "未命名世界"),
        genre=str(d.get("genre") or "ancient"),
        premise=str(d.get("premise") or ""),
        rules=list(d.get("rules") or []),
        clock=clock,
        facts=list(d.get("facts") or []),
        agents=list(d.get("agents") or []),
    )
    for loc in d.get("locations") or []:
        if not isinstance(loc, dict) or not loc.get("id"):
            continue
        world.locations[loc["id"]] = Location(
            id=str(loc["id"]),
            name=str(loc.get("name") or ""),
            description=str(loc.get("description") or ""),
            tags=list(loc.get("tags") or []),
        )
    for fac in d.get("factions") or []:
        if not isinstance(fac, dict) or not fac.get("id"):
            continue
        world.factions[fac["id"]] = Faction(
            id=str(fac["id"]),
            name=str(fac.get("name") or ""),
            ideology=str(fac.get("ideology") or ""),
            relations=dict(fac.get("relations") or {}),
        )
    return world


def _stats_from_dict(d: dict | None) -> WorldStats:
    d = d or {}
    stats = WorldStats(
        politics=float(d.get("politics") or 60),
        economy=float(d.get("economy") or 55),
        livelihood=float(d.get("livelihood") or 60),
        military=float(d.get("military") or 40),
        environment=float(d.get("environment") or 65),
        summary=dict(d.get("summary") or WorldStats().summary),
    )
    hist = d.get("history") or []
    stats.history = deque(hist[-64:], maxlen=64)
    return stats


def _tension_from_curve(curve: list | None) -> TensionTracker:
    t = TensionTracker()
    for v in (curve or [])[-4:]:
        try:
            t.history.append(float(v))
        except (TypeError, ValueError):
            pass
    return t


def _page_from_dict(d: dict) -> Page:
    scene_d = d.get("scene") or {}
    beats = [
        Beat(
            kind=b.get("kind") or "narration",  # type: ignore[arg-type]
            speaker=b.get("speaker"),
            content=str(b.get("content") or ""),
        )
        for b in (d.get("beats") or [])
        if isinstance(b, dict)
    ]
    return Page(
        page_no=int(d.get("page_no") or 1),
        chapter=str(d.get("chapter") or ""),
        scene=Scene(
            location_id=str(scene_d.get("location_id") or ""),
            location_name=str(scene_d.get("location_name") or ""),
            summary=str(scene_d.get("summary") or ""),
            present_agent_ids=list(scene_d.get("present_agent_ids") or []),
        ),
        beats=beats,
        choices=list(d.get("choices") or []),
        tension=float(d.get("tension") or 0),
    )


def _tasks_from_dict(raw: dict | None) -> TaskBoard:
    board = TaskBoard()
    for pid, rows in (raw or {}).items():
        for t in rows or []:
            if not isinstance(t, dict):
                continue
            try:
                source = TaskSource(t.get("source") or "self")
            except ValueError:
                source = TaskSource.SELF
            try:
                status = TaskStatus(t.get("status") or "open")
            except ValueError:
                status = TaskStatus.OPEN
            board.add(pid, Task(
                id=str(t.get("id") or "task_x"),
                title=str(t.get("title") or ""),
                description=str(t.get("description") or ""),
                source=source,
                status=status,
                rewards=dict(t.get("rewards") or {}),
                tick_created=int(t.get("tick_created") or 0),
                tick_deadline=t.get("tick_deadline"),
                location_id=t.get("location_id"),
                keywords=list(t.get("keywords") or []),
            ))
    return board


def _injections_from_dict(rows: list | None) -> InjectionQueue:
    q = InjectionQueue()
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        try:
            kind = InjectionKind(r.get("kind") or "event")
        except ValueError:
            kind = InjectionKind.EVENT
        q.items.append(ScheduledInjection(
            id=str(r.get("id") or "inj_x"),
            tick=int(r.get("tick") or 0),
            kind=kind,
            payload=dict(r.get("payload") or {}),
            fired=bool(r.get("fired")),
        ))
    q.items.sort(key=lambda x: x.tick)
    return q


def _finance_from_dict(d: dict | None, *, seed: str, society: Society) -> MarketState | None:
    if not d:
        return None
    m = MarketState(seed=str(d.get("seed") or seed), tick=int(d.get("tick") or 0))
    for g in d.get("goods") or []:
        if not isinstance(g, dict) or not g.get("id"):
            continue
        m.goods[g["id"]] = GoodState(
            id=str(g["id"]),
            name=str(g.get("name") or g["id"]),
            base=float(g.get("base") or 1),
            price=float(g.get("price") or g.get("base") or 1),
            inventory=float(g.get("inventory") or 80),
            supply_tick=float(g.get("supply_tick") or 0),
            demand_tick=float(g.get("demand_tick") or 0),
            suppliers=list(g.get("suppliers") or []),
        )
    for s in d.get("shocks") or []:
        if not isinstance(s, dict):
            continue
        m.shocks.append(FinanceShock(
            id=str(s.get("id") or "shock_x"),
            kind=str(s.get("kind") or "price"),
            good_id=str(s.get("good_id") or "*"),
            magnitude=float(s.get("magnitude") or 0),
            remaining=int(s.get("remaining") or 0),
            note=str(s.get("note") or ""),
        ))
    hist = d.get("history") or []
    m.history = deque(hist[-256:], maxlen=256)
    m.last_events = list(d.get("last_events") or [])
    m.money_supply = float(d.get("money_supply") or 0)
    m.price_index = float(d.get("price_index") or 100)
    m.inflation = float(d.get("inflation") or 0)
    m.velocity = float(d.get("velocity") or 0)
    m.gini = float(d.get("gini") or 0)
    m.volume = float(d.get("volume") or 0)
    if not m.goods:
        # Fallback recreate catalog if snapshot lacked goods.
        return MarketState.create(genre="ancient", seed=seed, society=society)
    return m


def _agents_need_position_init(society: Society) -> bool:
    """True if all agents sit at origin — likely missing coords in snapshot."""
    agents = list(society.all())
    if not agents:
        return False
    return all(
        abs(float(getattr(a, "world_x", 0) or 0)) < 1e-6
        and abs(float(getattr(a, "world_z", 0) or 0)) < 1e-6
        for a in agents
    )


def restore_session(session_id: str):
    """Rebuild a live Session from the latest compatible SQLite snapshot (B-2)."""
    from .session import Session, _SESSIONS, _init_agent_positions

    existing = _SESSIONS.get(session_id)
    if existing is not None:
        return existing

    with _RESTORE_LOCK:
        existing = _SESSIONS.get(session_id)
        if existing is not None:
            return existing

        es = EventStore(session_id)
        hit = es.latest_snapshot()
        if not hit:
            raise RestoreError("没有可用快照，无法续玩（创建或推进幕后会自动保存）")
        tick, state = hit
        if not isinstance(state, dict):
            raise RestoreError("快照损坏：状态不是对象")

        ver = int(state.get("snapshot_version") or 0)
        if ver != SNAPSHOT_VERSION:
            # Attempt soft hydrate for pre-v1 UI session_dict snapshots.
            if ver == 0 and state.get("world") and state.get("agents"):
                log.warning("Restoring legacy snapshot (no version) for %s", session_id)
                state = {**state, "snapshot_version": SNAPSHOT_VERSION, "id": session_id}
            else:
                raise RestoreError(
                    f"快照版本不兼容（got {ver}, need {SNAPSHOT_VERSION}）。请新建世界。"
                )

        try:
            world_d = state.get("world")
            if not isinstance(world_d, dict):
                raise RestoreError("快照缺少世界数据")
            world = _world_from_dict(world_d)

            society = Society()
            for ad in state.get("agents") or []:
                if isinstance(ad, dict) and ad.get("id"):
                    society.add(_agent_from_dict(ad))

            player_ids = [p for p in (state.get("player_ids") or []) if society.get(p)]
            if not player_ids:
                player_ids = [a.id for a in society.all() if a.kind == AgentKind.PLAYER]
            if not player_ids:
                raise RestoreError("快照中没有可操控角色")

            director_d = state.get("director") or {}
            director = Director(
                page_no=int(director_d.get("page_no") or len(state.get("pages") or [])),
                chapter=str(director_d.get("chapter") or "第一章 · 续"),
                tension=_tension_from_curve(
                    director_d.get("tension_curve") or state.get("tension_curve"),
                ),
                stats=_stats_from_dict(director_d.get("stats") or state.get("stats")),
                pending_injection=director_d.get("pending_injection"),
            )

            memory = MemoryStore(session_id=session_id)
            tasks = _tasks_from_dict(state.get("tasks_by_player"))
            injections = _injections_from_dict(state.get("injections"))

            seed_key = str(state.get("seed_key") or "")
            finance = _finance_from_dict(
                state.get("finance"),
                seed=f"{seed_key}:{session_id}",
                society=society,
            )
            finance_lab = FinanceLab.create(
                seed=f"{seed_key}:{session_id}:lab",
                genre=world.genre,
                world_name=world.name,
                civilization_key=seed_key or world.genre,
                user_id=state.get("user_id"),
            )

            pages = [
                _page_from_dict(p) for p in (state.get("pages") or []) if isinstance(p, dict)
            ]

            sess = Session(
                id=session_id,
                world=world,
                society=society,
                memory=memory,
                director=director,
                events=es,
                injections=injections,
                tasks=tasks,
                finance=finance,
                finance_lab=finance_lab,
                player_ids=player_ids,
                pages=pages,
                user_id=state.get("user_id"),
                seed_key=seed_key,
            )
            sess._loc_snapshot = {
                a.id: (a.location_id or "") for a in society.all()
            }
            # Preserve restored coords; only seed from map when snapshot lacked them.
            if _agents_need_position_init(society):
                try:
                    _init_agent_positions(sess)
                except Exception:
                    log.exception("Position init failed for restored %s", session_id)
            else:
                for a in society.all():
                    a.target_x = float(getattr(a, "world_x", 0) or 0)
                    a.target_z = float(getattr(a, "world_z", 0) or 0)
            _SESSIONS[session_id] = sess
            log.info(
                "Restored session %s from snapshot tick=%s players=%s pages=%s",
                session_id, tick, len(player_ids), len(pages),
            )
            return sess
        except RestoreError:
            raise
        except Exception as exc:
            log.exception("Failed to restore session %s", session_id)
            raise RestoreError(f"快照无法加载：{type(exc).__name__}") from exc


def flush_all_sessions() -> int:
    """Force-save every live room (process shutdown)."""
    from .session import _SESSIONS

    n = 0
    for sess in list(_SESSIONS.values()):
        try:
            force_save_snapshot(sess)
            n += 1
        except Exception:
            log.exception("Failed to flush snapshot for %s", getattr(sess, "id", "?"))
    return n

"""Session = one *world room* + 1..N players + N NPCs.

Tech Preview / through v0.3: in-memory registry on a **single** uvicorn
process; Scheme B snapshots in SQLite allow restore after restart.
``REDIS_URL`` in config is reserved for v0.4 multi-worker pub/sub and is
**not** wired here.

Dormancy: player agents go dormant on offline / explicit sleep. A background
loop advances the world while any player is dormant; those players miss
``world_event`` rows and receive a fragmentary wake briefing on return.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from uuid import uuid4

from .config import get_settings
from .layer1_foundation import LLM, get_llm
from .layer2_civilization import World, apply_injections, InjectionQueue, MarketState
from .layer2_civilization.live_simulation import infer_live_tick, apply_live_tick
from .layer2_civilization.finance_lab import FinanceLab
from .layer2_civilization.player_catalog import spawn_player_from_variant
from .layer3_agents import (
    Agent, AgentKind, MemoryStore, PresenceState, Society,
    TaskBoard, inventory_to_dict,
)
from .layer3_agents.offline_choice import decide_offline_mode, default_wander_schedule
from .layer3_agents.skills import skills_to_dict
from .layer3_agents.tasks import story_task_from_event
from .layer4_narrative import Director, Page, compose_wake_briefing
from .layer4_narrative.wake_briefing import compose_proxy_return_briefing
from .layer6_persistence import EventStore
from .layer6_persistence.users import link_session_to_user


@dataclass
class Session:
    id: str
    world: World
    society: Society
    memory: MemoryStore
    director: Director
    events: EventStore
    injections: InjectionQueue = field(default_factory=InjectionQueue)
    tasks: TaskBoard = field(default_factory=TaskBoard)
    finance: MarketState | None = None
    finance_lab: FinanceLab | None = None
    player_ids: list[str] = field(default_factory=list)
    pages: list[Page] = field(default_factory=list)
    subscribers: list["asyncio.Queue[dict]"] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    user_id: str | None = None
    seed_key: str = ""
    # MP-1: room capacity (inclusive of host). Clamped on create.
    max_players: int = 8
    simulation_running: bool = False
    simulation_last_model: str = ""
    simulation_last_error: str = ""
    simulation_last_tick: int = -1
    simulation_last_reasoning: str = ""
    # location_id snapshots for wake npc_shifts
    _loc_snapshot: dict[str, str] = field(default_factory=dict)

    @property
    def llm(self) -> LLM:
        return get_llm()

    @property
    def primary_player_id(self) -> str | None:
        return self.player_ids[0] if self.player_ids else None

    def any_player_dormant(self) -> bool:
        return any(
            (a := self.society.get(pid)) is not None and a.is_dormant()
            for pid in self.player_ids
        )

    def any_player_offline(self) -> bool:
        return any(
            (a := self.society.get(pid)) is not None and a.is_offline()
            for pid in self.player_ids
        )


_SESSIONS: dict[str, Session] = {}
_BG_TASK: asyncio.Task | None = None


def _init_agent_positions(sess: Session) -> None:
    """Initialize visual coordinates without making behavioral decisions."""
    from .layer2_civilization.map_meta import loc_id_coords
    for agent in sess.society.all():
        x, z = loc_id_coords(sess.world.genre, sess.world, agent.location_id)
        agent.world_x = x
        agent.world_z = z
        agent.target_x = x
        agent.target_z = z


def process_injections(sess: Session) -> list[dict]:
    """Fire user-scheduled events/characters at the current tick."""
    tick = sess.world.clock.tick
    fired = apply_injections(sess.injections, tick, sess.world, sess.society)
    for rec in fired:
        sess.events.append("injection_fired", rec, tick=tick)
        if rec.get("kind") == "event":
            sess.events.append("world_event", {
                "summary": rec.get("summary"),
                "kind": "custom",
                "importance": rec.get("importance", 0.85),
                "location_id": rec.get("location_id"),
                "observed_by": [],
                "actor_ids": [],
            }, tick=tick)
            for pid in sess.player_ids:
                title, desc, rewards = story_task_from_event(
                    rec.get("summary", ""), tick, rec.get("location_id"),
                )
                sess.tasks.create_story_task(
                    pid, title=title, description=desc, tick=tick,
                    location_id=rec.get("location_id"), rewards=rewards,
                )
        elif rec.get("kind") == "character":
            ag = sess.society.get(rec.get("agent_id", ""))
            if ag:
                sess.events.append("agent_added", {"agent": _agent_dict(ag)}, tick=tick)
    return fired


def _sync_player_tasks(sess: Session, player: Agent, player_input: str | None) -> list[dict]:
    if player.profession:
        sess.tasks.ensure_work_task(player.id, player.profession, sess.world.clock.tick)
    completed = []
    if player_input:
        done, inv, sav = sess.tasks.try_auto_complete_from_input(
            player.id, player_input,
            inventory=list(player.inventory),
            savings=player.savings,
            profession=player.profession,
            economy=player.economy or {},
        )
        player.inventory = inv
        player.savings = sav
        for t in done:
            completed.append(t.as_dict())
            sess.events.append("task_completed", {
                "player_id": player.id, "task": t.as_dict(),
            }, tick=sess.world.clock.tick)
    return completed


# ---------- create / join ----------
async def create_session(
    seed_key: str,
    player_description: str = "",
    *,
    category_key: str | None = None,
    variant_key: str | None = None,
    skin: str | None = None,
    user_id: str | None = None,
    max_players: int = 8,
) -> Session:
    from .layer2_civilization.civilization_resolver import load_seed_any, resolve_variant_any

    cap = max(2, min(16, int(max_players or 8)))
    seed = load_seed_any(seed_key, user_id=user_id)
    world = seed.materialize()
    society = Society()
    sid = f"sess_{uuid4().hex[:10]}"
    memory = MemoryStore(session_id=sid)
    director = Director()
    events = EventStore(sid)

    sess = Session(
        id=sid, world=world, society=society, memory=memory,
        director=director, events=events, user_id=user_id, seed_key=seed_key,
        max_players=cap,
    )

    events.append("world_created", {
        "seed": seed_key, "world": world.snapshot(), "user_id": user_id,
    }, tick=world.clock.tick)

    npcs = await director.generate_npcs_from_seed(sess.llm, world, seed.npc_archetypes)
    for n in npcs:
        n.ensure_skills(world.genre)
        n.init_inventory_from_economy()
        society.add(n)
        world.agents.append(n.id)
    for n in npcs:
        events.append("agent_added", {"agent": _agent_dict(n)}, tick=world.clock.tick)

    player: Agent
    if category_key and variant_key:
        variant = resolve_variant_any(seed_key, category_key, variant_key, user_id=user_id)
        if not variant:
            raise ValueError("角色形象不存在")
        player = spawn_player_from_variant(world, variant, seed_key=seed_key, skin=skin)
    elif player_description.strip():
        player = await director.generate_player_agent(sess.llm, world, player_description)
    else:
        raise ValueError("请选择角色或填写描述")

    player.ensure_skills(world.genre)
    if not player.inventory:
        player.init_inventory_from_economy()
    society.add(player)
    world.agents.append(player.id)
    sess.player_ids.append(player.id)
    if player.profession:
        sess.tasks.ensure_work_task(player.id, player.profession, world.clock.tick)
    events.append("agent_added", {"agent": _agent_dict(player), "player": True},
                  tick=world.clock.tick)

    sess.finance = MarketState.create(
        genre=world.genre,
        seed=f"{seed_key}:{sid}",
        society=society,
    )
    sess.finance_lab = FinanceLab.create(
        seed=f"{seed_key}:{sid}:lab",
        genre=world.genre,
        world_name=world.name,
        civilization_key=seed_key,
        user_id=user_id,
    )
    # Align macro economy gauge with market price index (0–100 scale)
    sess.director.stats.economy = max(5.0, min(95.0, sess.finance.price_index / 2.0))

    _init_agent_positions(sess)
    _SESSIONS[sid] = sess
    if user_id:
        link_session_to_user(
            sid,
            user_id,
            seed_key,
            player_id=player.id,
            world_name=world.name,
            character_name=player.name,
        )
    return sess


async def join_session(
    sid: str,
    player_description: str,
    *,
    user_id: str | None = None,
    max_players: int | None = None,
) -> tuple[Session, Agent]:
    sess = _SESSIONS.get(sid)
    if not sess:
        # B-2: invitees / re-join after process restart hydrate from snapshot.
        try:
            from .session_persist import RestoreError, restore_session
            sess = restore_session(sid)
        except RestoreError as e:
            raise KeyError(str(e.message) if hasattr(e, "message") else "session not found") from e
        except Exception:
            raise KeyError("session not found")

    # R0: re-join must be idempotent — same user keeps the same player binding.
    if user_id:
        from .layer6_persistence.users import get_member_player_id

        existing_pid = get_member_player_id(sid, user_id)
        if existing_pid:
            existing = sess.society.get(existing_pid)
            if existing is not None and existing_pid in sess.player_ids:
                return sess, existing

    cap = int(max_players) if max_players is not None else int(getattr(sess, "max_players", 8) or 8)
    # Hold the session lock across generation + roster mutation so concurrent
    # joins cannot exceed max_players (R0 multiplayer integrity).
    async with sess.lock:
        if len(sess.player_ids) >= cap:
            raise ValueError(f"房间已满（最多 {cap} 人）")
        # Re-check membership under lock (another request may have just linked).
        if user_id:
            from .layer6_persistence.users import get_member_player_id

            existing_pid = get_member_player_id(sid, user_id)
            if existing_pid:
                existing = sess.society.get(existing_pid)
                if existing is not None and existing_pid in sess.player_ids:
                    return sess, existing

        player = await sess.director.generate_player_agent(
            sess.llm, sess.world, player_description
        )
        player.ensure_skills(sess.world.genre)
        player.init_inventory_from_economy()
        # Spawn near the host / primary player when possible.
        host = sess.society.get(sess.primary_player_id) if sess.primary_player_id else None
        if host is not None:
            player.location_id = host.location_id
            player.world_x = float(getattr(host, "world_x", 0.0)) + 1.5
            player.world_z = float(getattr(host, "world_z", 0.0)) + 1.5
        sess.society.add(player)
        sess.world.agents.append(player.id)
        sess.player_ids.append(player.id)
        sess.events.append(
            "agent_added",
            {"agent": _agent_dict(player), "player": True},
            tick=sess.world.clock.tick,
        )
        if user_id:
            from .layer6_persistence.users import link_session_member
            link_session_member(
                sid,
                user_id,
                player_id=player.id,
                seed_key=sess.seed_key or "",
                world_name=sess.world.name,
                character_name=player.name,
            )
        try:
            from .session_persist import force_save_snapshot
            force_save_snapshot(sess)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to force-save snapshot after join for %s", sess.id,
            )

    _fanout(sess, {
        "type": "player_joined",
        "player_id": player.id,
        "agent": _agent_dict(player),
        "session": session_dict(sess),
        "tick": sess.world.clock.tick,
    })
    _fanout(sess, {
        "type": "agent_transform",
        "transform": {**_agent_transform_dict(player), "tick": sess.world.clock.tick},
        "tick": sess.world.clock.tick,
    })
    return sess, player


# ---------- room ops (v0.4 MP) ----------
def kick_player(sess: Session, *, host_user_id: str, target_player_id: str) -> dict:
    """Host removes a player from the live room (MP-2)."""
    from .layer6_persistence.users import (
        find_member_by_player_id,
        get_session_host_user_id,
        unlink_session_membership,
    )

    host = get_session_host_user_id(sess.id) or sess.user_id
    if not host or host != host_user_id:
        raise PermissionError("仅房主可踢人")
    tid = (target_player_id or "").strip()
    if not tid or tid not in sess.player_ids:
        raise ValueError("目标玩家不在房间内")
    if len(sess.player_ids) <= 1:
        raise ValueError("不能踢出房间内唯一玩家")
    # Host cannot kick their own bound character via this API (use leave later).
    member = find_member_by_player_id(sess.id, tid)
    if member and member["user_id"] == host_user_id:
        raise ValueError("不能踢出自己，请转让房主后离开")

    sess.player_ids = [p for p in sess.player_ids if p != tid]
    # Keep agent in society as NPC shell so world continuity is softer; demote kind.
    agent = sess.society.get(tid)
    if agent is not None:
        from .layer3_agents import AgentKind
        agent.kind = AgentKind.NPC
    if member:
        unlink_session_membership(sess.id, member["user_id"])
    payload = {
        "type": "player_kicked",
        "player_id": tid,
        "by_user_id": host_user_id,
        "session": session_dict(sess),
        "tick": sess.world.clock.tick,
    }
    _fanout(sess, payload)
    try:
        from .session_persist import force_save_snapshot
        force_save_snapshot(sess)
    except Exception:
        pass
    return payload


def transfer_host(sess: Session, *, host_user_id: str, to_user_id: str) -> dict:
    """Transfer room ownership to another member (MP-2)."""
    from .layer6_persistence.users import (
        get_session_host_user_id,
        is_session_member,
        transfer_session_host,
    )

    host = get_session_host_user_id(sess.id) or sess.user_id
    if not host or host != host_user_id:
        raise PermissionError("仅房主可转让")
    tid = (to_user_id or "").strip()
    if not tid or tid == host_user_id:
        raise ValueError("请指定其他成员为新房主")
    if not is_session_member(sess.id, tid):
        raise ValueError("目标用户不是房间成员")
    transfer_session_host(sess.id, from_user_id=host_user_id, to_user_id=tid)
    sess.user_id = tid
    payload = {
        "type": "host_transferred",
        "from_user_id": host_user_id,
        "to_user_id": tid,
        "session": session_dict(sess),
        "tick": sess.world.clock.tick,
    }
    _fanout(sess, payload)
    try:
        from .session_persist import force_save_snapshot
        force_save_snapshot(sess)
    except Exception:
        pass
    return payload


# ---------- presence / dormancy ----------
def _resolve_player(sess: Session, player_id: str | None) -> Agent:
    pid = player_id or sess.primary_player_id
    if pid is None:
        raise RuntimeError("session has no player agent")
    player = sess.society.get(pid)
    if player is None:
        raise RuntimeError(f"player {pid} not in session")
    return player


def _fanout(sess: Session, payload: dict) -> None:
    for q in list(sess.subscribers):
        try:
            q.put_nowait(payload)
        except Exception:
            pass


def _agent_transform_dict(agent: Agent) -> dict:
    return {
        "agent_id": agent.id,
        "world_x": round(float(getattr(agent, "world_x", 0.0)), 4),
        "world_z": round(float(getattr(agent, "world_z", 0.0)), 4),
        "behavior": getattr(agent, "behavior", "idle"),
    }


def _fanout_agent_transforms(sess: Session) -> None:
    transforms = [_agent_transform_dict(a) for a in sess.society.all()]
    if not transforms:
        return
    _fanout(sess, {
        "type": "agent_transforms",
        "transforms": transforms,
        "tick": sess.world.clock.tick,
    })


async def move_player(
    sess: Session,
    *,
    player_id: str | None = None,
    world_x: float = 0.0,
    world_z: float = 0.0,
) -> dict:
    """Explicit player movement (v1.4 UI-010 exploration). Does not wake dormant agents."""
    player = _resolve_player(sess, player_id)
    if player.is_dormant() or player.is_offline():
        raise RuntimeError("player not active")
    caps = sess.world.snapshot().get("visual_capabilities") or {}
    if not caps.get("exploration_enabled"):
        raise RuntimeError("exploration not enabled for this world")

    wx = max(-1.0, min(1.0, float(world_x)))
    wz = max(-1.0, min(1.0, float(world_z)))
    async with sess.lock:
        player.world_x = wx
        player.world_z = wz
        player.target_x = wx
        player.target_z = wz
        player.behavior = "walk"
        tick = sess.world.clock.tick
        transform = {**_agent_transform_dict(player), "tick": tick}
    _fanout(sess, {"type": "agent_transform", "transform": transform, "tick": tick})
    return transform


async def heartbeat(sess: Session, *, player_id: str | None = None) -> Agent:
    """Keep presence alive. Does not wake a dormant agent."""
    player = _resolve_player(sess, player_id)
    player.last_heartbeat_ts = time.time()
    return player


async def sleep_player(sess: Session, *, player_id: str | None = None,
                       reason: str = "offline") -> Agent:
    """User goes offline: character autonomously chooses sleep vs NPC-proxy."""
    player = _resolve_player(sess, player_id)
    if player.is_offline():
        return player

    tick = sess.world.clock.tick
    mode, rationale = await decide_offline_mode(
        sess.llm, sess.world, player, reason=reason,
    )
    if mode == "proxy":
        if not player.schedule:
            player.schedule = default_wander_schedule(sess.world, player)
        player.enter_proxy(tick, rationale=rationale)
        sess.events.append(
            "player_proxy",
            {
                "player_id": player.id, "reason": reason,
                "since_tick": tick, "rationale": rationale,
            },
            tick=tick,
        )
        _fanout(sess, {
            "type": "presence",
            "player_id": player.id,
            "presence": PresenceState.PROXY.value,
            "reason": reason,
            "rationale": rationale,
            "tick": tick,
        })
    else:
        player.enter_dormant(tick, rationale=rationale)
        sess.events.append(
            "player_dormant",
            {
                "player_id": player.id, "reason": reason,
                "since_tick": tick, "rationale": rationale,
            },
            tick=tick,
        )
        _fanout(sess, {
            "type": "presence",
            "player_id": player.id,
            "presence": PresenceState.DORMANT.value,
            "reason": reason,
            "rationale": rationale,
            "tick": tick,
        })
    # B-1: flush a restorable snapshot whenever a player goes offline / exits.
    try:
        from .session_persist import force_save_snapshot
        force_save_snapshot(sess)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to force-save snapshot on sleep for %s", sess.id,
        )
    return player


async def wake_player(sess: Session, *, player_id: str | None = None) -> dict:
    """Leave offline mode (sleep or proxy) and compose a return briefing."""
    player = _resolve_player(sess, player_id)
    async with sess.lock:
        was_mode = player.offline_mode or (
            "sleep" if player.is_dormant() else "proxy" if player.is_proxy() else ""
        )
        since = player.wake(sess.world.clock.tick)
        if since is None:
            player.last_heartbeat_ts = time.time()
            return {
                "already_awake": True,
                "presence": PresenceState.ACTIVE.value,
                "briefing": None,
                "offline_mode": was_mode or None,
                "session": session_dict(sess, viewer_id=player.id),
            }

        npc_shifts: list[dict] = []
        for npc in sess.society.npcs():
            prev = sess._loc_snapshot.get(npc.id)
            cur = npc.location_id or ""
            if prev and prev != cur:
                loc_by_id = sess.world.locations
                npc_shifts.append({
                    "name": npc.name,
                    "from": loc_by_id[prev].name if prev in loc_by_id else "?",
                    "to": loc_by_id[cur].name if cur in loc_by_id else "?",
                    "activity": npc.current_activity or "",
                })
            sess._loc_snapshot[npc.id] = cur
        stats_summary = dict(sess.director.stats.summary)
        from_tick = since
        rationale = player.offline_rationale

    if was_mode == "proxy":
        briefing = await compose_proxy_return_briefing(
            sess.llm, sess.world, player, sess.memory, sess.events,
            from_tick=from_tick,
            npc_shifts=npc_shifts,
            stats_summary=stats_summary,
            rationale=rationale,
        )
    else:
        briefing = await compose_wake_briefing(
            sess.llm, sess.world, player, sess.memory, sess.events,
            from_tick=from_tick,
            npc_shifts=npc_shifts,
            stats_summary=stats_summary,
        )

    async with sess.lock:
        sess.events.append(
            "player_awake",
            {
                "player_id": player.id,
                "from_tick": from_tick,
                "to_tick": sess.world.clock.tick,
                "ticks_asleep": briefing.ticks_asleep,
                "narrative": briefing.narrative,
                "offline_mode": was_mode,
            },
            tick=sess.world.clock.tick,
        )
        snap = session_dict(sess)

    payload = {
        "type": "wake",
        "player_id": player.id,
        "briefing": briefing.as_dict(),
        "offline_mode": was_mode,
        "session": snap,
    }
    _fanout(sess, payload)
    return {
        "already_awake": False,
        "presence": PresenceState.ACTIVE.value,
        "briefing": briefing.as_dict(),
        "offline_mode": was_mode,
        "session": session_dict(sess, viewer_id=player.id),
    }


# ---------- background world loop ----------
def ensure_finance(sess: Session) -> MarketState:
    if sess.finance is None:
        sess.finance = MarketState.create(
            genre=sess.world.genre,
            seed=f"{sess.seed_key or 'world'}:{sess.id}",
            society=sess.society,
        )
    return sess.finance


def ensure_finance_lab(sess: Session) -> FinanceLab:
    if sess.finance_lab is None:
        sess.finance_lab = FinanceLab.create(
            seed=f"{sess.seed_key or 'world'}:{sess.id}:lab",
            genre=sess.world.genre,
            world_name=sess.world.name,
            civilization_key=sess.seed_key or "modern",
            user_id=sess.user_id,
        )
    return sess.finance_lab


def _sync_macro_from_finance(sess: Session) -> None:
    """Map market aggregates into the 0–100 economy gauge for existing UI."""
    fin = sess.finance
    if not fin:
        return
    # High price index / inflation pressure → lower "prosperity" reading
    pressure = max(0.0, (fin.price_index - 100.0) * 0.35 + abs(fin.inflation) * 2.0)
    prosperity = 70.0 - pressure + min(15.0, fin.volume / 20.0)
    sess.director.stats.economy = max(5.0, min(95.0, prosperity))
    sess.director.stats.summary["economy"] = (
        f"物价指数 {fin.price_index:.1f} · 货币存量 {fin.money_supply:.0f} · "
        f"基尼 {fin.gini:.2f}"
    )


async def run_finance_ticks(sess: Session, steps: int = 1) -> dict:
    """Advance deterministic market N hours (validation / fast-forward)."""
    steps = max(1, min(168, int(steps)))
    async with sess.lock:
        fin = ensure_finance(sess)
        all_events: list[dict] = []
        for _ in range(steps):
            ev = fin.advance(sess.world, sess.society)
            sess.society.advance_schedules(sess.world)
            all_events.extend(ev)
            for e in ev:
                sess.events.append(
                    "finance_event",
                    {**e, "finance_tick": fin.tick},
                    tick=sess.world.clock.tick,
                )
        _sync_macro_from_finance(sess)
        snap = session_dict(sess)
        payload = {
            "type": "finance_tick",
            "finance": fin.snapshot(),
            "stats": sess.director.stats.snapshot(),
            "session": snap,
        }
    _fanout(sess, payload)
    _fanout_agent_transforms(sess)
    return {
        "steps": steps,
        "events": all_events[-20:],
        "finance": fin.snapshot(),
        "session": snap,
    }


async def run_background_tick(sess: Session) -> int:
    """Attempt one Ollama narrative/world tick. Finance advances separately."""
    if sess.simulation_running:
        return 0
    sess.simulation_running = True
    sess.simulation_last_error = ""
    try:
        async with sess.lock:
            process_injections(sess)
            for npc in sess.society.npcs():
                if npc.id not in sess._loc_snapshot:
                    sess._loc_snapshot[npc.id] = npc.location_id or ""
            ensure_finance(sess)

            fin_snap = None
            if sess.finance:
                fin_snap = {
                    "price_index": sess.finance.price_index,
                    "inflation": sess.finance.inflation,
                    "money_supply": sess.finance.money_supply,
                    "gini": sess.finance.gini,
                    "goods": [
                        {"id": g.id, "name": g.name, "price": round(g.price, 2)}
                        for g in sess.finance.goods.values()
                    ],
                }
        try:
            result, raw = await infer_live_tick(
                sess.llm, sess.world, sess.society, sess.director.stats, sess.memory,
                finance=fin_snap,
            )
        except Exception as exc:
            sess.simulation_last_error = str(exc)[:500]
            _fanout(sess, {
                "type": "simulation_error",
                "tick": sess.world.clock.tick,
                "error": sess.simulation_last_error,
                "session": session_dict(sess),
            })
            return 0

        async with sess.lock:
            world_events = apply_live_tick(
                result, raw, sess.world, sess.society,
                sess.director.stats, sess.memory,
            )
            if sess.finance:
                sess.finance.money_supply = sum(
                    float(a.savings or 0) for a in sess.society.all()
                )
                _sync_macro_from_finance(sess)
            for event in world_events:
                sess.events.append("world_event", event, tick=sess.world.clock.tick)
                if event.get("kind") in ("incident", "politics", "military", "economy"):
                    for pid in sess.player_ids:
                        title, desc, rewards = story_task_from_event(
                            event["summary"], sess.world.clock.tick,
                            event.get("location_id"),
                        )
                        sess.tasks.create_story_task(
                            pid, title=title, description=desc,
                            tick=sess.world.clock.tick,
                            location_id=event.get("location_id"), rewards=rewards,
                        )
            sess.simulation_last_model = result.model
            sess.simulation_last_tick = sess.world.clock.tick
            sess.simulation_last_reasoning = result.reasoning
            sess.events.append(
                "ollama_tick",
                {
                    "model": result.model,
                    "reasoning": result.reasoning,
                    "environment": result.environment,
                    "decision_count": len(result.decisions),
                    "event_count": len(world_events),
                    "finance_tick": sess.finance.tick if sess.finance else None,
                },
                tick=sess.world.clock.tick,
            )
            from .session_persist import maybe_save_snapshot
            maybe_save_snapshot(sess)
            sess.society.advance_schedules(sess.world)
            payload = {
                "type": "simulation_tick",
                "tick": sess.world.clock.tick,
                "clock": sess.world.clock.label(),
                "events": len(world_events),
                "model": result.model,
                "finance": sess.finance.snapshot() if sess.finance else None,
                "stats": sess.director.stats.snapshot(),
                "session": session_dict(sess),
            }
        _fanout(sess, payload)
        _fanout_agent_transforms(sess)
        return len(world_events)
    except Exception as exc:
        sess.simulation_last_error = str(exc)[:500]
        _fanout(sess, {
            "type": "simulation_error",
            "tick": sess.world.clock.tick,
            "error": sess.simulation_last_error,
            "session": session_dict(sess),
        })
        return 0
    finally:
        sess.simulation_running = False


async def apply_finance_shock(
    sess: Session,
    *,
    kind: str,
    good_id: str,
    magnitude: float,
    duration: int,
    note: str = "",
) -> dict:
    async with sess.lock:
        fin = ensure_finance(sess)
        shock = fin.schedule_shock(
            kind=kind, good_id=good_id, magnitude=magnitude,
            duration=duration, note=note,
        )
        sess.events.append(
            "finance_shock",
            shock.as_dict(),
            tick=sess.world.clock.tick,
        )
        snap = session_dict(sess)
    _fanout(sess, {"type": "finance_shock", "shock": shock.as_dict(), "session": snap})
    return {"shock": shock.as_dict(), "finance": fin.snapshot(), "session": snap}


async def lab_global_forecast(sess: Session, *, horizon: int = 24) -> dict:
    lab = ensure_finance_lab(sess)
    result = await lab.global_desk.forecast(sess.llm, horizon=horizon)
    async with sess.lock:
        sess.events.append("finance_lab_global", {
            "horizon": horizon,
            "outlook": (result.get("narrative") or {}).get("outlook"),
        }, tick=sess.world.clock.tick)
        snap = session_dict(sess)
    return {"result": result, "finance_lab": lab.snapshot(), "session": snap}


async def lab_global_event(
    sess: Session, *, at_step: int, title: str, kind: str, magnitude: float, note: str = "",
) -> dict:
    async with sess.lock:
        lab = ensure_finance_lab(sess)
        ev = lab.global_desk.insert_event(
            at_step=at_step, title=title, kind=kind, magnitude=magnitude, note=note,
        )
        snap = session_dict(sess)
    return {"event": ev.as_dict(), "finance_lab": lab.snapshot(), "session": snap}


async def lab_city_forecast(sess: Session, *, horizon: int = 24, city_key: str | None = None) -> dict:
    lab = ensure_finance_lab(sess)
    if city_key and not lab.select_city(city_key):
        raise ValueError(f"unknown city: {city_key}")
    result = await lab.city_desk.forecast(sess.llm, horizon=horizon)
    async with sess.lock:
        sess.events.append("finance_lab_city", {
            "horizon": horizon,
            "outlook": (result.get("narrative") or {}).get("outlook"),
        }, tick=sess.world.clock.tick)
        snap = session_dict(sess)
    return {"result": result, "finance_lab": lab.snapshot(), "session": snap}


async def lab_city_event(
    sess: Session, *, at_step: int, title: str, kind: str, magnitude: float, note: str = "",
) -> dict:
    async with sess.lock:
        lab = ensure_finance_lab(sess)
        ev = lab.city_desk.insert_event(
            at_step=at_step, title=title, kind=kind, magnitude=magnitude, note=note,
        )
        snap = session_dict(sess)
    return {"event": ev.as_dict(), "finance_lab": lab.snapshot(), "session": snap}


async def lab_corporate_forecast(
    sess: Session, *, horizon: int = 24, company_name: str | None = None, sector: str | None = None,
    company_key: str | None = None,
) -> dict:
    lab = ensure_finance_lab(sess)
    if company_key and not lab.select_company(company_key):
        raise ValueError(f"unknown company: {company_key}")
    if company_name:
        lab.corporate.company_name = company_name[:40]
    if sector:
        lab.corporate.sector = sector[:24]
    result = await lab.corporate.forecast(sess.llm, horizon=horizon)
    async with sess.lock:
        sess.events.append("finance_lab_corporate", {
            "company": lab.corporate.company_name,
            "expected_return_pct": result.get("expected_return_pct"),
        }, tick=sess.world.clock.tick)
        snap = session_dict(sess)
    return {"result": result, "finance_lab": lab.snapshot(), "session": snap}


async def lab_corporate_event(
    sess: Session, *, at_step: int, title: str, kind: str, magnitude: float, note: str = "",
) -> dict:
    async with sess.lock:
        lab = ensure_finance_lab(sess)
        ev = lab.corporate.insert_event(
            at_step=at_step, title=title, kind=kind, magnitude=magnitude, note=note,
        )
        snap = session_dict(sess)
    return {"event": ev.as_dict(), "finance_lab": lab.snapshot(), "session": snap}


async def lab_retail_run(
    sess: Session, *, risk: str = "balanced", horizon: str = "auto", capital: float | None = None,
) -> dict:
    async with sess.lock:
        lab = ensure_finance_lab(sess)
        result = lab.retail.run(risk=risk, horizon=horizon, capital=capital)
        sess.events.append("finance_lab_retail", {
            "risk": risk,
            "horizon": result["recommendation"]["horizon"],
            "expected_return_pct": result["recommendation"]["expected_return_pct"],
        }, tick=sess.world.clock.tick)
        snap = session_dict(sess)
    return {"result": result, "finance_lab": lab.snapshot(), "session": snap}


async def _background_loop() -> None:
    settings = get_settings()
    finance_interval = max(2.0, float(getattr(settings, "finance_tick_seconds", 3.0)))
    ollama_interval = max(finance_interval, float(settings.live_simulation_tick_seconds))
    timeout = float(settings.presence_timeout_seconds)
    last_ollama: dict[str, float] = {}
    while True:
        try:
            await asyncio.sleep(finance_interval)
            now = time.time()
            for sess in list(_SESSIONS.values()):
                for pid in list(sess.player_ids):
                    ag = sess.society.get(pid)
                    if not ag or ag.kind != AgentKind.PLAYER:
                        continue
                    if (
                        ag.presence == PresenceState.ACTIVE
                        and (now - ag.last_heartbeat_ts) > timeout
                    ):
                        try:
                            await sleep_player(sess, player_id=pid, reason="timeout")
                        except Exception:
                            pass
                # Finance always advances on a short cadence for validation.
                try:
                    await run_finance_ticks(sess, 1)
                except Exception:
                    pass
                # Ollama narrative/world tick on a slower cadence.
                prev = last_ollama.get(sess.id, 0.0)
                if (now - prev) >= ollama_interval and not sess.simulation_running:
                    last_ollama[sess.id] = now
                    try:
                        await run_background_tick(sess)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(1.0)


def start_background_loop() -> None:
    global _BG_TASK
    if _BG_TASK is None or _BG_TASK.done():
        _BG_TASK = asyncio.create_task(_background_loop())


def stop_background_loop() -> None:
    global _BG_TASK
    if _BG_TASK and not _BG_TASK.done():
        _BG_TASK.cancel()
    _BG_TASK = None


# ---------- step / fan-out ----------
async def step(sess: Session, *, player_id: str | None = None,
               player_input: str | None = None) -> Page:
    pid = player_id or sess.primary_player_id
    if pid is None:
        raise RuntimeError("session has no player agent")
    player = sess.society.get(pid)
    if player is None:
        raise RuntimeError(f"player {pid} not in session")

    if player.is_offline():
        await wake_player(sess, player_id=pid)

    async with sess.lock:
        process_injections(sess)
        player.last_heartbeat_ts = time.time()
        if player_input:
            sess.events.append("player_input",
                               {"player_id": pid, "text": player_input},
                               tick=sess.world.clock.tick)
        page = await sess.director.direct_page(
            sess.llm, sess.world, sess.society, sess.memory, player, player_input,
        )
        player.last_observed_tick = sess.world.clock.tick
        completed = _sync_player_tasks(sess, player, player_input)
        sess.pages.append(page)
        sess.events.append("page", page_dict(page), tick=sess.world.clock.tick)
        # B-1: narrative pages must persist even when world clock stalls at 0.
        try:
            from .session_persist import force_save_snapshot
            force_save_snapshot(sess)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to force-save snapshot after step for %s", sess.id,
            )

    _fanout(sess, {"type": "page", "page": page_dict(page),
                   "stats": sess.director.stats.snapshot(),
                   "tasks_completed": completed})
    return page


def subscribe(sess: Session) -> "asyncio.Queue[dict]":
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=64)
    sess.subscribers.append(q)
    return q


# ---------- direct NPC dialogue (out-of-band, doesn't increment page) ----------
async def npc_reply(sess: Session, *, npc_id: str, text: str,
                    player_id: str | None = None) -> dict:
    pid = player_id or sess.primary_player_id
    if pid is None:
        raise RuntimeError("session has no player agent")
    player = sess.society.get(pid)
    npc = sess.society.get(npc_id)
    if not player or not npc:
        raise KeyError("agent not found")
    if npc.kind.value != "npc":
        raise ValueError("target is not an NPC")

    # Resolve location name for context.
    loc_name = None
    if npc.location_id and npc.location_id in sess.world.locations:
        loc_name = sess.world.locations[npc.location_id].name

    # Write player utterance + npc reply into shared memory.
    sess.memory.add(player.id, "dialogue",
                    f"对【{npc.name}】说：{text}", importance=0.55)
    reply = await npc.reply_to(
        sess.world, sess.memory,
        speaker_name=player.name, speaker_text=text,
        llm=sess.llm, location_name=loc_name,
    )
    sess.memory.add(npc.id, "dialogue",
                    f"答【{player.name}】：{reply}", importance=0.55)

    # Tiny relation nudge so the social graph evolves with talk volume.
    sess.society.adjust_relation(player.id, npc.id, 0.02)
    sess.society.adjust_relation(npc.id, player.id, 0.02)

    sess.events.append("npc_dialogue", {
        "player_id": player.id, "npc_id": npc.id,
        "player_text": text, "npc_reply": reply,
        "location_id": npc.location_id,
    }, tick=sess.world.clock.tick)

    payload = {
        "type": "npc_dialogue",
        "npc_id": npc.id, "npc_name": npc.name,
        "player_text": text, "reply": reply,
    }
    for q in list(sess.subscribers):
        try:
            q.put_nowait(payload)
        except Exception:
            pass
    return {"npc_id": npc.id, "npc_name": npc.name, "reply": reply}


def _legacy_subscribe_marker() -> None:
    pass


def unsubscribe(sess: Session, q: "asyncio.Queue[dict]") -> None:
    try:
        sess.subscribers.remove(q)
    except ValueError:
        pass


# ---------- query ----------
def get_session(sid: str) -> Session | None:
    return _SESSIONS.get(sid)


def destroy_session(sid: str) -> None:
    """Remove a room from the in-memory registry (R1-3 orphan cleanup)."""
    _SESSIONS.pop(sid, None)


def list_sessions() -> list[dict]:
    return [
        {
            "id": s.id,
            "world": s.world.name,
            "genre": s.world.genre,
            "tick": s.world.clock.tick,
            "players": len(s.player_ids),
        }
        for s in _SESSIONS.values()
    ]


# ---------- replay ----------
def replay_to_tick(sid: str, *, to_tick: int) -> dict:
    """Reconstruct a UI-friendly view of the session up to `to_tick`."""
    es = EventStore(sid)
    snap = es.latest_snapshot(max_tick=to_tick)
    base = snap[1] if snap else {"agents": [], "pages": [], "world": None,
                                 "player_ids": []}
    base.setdefault("pages", [])
    after_tick = snap[0] if snap else -1
    for ev in es.replay(to_tick=to_tick):
        if ev.tick <= after_tick:
            continue
        if ev.kind == "page":
            base["pages"].append(ev.payload)
        elif ev.kind == "agent_added":
            base.setdefault("agents", []).append(ev.payload["agent"])
            if ev.payload.get("player"):
                base.setdefault("player_ids", []).append(ev.payload["agent"]["id"])
        elif ev.kind == "world_created":
            base["world"] = ev.payload["world"]
    base["id"] = sid
    base.setdefault("player_id",
                    base["player_ids"][0] if base.get("player_ids") else None)
    return base


# ---------- serialization ----------
def _agent_dict(a: Agent) -> dict:
    presence = getattr(a, "presence", PresenceState.ACTIVE)
    if hasattr(presence, "value"):
        presence = presence.value
    inv = getattr(a, "inventory", None) or []
    return {
        "id": a.id, "name": a.name, "kind": a.kind.value,
        "persona": a.persona, "goals": a.goals, "traits": a.traits,
        "location_id": a.location_id,
        "relations": dict(a.relations),
        "avatar": getattr(a, "avatar", ""),
        "appearance": dict(getattr(a, "appearance", {}) or {}),
        "profession": getattr(a, "profession", ""),
        "schedule": list(getattr(a, "schedule", [])),
        "economy": dict(getattr(a, "economy", {})),
        "current_activity": getattr(a, "current_activity", ""),
        "savings": getattr(a, "savings", 0.0),
        "today_income": getattr(a, "today_income", 0.0),
        "today_customers": getattr(a, "today_customers", 0),
        "last_meal_tier": getattr(a, "last_meal_tier", ""),
        "presence": presence,
        "dormant_since_tick": getattr(a, "dormant_since_tick", None),
        "last_observed_tick": getattr(a, "last_observed_tick", 0),
        "offline_mode": getattr(a, "offline_mode", ""),
        "offline_rationale": getattr(a, "offline_rationale", ""),
        "world_x": getattr(a, "world_x", 0.0),
        "world_z": getattr(a, "world_z", 0.0),
        "behavior": getattr(a, "behavior", "idle"),
        "inventory": inventory_to_dict(inv),
        "equipment": dict(getattr(a, "equipment", {})),
        "skills": skills_to_dict(getattr(a, "skills", None) or [], tick=0),
    }


def page_dict(p: Page) -> dict:
    return {
        "page_no": p.page_no,
        "chapter": p.chapter,
        "scene": {
            "location_id": p.scene.location_id,
            "location_name": p.scene.location_name,
            "summary": p.scene.summary,
            "present_agent_ids": list(p.scene.present_agent_ids),
        },
        "beats": [{"kind": b.kind, "speaker": b.speaker, "content": b.content} for b in p.beats],
        "choices": list(p.choices),
        "tension": getattr(p, "tension", 0.0),
    }


def session_dict(s: Session, *, viewer_id: str | None = None) -> dict:
    """Serialize a room. ``viewer_id`` selects which player is "me" for the client."""
    from .layer6_persistence.users import find_member_by_player_id, get_session_host_user_id

    pid = viewer_id if (viewer_id and viewer_id in s.player_ids) else s.primary_player_id
    tick = s.world.clock.tick
    genre = s.world.genre
    host_uid = get_session_host_user_id(s.id) or s.user_id
    agents_out = []
    for a in s.society.all():
        a.ensure_skills(genre)
        d = _agent_dict(a)
        d["skills"] = skills_to_dict(a.skills, tick=tick)
        agents_out.append(d)
    roster = []
    for p in s.player_ids:
        ag = s.society.get(p)
        mem = find_member_by_player_id(s.id, p)
        uid = mem["user_id"] if mem else None
        roster.append({
            "player_id": p,
            "user_id": uid,
            "name": (ag.name if ag else p),
            "presence": (ag.presence.value if ag else "unknown"),
            "is_self": p == pid,
            "is_host": bool(uid and host_uid and uid == host_uid),
        })
    return {
        "id": s.id,
        "world": s.world.snapshot(),
        "agents": agents_out,
        "player_ids": list(s.player_ids),
        "player_id": pid,
        "user_id": s.user_id,
        "host_user_id": host_uid,
        "max_players": int(getattr(s, "max_players", 8) or 8),
        "seed_key": s.seed_key,
        "pages": [page_dict(p) for p in s.pages],
        "tension_curve": s.director.tension.to_curve(),
        "stats": s.director.stats.snapshot(),
        "finance": s.finance.snapshot() if s.finance else None,
        "finance_lab": s.finance_lab.snapshot() if s.finance_lab else None,
        "simulation": {
            "provider": s.llm.name,
            "running": s.simulation_running,
            "last_model": s.simulation_last_model,
            "last_tick": s.simulation_last_tick,
            "last_error": s.simulation_last_error,
            "last_reasoning": s.simulation_last_reasoning,
            "continuous": True,
        },
        "injections": s.injections.snapshot(),
        "tasks": s.tasks.snapshot(pid) if pid else [],
        "roster": roster,
    }


async def use_skill(sess: Session, *, skill_id: str,
                    player_id: str | None = None) -> Page:
    """Use a player skill as the next page action."""
    player = _resolve_player(sess, player_id)
    player.ensure_skills(sess.world.genre)
    sk, prompt = player.use_skill(skill_id, sess.world.clock.tick)
    if sk is None:
        raise ValueError(prompt)
    return await step(sess, player_id=player.id, player_input=prompt)


# ---------- injections / tasks API ----------
async def schedule_event(sess: Session, *, tick: int, summary: str,
                         importance: float = 0.85,
                         location_id: str | None = None) -> dict:
    inj = sess.injections.schedule_event(
        tick, summary=summary, importance=importance, location_id=location_id,
    )
    if tick <= sess.world.clock.tick:
        async with sess.lock:
            process_injections(sess)
    return inj.as_dict()


async def schedule_character(sess: Session, *, tick: int, name: str, persona: str,
                             profession: str = "", location_id: str | None = None,
                             traits: list[str] | None = None,
                             agent_kind: str = "npc") -> dict:
    inj = sess.injections.schedule_character(
        tick, name=name, persona=persona, profession=profession,
        location_id=location_id, traits=traits, agent_kind=agent_kind,
    )
    if tick <= sess.world.clock.tick:
        async with sess.lock:
            process_injections(sess)
    return inj.as_dict()


async def create_self_task(sess: Session, *, player_id: str | None = None,
                           title: str, description: str = "",
                           rewards: dict | None = None) -> dict:
    pid = player_id or sess.primary_player_id
    if not pid:
        raise RuntimeError("no player")
    task = sess.tasks.create_self_task(
        pid, title=title, description=description or title,
        tick=sess.world.clock.tick, rewards=rewards,
    )
    return task.as_dict()


async def complete_task(sess: Session, *, player_id: str | None = None,
                        task_id: str) -> dict:
    pid = player_id or sess.primary_player_id
    if not pid:
        raise KeyError("player not found")
    player = sess.society.get(pid)
    if not player:
        raise KeyError("player not found")
    task, inv, sav, result = sess.tasks.complete(
        pid, task_id,
        inventory=list(player.inventory),
        savings=player.savings,
        profession=player.profession,
        economy=player.economy or {},
    )
    if not task:
        return result
    player.inventory = inv
    player.savings = sav
    sess.events.append("task_completed", {
        "player_id": pid, "task": task.as_dict(),
    }, tick=sess.world.clock.tick)
    return result


async def skip_to_tick(sess: Session, target_tick: int) -> dict:
    """Fast-forward through real Ollama ticks; never synthesize random state."""
    target_tick = max(sess.world.clock.tick, target_tick)
    steps = 0
    while sess.world.clock.tick < target_tick:
        before = sess.world.clock.tick
        await run_background_tick(sess)
        if sess.world.clock.tick == before:
            break
        steps += 1
    return {
        "tick": sess.world.clock.tick,
        "steps": steps,
        "error": sess.simulation_last_error or None,
        "session": session_dict(sess),
    }

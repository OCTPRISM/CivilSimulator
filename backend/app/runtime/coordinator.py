"""TickCoordinator — single entry for session mutations."""
from __future__ import annotations

import time
from typing import Any, Callable, Awaitable

from ..observability import bump_metric
from .commands import TickCommand, TickKind, TickResult
from .errors import RuntimeAppError, RuntimeErrorCode
from .events import EventEnvelope
from .effects import WorldEffect, validate_effects
from .idempotency import IdempotencyCache
from .leases import InProcessLeaseManager
from .perceive import perceive_for_actor
from .plan import plan_from_command
from .reflect import derive_narrative_effects, reflect_after_commit
from .reducer import apply_effects

# Injected by session module to avoid circular imports at import time.
_NarrativeStepFn = Callable[..., Awaitable[tuple[Any, list[dict[str, Any]]]]]
_FanoutFn = Callable[[Any, dict[str, Any]], None]


class TickCoordinator:
    def __init__(self) -> None:
        self.leases = InProcessLeaseManager()
        self.idempotency = IdempotencyCache()
        self._narrative_step: _NarrativeStepFn | None = None
        self._fanout: _FanoutFn | None = None

    def bind(
        self,
        *,
        narrative_step: _NarrativeStepFn | None = None,
        fanout: _FanoutFn | None = None,
    ) -> None:
        if narrative_step is not None:
            self._narrative_step = narrative_step
        if fanout is not None:
            self._fanout = fanout

    async def execute(self, sess: Any, cmd: TickCommand) -> TickResult:
        t0 = time.perf_counter()
        cached = self.idempotency.get(cmd.session_id, cmd.command_id)
        if cached is not None:
            bump_metric("runtime.tick.dedup")
            if isinstance(cached, TickResult):
                cached.deduplicated = True
                return cached
            return cached

        if cmd.session_id != sess.id:
            raise RuntimeAppError(
                RuntimeErrorCode.VALIDATION_FAILED,
                "command session_id mismatch",
                details={"command": cmd.session_id, "session": sess.id},
            )

        owner = cmd.user_id or cmd.actor_id or "system"
        async with self.leases.hold(cmd.session_id, owner=owner):
            base_rev = int(getattr(sess, "revision", 0) or 0)
            if cmd.expected_revision is not None and cmd.expected_revision != base_rev:
                raise RuntimeAppError(
                    RuntimeErrorCode.SESSION_REVISION_CONFLICT,
                    "session revision conflict",
                    details={
                        "expected": cmd.expected_revision,
                        "actual": base_rev,
                    },
                    retry_after_ms=100,
                )

            perception = perceive_for_actor(sess, cmd.actor_id)
            plan = plan_from_command(cmd, perception)

            if cmd.kind == TickKind.NARRATIVE:
                result = await self._run_narrative(sess, cmd, perception, plan, base_rev)
            elif cmd.kind == TickKind.DIALOGUE:
                result = await self._run_dialogue(sess, cmd, perception, plan, base_rev)
            else:
                result = await self._run_generic(sess, cmd, perception, plan, base_rev)

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            result.metrics = {
                "latency_ms": round(elapsed_ms, 2),
                "kind": cmd.kind.value,
            }
            bump_metric("runtime.tick.ok", latency_ms=elapsed_ms)
            bump_metric(f"runtime.tick.{cmd.kind.value}", latency_ms=elapsed_ms)
            self.idempotency.put(cmd.session_id, cmd.command_id, result)
            return result

    async def _run_narrative(
        self,
        sess: Any,
        cmd: TickCommand,
        perception: dict[str, Any],
        plan: dict[str, Any],
        base_rev: int,
    ) -> TickResult:
        if self._narrative_step is None:
            raise RuntimeAppError(
                RuntimeErrorCode.INTERNAL_ERROR,
                "narrative step handler not bound",
            )
        player_input = str(cmd.payload.get("input") or "") or None
        page, completed = await self._narrative_step(
            sess,
            player_id=cmd.actor_id,
            player_input=player_input,
            skip_fanout=True,
            skip_lock=False,
        )
        from ..session import page_dict

        pd = page_dict(page)
        effects = derive_narrative_effects(
            actor_id=cmd.actor_id,
            player_input=player_input,
            page_dict=pd,
            tasks_completed=completed,
        )
        known_agents = {a.id for a in sess.society.all()}
        known_locs = set(sess.world.locations.keys())
        effects = validate_effects(
            effects, known_agent_ids=known_agents, known_location_ids=known_locs,
        )

        # Memory + revision under same lock as step (step already released).
        async with sess.lock:
            # Avoid double-writing page memory if step already recorded input event;
            # only apply APPEND_MEMORY + BUMP_REVISION here.
            to_apply = [
                e for e in effects
                if e.op.value in ("append_memory", "bump_revision")
            ]
            apply_effects(sess, to_apply)
            env = EventEnvelope(
                session_id=sess.id,
                kind="page",
                payload={
                    "page": pd,
                    "stats": sess.director.stats.snapshot(),
                    "tasks_completed": completed,
                    "perception": perception,
                    "plan": plan,
                },
                tick=sess.world.clock.tick,
                revision=int(sess.revision),
                command_id=cmd.command_id,
                correlation_id=cmd.correlation_id,
                actor_id=cmd.actor_id,
                effects=[e.as_dict() for e in effects],
            )
            sess.events.append(env.kind, env.as_store_payload(), tick=env.tick)
            reflection = reflect_after_commit(
                sess, cmd, perception=perception, plan=plan, effects=effects,
            )

        ws_msg = env.as_ws_message()
        if self._fanout:
            self._fanout(sess, ws_msg)

        return TickResult(
            command_id=cmd.command_id,
            session_id=sess.id,
            kind=cmd.kind,
            base_revision=base_rev,
            revision=int(sess.revision),
            world_tick=int(sess.world.clock.tick),
            event_ids=[env.event_id],
            effects=[e.as_dict() for e in effects],
            envelopes=[env.as_dict()],
            page=page,
            stats=sess.director.stats.snapshot(),
            tasks_completed=list(completed or []),
            perception=perception,
            plan=plan,
            reflection=reflection,
            correlation_id=cmd.correlation_id,
        )

    async def _run_dialogue(
        self,
        sess: Any,
        cmd: TickCommand,
        perception: dict[str, Any],
        plan: dict[str, Any],
        base_rev: int,
    ) -> TickResult:
        from ..session import npc_reply

        npc_id = str(cmd.payload.get("npc_id") or "")
        text = str(cmd.payload.get("text") or cmd.payload.get("input") or "")
        if not npc_id or not text:
            raise RuntimeAppError(
                RuntimeErrorCode.VALIDATION_FAILED,
                "dialogue requires npc_id and text",
            )
        reply = await npc_reply(
            sess, npc_id=npc_id, text=text, player_id=cmd.actor_id,
        )
        kind = str((reply or {}).get("target_kind") or "npc")
        effects = [
            WorldEffect.from_dict({"op": "bump_revision", "payload": {}}),
        ]
        # Relations already nudged inside npc_reply; only bump revision.
        async with sess.lock:
            apply_effects(sess, effects)
            env = EventEnvelope(
                session_id=sess.id,
                kind="player_dialogue" if kind == "player" else "npc_dialogue",
                payload=dict(reply),
                tick=sess.world.clock.tick,
                revision=int(sess.revision),
                command_id=cmd.command_id,
                correlation_id=cmd.correlation_id,
                actor_id=cmd.actor_id,
                effects=[e.as_dict() for e in effects],
            )
            reflection = reflect_after_commit(
                sess, cmd, perception=perception, plan=plan, effects=effects,
            )

        if self._fanout:
            self._fanout(sess, env.as_ws_message())

        return TickResult(
            command_id=cmd.command_id,
            session_id=sess.id,
            kind=cmd.kind,
            base_revision=base_rev,
            revision=int(sess.revision),
            world_tick=int(sess.world.clock.tick),
            event_ids=[env.event_id],
            effects=[e.as_dict() for e in effects],
            envelopes=[env.as_dict()],
            reply=reply,
            perception=perception,
            plan=plan,
            reflection=reflection,
            correlation_id=cmd.correlation_id,
        )

    async def _run_generic(
        self,
        sess: Any,
        cmd: TickCommand,
        perception: dict[str, Any],
        plan: dict[str, Any],
        base_rev: int,
    ) -> TickResult:
        """WORLD_HOUR runs unified market+schedules+clock; other kinds bump revision."""
        from .world_hour import commit_world_hours_locked

        effects: list[WorldEffect] = []
        hour_summary: dict[str, Any] | None = None
        if cmd.kind == TickKind.WORLD_HOUR and cmd.advance_hours > 0:
            effects.append(WorldEffect.from_dict({
                "op": "advance_clock",
                "payload": {"hours": cmd.advance_hours, "unified_market": True},
                "reason": "world_hour",
            }))
        effects.append(WorldEffect.from_dict({"op": "bump_revision", "payload": {}}))
        known_agents = {a.id for a in sess.society.all()}
        known_locs = set(sess.world.locations.keys())
        effects = validate_effects(
            effects, known_agent_ids=known_agents, known_location_ids=known_locs,
        )

        async with sess.lock:
            if cmd.kind == TickKind.WORLD_HOUR and cmd.advance_hours > 0:
                hour_summary = commit_world_hours_locked(
                    sess, cmd.advance_hours, skip_injections=False,
                )
                # Clock already advanced; only bump revision here.
                apply_effects(sess, [
                    e for e in effects if e.op.value == "bump_revision"
                ])
            else:
                apply_effects(sess, effects)

            payload: dict[str, Any] = {
                "plan": plan,
                "perception": perception,
                "advance_hours": cmd.advance_hours,
            }
            if hour_summary is not None:
                payload["world_hour"] = {
                    "hours": hour_summary.get("hours"),
                    "world_tick": hour_summary.get("world_tick"),
                    "finance_tick": hour_summary.get("finance_tick"),
                    "in_sync": hour_summary.get("in_sync"),
                    "align": hour_summary.get("align"),
                    "event_count": len(hour_summary.get("events") or []),
                }
                fin = getattr(sess, "finance", None)
                if fin is not None:
                    payload["finance"] = fin.snapshot()

            env = EventEnvelope(
                session_id=sess.id,
                kind=cmd.kind.value,
                payload=payload,
                tick=sess.world.clock.tick,
                revision=int(sess.revision),
                command_id=cmd.command_id,
                correlation_id=cmd.correlation_id,
                actor_id=cmd.actor_id,
                effects=[e.as_dict() for e in effects],
            )
            sess.events.append(env.kind, env.as_store_payload(), tick=env.tick)
            reflection = reflect_after_commit(
                sess, cmd, perception=perception, plan=plan, effects=effects,
            )

        ws_msg = env.as_ws_message()
        if cmd.kind == TickKind.WORLD_HOUR and hour_summary is not None:
            # Keep legacy UI consumers that listen for finance_tick.
            ws_msg.setdefault("type", "world_hour")
            if self._fanout:
                self._fanout(sess, ws_msg)
                fin = getattr(sess, "finance", None)
                if fin is not None:
                    from ..session import session_dict
                    self._fanout(sess, {
                        "type": "finance_tick",
                        "finance": fin.snapshot(),
                        "stats": sess.director.stats.snapshot(),
                        "session": session_dict(sess),
                        "revision": int(sess.revision),
                        "world_tick": int(sess.world.clock.tick),
                        "unified": True,
                        "command_id": cmd.command_id,
                    })
        elif self._fanout:
            self._fanout(sess, ws_msg)

        return TickResult(
            command_id=cmd.command_id,
            session_id=sess.id,
            kind=cmd.kind,
            base_revision=base_rev,
            revision=int(sess.revision),
            world_tick=int(sess.world.clock.tick),
            event_ids=[env.event_id],
            effects=[e.as_dict() for e in effects],
            envelopes=[env.as_dict()],
            perception=perception,
            plan=plan,
            reflection=reflection,
            correlation_id=cmd.correlation_id,
            reply=hour_summary,
        )


_COORDINATOR: TickCoordinator | None = None


def get_coordinator() -> TickCoordinator:
    global _COORDINATOR
    if _COORDINATOR is None:
        _COORDINATOR = TickCoordinator()
    return _COORDINATOR

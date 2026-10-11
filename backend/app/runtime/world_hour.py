"""Unified WORLD_HOUR commit: injections → schedules → market → clock.

Caller must hold ``sess.lock`` (or use the async public wrapper that acquires it).
Invariant after a clean run from synced clocks: ``world.clock.tick == finance.tick``.
"""
from __future__ import annotations

from typing import Any


def align_finance_to_world(sess: Any) -> dict[str, Any]:
    """One-time heal when legacy dual-loop left clocks diverged.

    - Finance behind → catch up market clears (no world advance).
    - World behind → advance world clock only (market already cleared those hours).
    """
    from ..session import ensure_finance

    fin = ensure_finance(sess)
    wt = int(sess.world.clock.tick)
    ft = int(fin.tick)
    if ft == wt:
        return {"aligned": True, "world_tick": wt, "finance_tick": ft, "action": "none"}
    if ft < wt:
        lag = wt - ft
        for _ in range(lag):
            fin.advance(sess.world, sess.society)
        return {
            "aligned": True,
            "world_tick": int(sess.world.clock.tick),
            "finance_tick": int(fin.tick),
            "action": "catch_up_finance",
            "hours": lag,
        }
    # World behind finance: snap world forward without re-clearing market.
    gap = ft - wt
    sess.world.clock.advance(gap)
    return {
        "aligned": True,
        "world_tick": int(sess.world.clock.tick),
        "finance_tick": int(fin.tick),
        "action": "catch_up_world",
        "hours": gap,
    }


def commit_world_hours_locked(
    sess: Any,
    hours: int = 1,
    *,
    skip_injections: bool = False,
    record_events: bool = True,
) -> dict[str, Any]:
    """Advance ``hours`` unified in-world hours. Requires session lock held."""
    from ..session import ensure_finance, process_injections, _sync_macro_from_finance

    hours = max(0, min(168, int(hours)))
    align = align_finance_to_world(sess)
    fin = ensure_finance(sess)
    all_events: list[dict[str, Any]] = []
    base_world = int(sess.world.clock.tick)
    base_fin = int(fin.tick)

    for _ in range(hours):
        if not skip_injections:
            process_injections(sess)
        sess.society.advance_schedules(sess.world)
        ev = fin.advance(sess.world, sess.society)
        all_events.extend(ev)
        if record_events:
            for e in ev:
                sess.events.append(
                    "finance_event",
                    {**e, "finance_tick": fin.tick, "unified": True},
                    tick=sess.world.clock.tick,
                )
        sess.world.clock.advance(1)
        if record_events:
            sess.events.append(
                "world_hour",
                {
                    "world_tick": sess.world.clock.tick,
                    "finance_tick": fin.tick,
                    "finance_events": len(ev),
                },
                tick=sess.world.clock.tick,
            )

    _sync_macro_from_finance(sess)
    return {
        "hours": hours,
        "world_tick": int(sess.world.clock.tick),
        "finance_tick": int(fin.tick),
        "base_world_tick": base_world,
        "base_finance_tick": base_fin,
        "events": all_events,
        "align": align,
        "in_sync": int(sess.world.clock.tick) == int(fin.tick),
    }

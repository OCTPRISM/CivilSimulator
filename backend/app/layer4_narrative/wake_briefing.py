"""Wake intelligence — narrative layer for events missed while dormant.

Dormant players do not observe ``world_event`` rows. On wake we collect those
events, deliberately blur them, and ask the LLM for an incomplete briefing
(rumour / fragment / hard miss) so the player feels time passed without them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..config import get_settings
from ..layer1_foundation import LLM, Message
from ..layer2_civilization import World
from ..layer3_agents import Agent, MemoryStore
from ..layer6_persistence import EventStore


@dataclass
class MissedShard:
    tick: int
    kind: str
    truth: str                 # full event summary (server-side)
    perceived: str             # what the player may vaguely know
    clarity: str               # rumour | fragment | miss
    importance: float


@dataclass
class WakeBriefing:
    ticks_asleep: int
    from_tick: int
    to_tick: int
    clock_label: str
    narrative: str
    shards: list[MissedShard] = field(default_factory=list)
    npc_shifts: list[dict[str, str]] = field(default_factory=list)
    world_stats_hint: str = ""
    offline_mode: str = "sleep"  # sleep | proxy

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticks_asleep": self.ticks_asleep,
            "from_tick": self.from_tick,
            "to_tick": self.to_tick,
            "clock_label": self.clock_label,
            "narrative": self.narrative,
            "offline_mode": self.offline_mode,
            "shards": [
                {
                    "tick": s.tick,
                    "kind": s.kind,
                    "perceived": s.perceived,
                    "clarity": s.clarity,
                    "importance": s.importance,
                    "truth": s.truth,
                }
                for s in self.shards
            ],
            "npc_shifts": list(self.npc_shifts),
            "world_stats_hint": self.world_stats_hint,
        }


def _blur(summary: str, importance: float, rng_salt: int) -> tuple[str, str]:
    """Return (perceived_text, clarity). Higher importance → more chance of fragment."""
    # Deterministic-ish from salt + length
    roll = (rng_salt + len(summary) * 13) % 100
    if importance < 0.35 or roll < 35:
        return ("……似有动静，却记不清。", "miss")
    if importance < 0.55 or roll < 65:
        # Truncate / fog
        fog = summary
        if len(fog) > 18:
            fog = fog[:10] + "……" + fog[-4:]
        return (f"隐约听闻：{fog}", "rumour")
    # fragment: keep spine of the sentence
    return (f"残缺印象：{summary[:22]}{'…' if len(summary) > 22 else ''}", "fragment")


def collect_missed_events(
    store: EventStore,
    *,
    player_id: str,
    from_tick: int,
    to_tick: int,
    limit: int | None = None,
) -> list[MissedShard]:
    settings = get_settings()
    limit = limit or settings.wake_briefing_max_events
    shards: list[MissedShard] = []
    for ev in store.replay(to_tick=to_tick):
        if ev.tick < from_tick or ev.tick > to_tick:
            continue
        if ev.kind != "world_event":
            continue
        observed = ev.payload.get("observed_by") or []
        if player_id in observed:
            continue
        summary = str(ev.payload.get("summary") or "")
        if not summary:
            continue
        importance = float(ev.payload.get("importance") or 0.4)
        kind = str(ev.payload.get("kind") or "incident")
        perceived, clarity = _blur(summary, importance, ev.tick + len(player_id))
        shards.append(MissedShard(
            tick=ev.tick,
            kind=kind,
            truth=summary,
            perceived=perceived,
            clarity=clarity,
            importance=importance,
        ))
    # Prefer higher importance, then chronological
    shards.sort(key=lambda s: (-s.importance, s.tick))
    return shards[:limit]


async def compose_wake_briefing(
    llm: LLM,
    world: World,
    player: Agent,
    memory: MemoryStore,
    store: EventStore,
    *,
    from_tick: int,
    npc_shifts: list[dict[str, str]] | None = None,
    stats_summary: dict[str, str] | None = None,
) -> WakeBriefing:
    to_tick = world.clock.tick
    shards = collect_missed_events(
        store, player_id=player.id, from_tick=from_tick, to_tick=to_tick,
    )
    ticks_asleep = max(0, to_tick - from_tick)
    npc_shifts = npc_shifts or []

    hint_parts = []
    if stats_summary:
        for k, v in stats_summary.items():
            hint_parts.append(f"{k}:{v}")
    world_stats_hint = "；".join(hint_parts)

    shard_lines = "\n".join(
        f"- [{s.clarity}/{s.kind}@t{s.tick}] {s.perceived}"
        for s in shards
    ) or "（几乎一片空白）"
    shift_lines = "\n".join(
        f"- {s.get('name')}: {s.get('from')} → {s.get('to')}（{s.get('activity','')}）"
        for s in npc_shifts[:8]
    ) or "（无人可察的挪移）"

    sys = (
        f"你是《{world.name}》的苏醒叙事层。玩家角色刚刚从休眠中醒来——"
        "休眠期间世界仍在推进，角色错过了大量事件。"
        "请用第二人称、朦胧而克制的中文写一段醒来后的情报感言（4-7 句）。"
        "规则：只能根据『残缺感知』描写，不得补全真相；"
        "允许传闻、断片、记不清；强调错过与信息差。"
        "输出严格 JSON：{\"narrative\": str}"
    )
    usr = (
        f"角色：{player.name}（{player.persona}）\n"
        f"休眠：约 {ticks_asleep} 个时辰（tick {from_tick}→{to_tick}）\n"
        f"此刻：{world.clock.label()}\n"
        f"残缺感知：\n{shard_lines}\n"
        f"归来后察觉的人事变化：\n{shift_lines}\n"
        f"宏观风向：{world_stats_hint or '不明'}\n"
    )
    resp = await llm.chat(
        [Message("system", sys), Message("user", usr)],
        temperature=0.85, max_tokens=420,
    )
    narrative = _extract_narrative(resp.content) or _fallback_narrative(
        player.name, ticks_asleep, world.clock.label(), shards,
    )

    # Persist a blurred memory — not the full truths
    memory.add(
        player.id,
        "observation",
        f"【苏醒】{narrative}",
        importance=0.75,
    )

    return WakeBriefing(
        ticks_asleep=ticks_asleep,
        from_tick=from_tick,
        to_tick=to_tick,
        clock_label=world.clock.label(),
        narrative=narrative,
        shards=shards,
        npc_shifts=npc_shifts,
        world_stats_hint=world_stats_hint,
        offline_mode="sleep",
    )


def collect_lived_events(
    store: EventStore,
    *,
    player_id: str,
    from_tick: int,
    to_tick: int,
    limit: int | None = None,
) -> list[MissedShard]:
    """Events the proxy character actually observed / caused."""
    settings = get_settings()
    limit = limit or settings.wake_briefing_max_events
    shards: list[MissedShard] = []
    for ev in store.replay(to_tick=to_tick):
        if ev.tick < from_tick or ev.tick > to_tick:
            continue
        if ev.kind != "world_event":
            continue
        observed = ev.payload.get("observed_by") or []
        actors = ev.payload.get("actor_ids") or []
        if player_id not in observed and player_id not in actors:
            continue
        summary = str(ev.payload.get("summary") or "")
        if not summary:
            continue
        shards.append(MissedShard(
            tick=ev.tick,
            kind=str(ev.payload.get("kind") or "incident"),
            truth=summary,
            perceived=summary,
            clarity="lived",
            importance=float(ev.payload.get("importance") or 0.5),
        ))
    shards.sort(key=lambda s: (-s.importance, s.tick))
    return shards[:limit]


async def compose_proxy_return_briefing(
    llm: LLM,
    world: World,
    player: Agent,
    memory: MemoryStore,
    store: EventStore,
    *,
    from_tick: int,
    npc_shifts: list[dict[str, str]] | None = None,
    stats_summary: dict[str, str] | None = None,
    rationale: str = "",
) -> WakeBriefing:
    """Briefing after the character continued as an NPC while the user was away."""
    to_tick = world.clock.tick
    shards = collect_lived_events(
        store, player_id=player.id, from_tick=from_tick, to_tick=to_tick,
    )
    ticks_away = max(0, to_tick - from_tick)
    npc_shifts = npc_shifts or []
    hint_parts = []
    if stats_summary:
        for k, v in stats_summary.items():
            hint_parts.append(f"{k}:{v}")
    world_stats_hint = "；".join(hint_parts)
    lived = "\n".join(f"- [t{s.tick}] {s.truth}" for s in shards) or "（平静度过，无大事）"
    shift_lines = "\n".join(
        f"- {s.get('name')}: {s.get('from')} → {s.get('to')}"
        for s in npc_shifts[:8]
    ) or "（人事如常）"

    sys = (
        f"你是《{world.name}》的归位叙事层。玩家重新上线——"
        f"但其角色【{player.name}】离线期间以自主意志（NPC 代行）继续参与了世界。"
        "用第二人称写 4-7 句清晰回顾：角色自己选择了继续活动、做过什么、眼前状况。"
        "语气如实，不应「错过」而应「亲历」。"
        "输出严格 JSON：{\"narrative\": str}"
    )
    usr = (
        f"角色：{player.name}（{player.persona}）\n"
        f"当时抉择：{rationale or '自主继续'}\n"
        f"离线时长：约 {ticks_away} 时辰（tick {from_tick}→{to_tick}）\n"
        f"此刻：{world.clock.label()}\n"
        f"亲历之事：\n{lived}\n"
        f"人事变化：\n{shift_lines}\n"
        f"宏观：{world_stats_hint or '不明'}\n"
    )
    resp = await llm.chat(
        [Message("system", sys), Message("user", usr)],
        temperature=0.8, max_tokens=420,
    )
    narrative = _extract_narrative(resp.content) or (
        f"你的意识重新扣回身体。这 {ticks_away} 个时辰里，"
        f"{player.name}并未沉睡——{rationale or '心有未了之事'}。"
        f"眼前是{world.clock.label()}，一段记忆历历在目"
        f"（约 {len(shards)} 桩亲历）。"
    )
    memory.add(player.id, "observation", f"【归位·代行结束】{narrative}", importance=0.8)
    return WakeBriefing(
        ticks_asleep=ticks_away,
        from_tick=from_tick,
        to_tick=to_tick,
        clock_label=world.clock.label(),
        narrative=narrative,
        shards=shards,
        npc_shifts=npc_shifts,
        world_stats_hint=world_stats_hint,
        offline_mode="proxy",
    )


def _extract_narrative(text: str) -> str | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    l, r = text.find("{"), text.rfind("}")
    if l != -1 and r != -1:
        try:
            data = json.loads(text[l : r + 1])
            n = data.get("narrative")
            if isinstance(n, str) and n.strip():
                return n.strip()
        except Exception:
            pass
    # plain prose fallback
    if len(text) > 20 and "{" not in text[:5]:
        return text
    return None


def _fallback_narrative(
    name: str, ticks: int, clock: str, shards: list[MissedShard],
) -> str:
    n_rumour = sum(1 for s in shards if s.clarity != "miss")
    return (
        f"你缓缓睁眼。墙上的光影已换到{clock}——"
        f"大约错过了 {ticks} 个时辰。"
        f"耳边尽是含混传闻（约 {n_rumour} 则隐约可辨），"
        f"其余之事像沉入水底。{name}知道：世界并未停下，只是你不在场。"
    )

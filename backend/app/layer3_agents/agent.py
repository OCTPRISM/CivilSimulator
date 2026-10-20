from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from ..layer1_foundation import LLM, Message
from .memory import MemoryStore

if TYPE_CHECKING:
    from ..layer2_civilization.world import World


class AgentKind(str, Enum):
    PLAYER = "player"     # human-controlled
    NPC = "npc"           # llm-controlled


class PresenceState(str, Enum):
    """Player characters only.

    ACTIVE  — user online, human-driven
    DORMANT — user offline, character sleeps and misses events
    PROXY   — user offline, character keeps acting like an NPC
    """
    ACTIVE = "active"
    DORMANT = "dormant"
    PROXY = "proxy"


@dataclass
class Agent:
    id: str
    name: str
    kind: AgentKind
    persona: str                 # short character bible
    goals: list[str] = field(default_factory=list)
    location_id: str | None = None
    traits: list[str] = field(default_factory=list)
    relations: dict[str, float] = field(default_factory=dict)  # other_id -> [-1,1]
    avatar: str = ""             # legacy emoji; UI uses appearance.figure
    appearance: dict = field(default_factory=dict)  # { figure: str, ... }

    # ---- profession & schedule (Phase 6b) ----
    profession: str = ""
    schedule: list[dict] = field(default_factory=list)  # [{from,to,location,activity}]
    economy: dict = field(default_factory=dict)         # static income spec
    current_activity: str = ""
    savings: float = 0.0
    today_income: float = 0.0
    today_customers: int = 0
    last_meal_tier: str = ""    # 差/中/好/无
    _last_day_settled: int = -1  # internal: last day for which expenses were paid

    # ---- dormancy / presence (players) ----
    presence: PresenceState = PresenceState.ACTIVE
    dormant_since_tick: int | None = None
    last_observed_tick: int = 0
    last_heartbeat_ts: float = field(default_factory=time.time)
    offline_mode: str = ""          # last offline choice: sleep | proxy
    offline_rationale: str = ""     # why the character chose that mode
    _saved_activity: str = ""       # restore after wake from sleep

    # ---- 3D world position (normalized map coords) ----
    world_x: float = 0.0
    world_z: float = 0.0
    behavior: str = "idle"          # idle | walk | work | drink | climb | swim | farm
    target_x: float | None = None
    target_z: float | None = None

    # ---- inventory / tasks ----
    inventory: list = field(default_factory=list)  # list[Item] at runtime
    equipment: dict = field(default_factory=dict)

    # ---- skills ----
    skills: list = field(default_factory=list)  # list[Skill] at runtime

    def is_dormant(self) -> bool:
        return self.presence == PresenceState.DORMANT

    def is_proxy(self) -> bool:
        return self.presence == PresenceState.PROXY

    def is_offline(self) -> bool:
        return self.presence in (PresenceState.DORMANT, PresenceState.PROXY)

    def enter_dormant(self, tick: int, *, rationale: str = "") -> None:
        if self.presence == PresenceState.DORMANT:
            return
        self.presence = PresenceState.DORMANT
        self.dormant_since_tick = tick
        self.offline_mode = "sleep"
        self.offline_rationale = rationale
        if self.current_activity and not self.current_activity.startswith("沉睡"):
            self._saved_activity = self.current_activity
        self.current_activity = "沉睡 / 离线休眠"
        self.behavior = "idle"

    def enter_proxy(self, tick: int, *, rationale: str = "") -> None:
        if self.presence == PresenceState.PROXY:
            return
        self.presence = PresenceState.PROXY
        self.dormant_since_tick = tick
        self.offline_mode = "proxy"
        self.offline_rationale = rationale
        if not self.current_activity or self.current_activity.startswith("沉睡"):
            self.current_activity = "离线代行 · 自主行动"
        self.behavior = "walk"

    def wake(self, tick: int) -> int | None:
        """Return the tick when offline began, or None if already active."""
        if self.presence == PresenceState.ACTIVE:
            return None
        since = self.dormant_since_tick
        was_sleep = self.presence == PresenceState.DORMANT
        self.presence = PresenceState.ACTIVE
        self.dormant_since_tick = None
        self.last_observed_tick = tick
        self.last_heartbeat_ts = time.time()
        if was_sleep:
            self.current_activity = self._saved_activity or ""
            self._saved_activity = ""
        elif self.current_activity.startswith("离线代行"):
            self.current_activity = ""
        return since

    def ensure_skills(self, genre: str = "ancient") -> None:
        if self.skills:
            return
        from .skills import build_skills_for
        self.skills = build_skills_for(
            profession=self.profession or "",
            traits=list(self.traits or []),
            genre=genre,
            name=self.name or "",
        )

    def use_skill(self, skill_id: str, tick: int) -> tuple[object | None, str]:
        """Mark skill used; return (skill, action_prompt) or (None, error)."""
        self.ensure_skills()
        for sk in self.skills:
            if sk.id == skill_id:
                if not sk.ready(tick):
                    left = sk.cooldown - (tick - sk.last_used_tick)
                    return None, f"技能冷却中（约余 {max(1, left)} 时辰）"
                sk.last_used_tick = tick
                return sk, sk.action_prompt or sk.name
        return None, "技能不存在"

    def init_inventory_from_economy(self) -> None:
        if self.inventory:
            return
        from .inventory import new_item, ItemKind
        start = float(self.economy.get("starting_savings", 0) or 0) if self.economy else 0
        if start:
            self.inventory.append(new_item("铜钱", ItemKind.GOLD, start))
        self.savings = start

    def system_prompt(self, world: World) -> str:
        from .context import ability_scope_rules, civilization_grounding, cognitive_scope_rules
        profession = f"\n职业：{self.profession}" if self.profession else ""
        return (
            f"你正在扮演角色【{self.name}】。\n"
            f"角色设定：{self.persona}\n"
            f"目标：{'；'.join(self.goals) or '尚未明确'}\n"
            f"性格标签：{', '.join(self.traits) or '中性'}"
            f"{profession}\n"
            f"---\n"
            f"{civilization_grounding(world)}\n"
            f"{cognitive_scope_rules(self)}\n"
            f"{ability_scope_rules(self)}\n"
            f"重要：请始终保持角色一致，用第一人称行动与说话，"
            f"反应须可信——符合文明环境、个人处境、认知范围与能力边界；"
            f"输出请严格遵循调用方要求的格式。"
        )

    async def think(
        self,
        world: World,
        memory: MemoryStore,
        scene_brief: str,
        llm: LLM,
        *,
        society=None,
        perception: dict | None = None,
        other_id: str | None = None,
        other_name: str = "",
        location_name: str | None = None,
        player_input: str | None = None,
    ) -> str:
        """Produce one in-character utterance/action for the current scene."""
        from .context import build_reaction_brief

        recall = await memory.recall(self.id, query=scene_brief, k_relevant=5, m_recent=4)
        recall_txt = "\n".join(f"- [{m.kind}] {m.content}" for m in recall) or "（无）"
        brief = build_reaction_brief(
            self, world,
            location_name=location_name,
            society=society,
            perception=perception,
            other_id=other_id,
            other_name=other_name,
        )
        player_line = (
            f"主角刚做/刚说：{player_input}\n\n" if player_input else ""
        )

        msgs = [
            Message("system", self.system_prompt(world)),
            Message(
                "user",
                f"{brief}\n\n"
                f"当前场景旁白：\n{scene_brief}\n\n"
                f"{player_line}"
                f"你脑海中浮现的相关记忆：\n{recall_txt}\n\n"
                f"请用 1-3 句话以第一人称给出你的【一次行动 + 一句台词】。"
                f"行动须落在你此刻能力与所见范围内；勿代替他人决策，勿知晓你看不见的事。"
                f"格式：动作（括号内）+ 台词。",
            ),
        ]
        resp = await llm.chat(msgs, temperature=0.9, max_tokens=200)
        return resp.content.strip()

    async def reply_to(
        self,
        world: World,
        memory: MemoryStore,
        speaker_name: str,
        speaker_text: str,
        llm: LLM,
        location_name: str | None = None,
        *,
        society=None,
        perception: dict | None = None,
        speaker_id: str | None = None,
    ) -> str:
        """One-shot in-character reply when a player addresses this NPC directly."""
        from .context import build_reaction_brief

        recall = await memory.recall(
            self.id, query=speaker_text, k_relevant=4, m_recent=4,
        )
        recall_txt = "\n".join(f"- [{m.kind}] {m.content}" for m in recall) or "（无）"
        brief = build_reaction_brief(
            self, world,
            location_name=location_name,
            society=society,
            perception=perception,
            other_id=speaker_id,
            other_name=speaker_name,
        )

        msgs = [
            Message("system", self.system_prompt(world)),
            Message(
                "user",
                f"{brief}\n\n"
                f"你脑海中浮现的相关记忆：\n{recall_txt}\n\n"
                f"【{speaker_name}】刚刚对你说：「{speaker_text}」\n\n"
                f"请以你的身份、人设、职业、关系与当下生计作出一段回复："
                f"动作描写（括号内，可选）与一两句口语台词。"
                f"可自然带出你此刻在做什么；若对方所求超出你的能力或见闻，应推辞或含糊带过。"
                f"不要超过 60 字。禁止跳出角色，禁止现代辞令。",
            ),
        ]
        resp = await llm.chat(msgs, temperature=0.85, max_tokens=180)
        return resp.content.strip()

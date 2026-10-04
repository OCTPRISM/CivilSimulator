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
        return (
            f"你正在扮演角色【{self.name}】。\n"
            f"角色设定：{self.persona}\n"
            f"目标：{'；'.join(self.goals) or '尚未明确'}\n"
            f"性格标签：{', '.join(self.traits) or '中性'}\n"
            f"---\n"
            f"你身处的世界：《{world.name}》（{world.genre}）。\n"
            f"世界设定：{world.premise}\n"
            f"世界法则：{'；'.join(world.rules)}\n"
            f"重要：请始终保持角色一致，用第一人称行动与说话，"
            f"输出请严格遵循调用方要求的格式。"
        )

    async def think(
        self,
        world: World,
        memory: MemoryStore,
        scene_brief: str,
        llm: LLM,
    ) -> str:
        """Produce one in-character utterance/action for the current scene."""
        recall = await memory.recall(self.id, query=scene_brief, k_relevant=5, m_recent=4)
        recall_txt = "\n".join(f"- [{m.kind}] {m.content}" for m in recall) or "（无）"

        msgs = [
            Message("system", self.system_prompt(world)),
            Message(
                "user",
                f"当前场景：\n{scene_brief}\n\n你脑海中浮现的相关记忆：\n{recall_txt}\n\n"
                f"请用 1-3 句话以第一人称给出你的【一次行动 + 一句台词】。"
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
    ) -> str:
        """One-shot in-character reply when a player addresses this NPC directly."""
        recall = await memory.recall(
            self.id, query=speaker_text, k_relevant=4, m_recent=4,
        )
        recall_txt = "\n".join(f"- [{m.kind}] {m.content}" for m in recall) or "（无）"
        loc = location_name or self.location_id or "未知之地"

        # current life context (profession / activity / economy)
        life_lines: list[str] = []
        if self.profession:
            life_lines.append(f"职业：{self.profession}")
        if self.current_activity:
            life_lines.append(f"此刻你正在：{self.current_activity}")
        if self.economy:
            unit = self.economy.get("unit", "笔")
            label = self.economy.get("income_label", "收入")
            life_lines.append(
                f"今日已得 {label} {self.today_income:g}（共 {self.today_customers} {unit}），"
                f"手头积蓄约 {self.savings:g}，最近一餐：{self.last_meal_tier or '未记'}"
            )
        life_ctx = "\n".join(life_lines) or "（无特别状态）"

        msgs = [
            Message("system", self.system_prompt(world)),
            Message(
                "user",
                f"你正在【{loc}】。\n"
                f"你的当下生活状态：\n{life_ctx}\n\n"
                f"你脑海中浮现的相关记忆：\n{recall_txt}\n\n"
                f"【{speaker_name}】刚刚对你说：「{speaker_text}」\n\n"
                f"请以你的身份、人设、职业与目标作出一段回复："
                f"动作描写（括号内，可选）与一两句口语台词，"
                f"可以自然带出你此刻在做什么或刚才挣到的钱。"
                f"不要超过 60 字。禁止跳出角色。",
            ),
        ]
        resp = await llm.chat(msgs, temperature=0.85, max_tokens=180)
        return resp.content.strip()

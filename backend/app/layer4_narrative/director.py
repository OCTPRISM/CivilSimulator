from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from ..config import get_settings
from ..layer1_foundation import LLM, Message
from ..layer2_civilization import World, WorldStats
from ..layer3_agents import Agent, AgentKind, MemoryStore, Society, reflect
from .scene import Beat, Page, Scene
from .choices import normalize_choices, choices_for_scene
from .tension import TensionTracker, make_conflict_injection


@dataclass
class Director:
    """Decides what happens next. Stateless beyond a page counter & chapter."""
    page_no: int = 0
    chapter: str = "第一章 · 序"
    rng: random.Random = field(default_factory=lambda: random.Random())
    tension: TensionTracker = field(default_factory=TensionTracker)
    stats: WorldStats = field(default_factory=WorldStats)
    pending_injection: str | None = None  # set when last page was too quiet

    # ---------- character generation ----------
    async def generate_player_agent(
        self,
        llm: LLM,
        world: World,
        description: str,
    ) -> Agent:
        """Turn a free-form player wish into a concrete Agent."""
        from uuid import uuid4

        sys = (
            "你是文明模拟器的角色生成器。请根据世界设定与玩家描述，"
            "生成一个符合世界观的角色。务必输出**严格 JSON**，字段："
            '{"name": str, "persona": str, "goals": [str,...], "traits": [str,...]}'
        )
        usr = (
            f"世界：《{world.name}》（{world.genre}）。\n"
            f"世界设定：{world.premise}\n"
            f"世界法则：{'；'.join(world.rules)}\n"
            f"玩家描述：{description}\n"
            f"请返回 JSON。"
        )
        resp = await llm.chat([Message("system", sys), Message("user", usr)],
                              temperature=0.9, max_tokens=400)
        data = _safe_json(resp.content) or {
            "name": "无名旅人",
            "persona": description or "一名身世成谜的旅人。",
            "goals": ["在这个世界活下去"],
            "traits": ["谨慎", "好奇"],
        }
        loc_id = next(iter(world.locations)) if world.locations else None
        return Agent(
            id=f"agent_{uuid4().hex[:10]}",
            name=data.get("name", "无名旅人"),
            kind=AgentKind.PLAYER,
            persona=data.get("persona", ""),
            goals=list(data.get("goals", [])),
            traits=list(data.get("traits", [])),
            location_id=loc_id,
        )

    async def generate_npcs_from_seed(
        self, llm: LLM, world: World, seed_archetypes: list[dict],
        count: int | None = None,
    ) -> list[Agent]:
        """Spawn one Agent per archetype and place them at their `home`
        location (if set), else round-robin across all world locations.
        `count` is honoured if provided (otherwise all archetypes are used).
        """
        from uuid import uuid4

        # name → location_id lookup
        name_to_id = {l.name: l.id for l in world.locations.values()}
        loc_ids = list(world.locations.keys())
        archetypes = list(seed_archetypes)
        if count is not None and count < len(archetypes):
            archetypes = self.rng.sample(archetypes, k=count)

        agents: list[Agent] = []
        for i, arc in enumerate(archetypes):
            home = arc.get("home")
            if home and home in name_to_id:
                loc_id = name_to_id[home]
            elif loc_ids:
                loc_id = loc_ids[i % len(loc_ids)]
            else:
                loc_id = None
            figure = arc.get("figure") or ""
            if not figure:
                from ..layer2_civilization.player_catalog import npc_figure_from_archetype
                figure = npc_figure_from_archetype(arc, world.genre)
            agents.append(Agent(
                id=f"agent_{uuid4().hex[:10]}",
                name=arc["name"],
                kind=AgentKind.NPC,
                persona=arc["persona"],
                goals=list(arc.get("goals", [])),
                traits=list(arc.get("traits", [])),
                location_id=loc_id,
                avatar=arc.get("avatar", ""),
                profession=arc.get("profession", ""),
                schedule=list(arc.get("schedule", [])),
                economy=dict(arc.get("economy", {})),
                savings=float(arc.get("economy", {}).get("starting_savings", 0)),
                last_meal_tier=arc.get("economy", {}).get("meal_tier", ""),
                appearance={"figure": figure},
            ))
        return agents

    # ---------- scene & page generation ----------
    def pick_scene(self, world: World, society: Society, player: Agent) -> Scene:
        if not world.locations:
            world.add_location("无名之地", "一片混沌初开的虚空。")
        # Prefer the player's current location.
        loc = world.locations.get(player.location_id) or next(iter(world.locations.values()))
        present = society.at(loc.id) or society.all()
        present = present[: max(2, min(4, len(present)))]
        if player.id not in [a.id for a in present]:
            present.insert(0, player)
        return Scene(
            location_id=loc.id,
            location_name=loc.name,
            summary=f"{world.clock.label()} — {loc.name}",
            present_agent_ids=[a.id for a in present],
        )

    async def direct_page(
        self,
        llm: LLM,
        world: World,
        society: Society,
        memory: MemoryStore,
        player: Agent,
        player_input: str | None = None,
    ) -> Page:
        """Produce ONE Flipbook page."""
        self.page_no += 1
        scene = self.pick_scene(world, society, player)
        beats: list[Beat] = []

        # 0. If the previous run flagged a low-tension period, inject a conflict event up-front.
        if self.pending_injection:
            beats.append(Beat(kind="system", speaker=None, content=self.pending_injection))
            memory.add(player.id, "observation", self.pending_injection, importance=0.9)
            self.pending_injection = None

        # 1. Narration via LLM (JSON-shaped so we can split fields cleanly).
        try:
            narration = await self._narrate(llm, world, scene, player, player_input,
                                            injected=beats[0].content if beats else None)
        except Exception:
            narration = {
                "narration": f"{scene.location_name}的风穿过石阶，{player.name}站定。",
                "choices": [c.as_dict() for c in choices_for_scene(
                    location_name=scene.location_name, genre=world.genre,
                )],
            }
        beats.append(Beat(kind="narration", speaker=None, content=narration["narration"]))

        # 2. Player's input (if any) becomes their action beat.
        if player_input:
            beats.append(Beat(kind="speech", speaker=player.name, content=player_input))
            memory.add(player.id, "action", player_input, importance=0.7)

        # 3. Each present NPC speaks/acts once (cap to keep opening page snappy).
        for aid in scene.present_agent_ids[:3]:
            ag = society.get(aid)
            if not ag or ag.id == player.id:
                continue
            try:
                line = await ag.think(world, memory, scene_brief=narration["narration"], llm=llm)
            except Exception:
                line = f"（{ag.name}沉默片刻，望向远处。）"
            beats.append(Beat(kind="speech", speaker=ag.name, content=line))
            memory.add(ag.id, "dialogue", line, importance=0.5)

        # 4. Build the page. World time and domain state are advanced only by
        # the continuous Ollama simulation tick, never by random drift here.
        page = Page(
            page_no=self.page_no,
            chapter=self.chapter,
            scene=scene,
            beats=beats,
            choices=normalize_choices(
                narration.get("choices"),
                location_name=scene.location_name,
                genre=world.genre,
            ),
        )
        score = self.tension.push(page)
        s = get_settings()

        # 5. Periodic NPC reflection (Generative-Agents style).
        if world.clock.tick % max(1, s.reflection_every_ticks) == 0:
            for ag in society.npcs():
                try:
                    await reflect(ag, memory, llm)
                except Exception:
                    pass

        page.tension = score
        return page

    async def _narrate(
        self, llm: LLM, world: World, scene: Scene, player: Agent, player_input: str | None,
        injected: str | None = None,
    ) -> dict:
        sys = (
            f"你是《{world.name}》的小说式叙事导演（{world.genre} 题材）。"
            "请用电影分镜般凝练的中文写一段 2-4 句的第三人称旁白，"
            "并给出 2-3 个**玩家看得懂**的下一步选项。"
            "每个选项必须包含：label（按钮短标题，6字内）、"
            "hint（一行白话说明后果/意图）、"
            "action（提交给叙事的完整行动描述，第一人称）。"
            "务必输出**严格 JSON**："
            '{"narration": str, "choices": [{"label": str, "hint": str, "action": str}, ...]}'
        )
        usr = (
            f"地点：{scene.location_name}\n"
            f"主角：{player.name}（{player.persona}）\n"
            f"在场：{', '.join(scene.present_agent_ids)}\n"
            f"上一幕玩家选择：{player_input or '（开场）'}\n"
            + (f"刚刚发生的突发事件：{injected}\n" if injected else "")
            + f"世界设定：{world.premise}"
        )
        resp = await llm.chat(
            [Message("system", sys), Message("user", usr)],
            temperature=0.85, max_tokens=350,
        )
        data = _safe_json(resp.content)
        if not data:
            data = {
                "narration": f"{scene.location_name}的风穿过石阶，{player.name}站定。",
                "choices": [c.as_dict() for c in choices_for_scene(
                    location_name=scene.location_name, genre=world.genre,
                )],
            }
        data["choices"] = normalize_choices(
            data.get("choices"),
            location_name=scene.location_name,
            genre=world.genre,
        )
        return data


def _safe_json(text: str) -> dict | None:
    """Best-effort JSON extraction from an LLM response."""
    text = text.strip()
    # crude fence stripping
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    # find first { ... last }
    l, r = text.find("{"), text.rfind("}")
    if l == -1 or r == -1:
        return None
    try:
        return json.loads(text[l : r + 1])
    except Exception:
        return None

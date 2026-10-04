"""Task board: work pay, story-generated quests, self-assigned goals."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from .inventory import Item, grant_rewards, inventory_to_dict, new_item, ItemKind


class TaskSource(str, Enum):
    WORK = "work"
    STORY = "story"
    SELF = "self"


class TaskStatus(str, Enum):
    OPEN = "open"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    title: str
    description: str
    source: TaskSource
    status: TaskStatus = TaskStatus.OPEN
    rewards: dict = field(default_factory=dict)
    tick_created: int = 0
    tick_deadline: int | None = None
    location_id: str | None = None
    keywords: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source": self.source.value,
            "status": self.status.value,
            "rewards": dict(self.rewards),
            "tick_created": self.tick_created,
            "tick_deadline": self.tick_deadline,
            "location_id": self.location_id,
            "keywords": list(self.keywords),
        }


@dataclass
class TaskBoard:
    """Per-player task lists keyed by agent_id."""
    _tasks: dict[str, list[Task]] = field(default_factory=dict)

    def for_agent(self, agent_id: str) -> list[Task]:
        return self._tasks.setdefault(agent_id, [])

    def open_tasks(self, agent_id: str) -> list[Task]:
        return [t for t in self.for_agent(agent_id) if t.status == TaskStatus.OPEN]

    def add(self, agent_id: str, task: Task) -> Task:
        self.for_agent(agent_id).append(task)
        return task

    def create_self_task(
        self, agent_id: str, *, title: str, description: str,
        tick: int, rewards: dict | None = None, deadline_ticks: int = 48,
    ) -> Task:
        task = Task(
            id=f"task_{uuid4().hex[:8]}",
            title=title,
            description=description or title,
            source=TaskSource.SELF,
            rewards=rewards or {"gold": 15},
            tick_created=tick,
            tick_deadline=tick + deadline_ticks,
        )
        return self.add(agent_id, task)

    def create_story_task(
        self, agent_id: str, *, title: str, description: str,
        tick: int, location_id: str | None = None,
        rewards: dict | None = None,
    ) -> Task | None:
        open_ = self.open_tasks(agent_id)
        if any(t.source == TaskSource.STORY and t.title == title for t in open_):
            return None
        task = Task(
            id=f"task_{uuid4().hex[:8]}",
            title=title,
            description=description,
            source=TaskSource.STORY,
            rewards=rewards or {"gold": 30, "equipment": ["线索卷轴"]},
            tick_created=tick,
            tick_deadline=tick + 72,
            location_id=location_id,
            keywords=_keywords_from_text(description),
        )
        return self.add(agent_id, task)

    def ensure_work_task(self, agent_id: str, profession: str, tick: int) -> Task | None:
        if not profession:
            return None
        open_ = self.open_tasks(agent_id)
        if any(t.source == TaskSource.WORK for t in open_):
            return None
        task = Task(
            id=f"task_{uuid4().hex[:8]}",
            title=f"完成今日{profession}工作",
            description=f"按职业「{profession}」完成一个工作时段，领取薪酬。",
            source=TaskSource.WORK,
            rewards={"gold": 0},  # pay comes from economy on complete
            tick_created=tick,
            tick_deadline=tick + 12,
            keywords=["工作", "劳作", "营生", profession[:4] if len(profession) >= 2 else profession],
        )
        return self.add(agent_id, task)

    def complete(
        self, agent_id: str, task_id: str, *,
        inventory: list[Item], savings: float, profession: str, economy: dict,
    ) -> tuple[Task | None, list[Item], float, dict]:
        tasks = self.for_agent(agent_id)
        task = next((t for t in tasks if t.id == task_id and t.status == TaskStatus.OPEN), None)
        if not task:
            return None, inventory, savings, {"error": "task not found"}

        task.status = TaskStatus.COMPLETED
        pay = 0.0
        if task.source == TaskSource.WORK:
            unit = float(economy.get("income_per_unit", 10) or 10)
            cap = int(economy.get("daily_capacity", 3) or 3)
            pay = unit * max(1, min(cap, 3))
            savings += pay
        inv = grant_rewards(inventory, task.rewards)
        if pay:
            inv = grant_rewards(inv, {"gold": pay})
        return task, inv, savings, {
            "task": task.as_dict(),
            "pay": pay,
            "inventory": inventory_to_dict(inv),
            "savings": savings,
        }

    def try_auto_complete_from_input(
        self, agent_id: str, text: str, *,
        inventory: list[Item], savings: float, profession: str, economy: dict,
    ) -> tuple[list[Task], list[Item], float]:
        """Complete open tasks whose keywords match player input."""
        completed: list[Task] = []
        inv, sav = inventory, savings
        for t in list(self.open_tasks(agent_id)):
            if t.source == TaskSource.WORK:
                if any(kw in text for kw in t.keywords) or any(
                    w in text for w in ("工作", "劳作", "营生", "上工", "接活")
                ):
                    ct, inv, sav, _ = self.complete(
                        agent_id, t.id, inventory=inv, savings=sav,
                        profession=profession, economy=economy,
                    )
                    if ct:
                        completed.append(ct)
            elif t.keywords and any(kw in text for kw in t.keywords):
                ct, inv, sav, _ = self.complete(
                    agent_id, t.id, inventory=inv, savings=sav,
                    profession=profession, economy=economy,
                )
                if ct:
                    completed.append(ct)
        return completed, inv, sav

    def snapshot(self, agent_id: str) -> list[dict]:
        return [t.as_dict() for t in self.for_agent(agent_id)]


def _keywords_from_text(text: str) -> list[str]:
    kws = []
    for w in ("查", "寻", "探", "送", "杀", "救", "护", "取", "报"):
        if w in text:
            kws.append(w)
    return kws or ["调查"]


def story_task_from_event(summary: str, tick: int, location_id: str | None) -> tuple[str, str, dict]:
    """Derive a quest offer from a world incident."""
    title = "追查异动"
    if "血" in summary or "杀" in summary:
        title = "血案追索"
    elif "密信" in summary or "悬赏" in summary:
        title = "暗线调查"
    elif "灵气" in summary or "阵" in summary:
        title = "异象勘验"
    rewards = {"gold": 25 + random.randint(0, 20)}
    if random.random() < 0.4:
        rewards["food"] = ["干粮"]
    if random.random() < 0.25:
        rewards["equipment"] = ["旧式护腕"]
    return title, f"坊间传闻：{summary[:60]}… 是否介入？", rewards

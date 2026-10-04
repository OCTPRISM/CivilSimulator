"""Agent skill catalog — basic actions + profession/trait unique skills."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Skill:
    id: str
    name: str
    kind: str              # basic | unique
    description: str = ""
    cooldown: int = 0      # ticks between uses; 0 = free always
    last_used_tick: int = -999
    action_prompt: str = ""  # text fed into director as player_input

    def ready(self, tick: int) -> bool:
        return (tick - self.last_used_tick) >= max(0, self.cooldown)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "cooldown": self.cooldown,
            "last_used_tick": self.last_used_tick,
            "action_prompt": self.action_prompt or self.name,
            "ready": True,  # caller may overwrite with tick-aware ready
        }


BASIC_ACTIONS: list[dict] = [
    {
        "name": "观察四周", "description": "打量环境与人物动向",
        "action_prompt": "静立观察四周，仔细打量此地人事。",
    },
    {
        "name": "靠近", "description": "走近眼前之人或事发中心",
        "action_prompt": "我走上前去，逼近眼前之人。",
    },
    {
        "name": "交谈", "description": "开口试探",
        "action_prompt": "出声试探旁边的人，想打听些消息。",
    },
    {
        "name": "稍作歇息", "description": "稳住气息",
        "action_prompt": "原地稍作歇息，调匀呼吸，留意动静。",
    },
]


# profession substring → unique skills
_PROFESSION_SKILLS: list[tuple[str, list[dict]]] = [
    ("剑", [
        {"name": "拔剑试锋", "description": "亮剑震慑", "cooldown": 3,
         "action_prompt": "按住剑柄，微微拔剑试锋，气势外放。"},
        {"name": "剑气斜飞", "description": "远程牵制", "cooldown": 6,
         "action_prompt": "一缕剑气斜飞而出，遥遥指向对方颈侧。"},
    ]),
    ("杀手", [
        {"name": "隐匿行踪", "description": "收敛气息", "cooldown": 4,
         "action_prompt": "呼吸放缓，人影贴向暗处，隐匿行踪。"},
        {"name": "夜刺", "description": "突发一击", "cooldown": 8,
         "action_prompt": "袖中短刃一闪，朝着对方要害骤然刺去。"},
    ]),
    ("丐帮", [
        {"name": "打狗棍式", "description": "杆棒虚晃", "cooldown": 4,
         "action_prompt": "信手掂起竹杆，使一式打狗棍法虚晃试探。"},
        {"name": "耳报神通", "description": "打听情报", "cooldown": 3,
         "action_prompt": "凑近路人低声套话，打听近日江湖风声。"},
    ]),
    ("摆渡", [
        {"name": "摆渡", "description": "载人过江", "cooldown": 2,
         "action_prompt": "解缆摆渡，要把人送到江对岸。"},
    ]),
    ("船", [
        {"name": "听江声", "description": "辨识水情", "cooldown": 3,
         "action_prompt": "侧耳听水，凭江声判断来人与暗流。"},
    ]),
    ("说书", [
        {"name": "醒木一拍", "description": "引人注目", "cooldown": 2,
         "action_prompt": "醒木一拍，朗声讲起眼前之事。"},
    ]),
    ("账", [
        {"name": "查账点库", "description": "清点财物", "cooldown": 4,
         "action_prompt": "摊开账册，仔细核对出入银两。"},
    ]),
    ("管事", [
        {"name": "发号施令", "description": "调动人手", "cooldown": 5,
         "action_prompt": "抬手示意左右，发号施令调度人手。"},
    ]),
    ("侦探", [
        {"name": "搜查现场", "description": "找线索", "cooldown": 3,
         "action_prompt": "蹲下仔细搜查现场蛛丝马迹。"},
    ]),
    ("医师", [
        {"name": "诊脉", "description": "辨识伤势", "cooldown": 3,
         "action_prompt": "伸出二指，诊脉察色。"},
    ]),
]


_TRAIT_SKILLS: list[tuple[str, dict]] = [
    ("执拗", {"name": "咬定不放", "description": "追问到底", "cooldown": 4,
             "action_prompt": "追问一句，咬定疑点不肯放过。"}),
    ("热血", {"name": "挺身而出", "description": "挺身护人", "cooldown": 5,
             "action_prompt": "挺身而出，挡在弱者身前。"}),
    ("机敏", {"name": "眼观六路", "description": "察觉异常", "cooldown": 3,
             "action_prompt": "眼观六路，捕捉周围异常细节。"}),
    ("冷酷", {"name": "杀意凝视", "description": "压迫对手", "cooldown": 4,
             "action_prompt": "以杀意凝视对方，压迫其心神。"}),
    ("好奇", {"name": "追根问底", "description": "探查秘密", "cooldown": 3,
             "action_prompt": "按捺不住好奇，追根问底。"}),
]


_GENRE_DEFAULT_UNIQUE: dict[str, list[dict]] = {
    "wuxia": [
        {"name": "运功护体", "description": "内力护身", "cooldown": 5,
         "action_prompt": "运起内力护住周身要害。"},
    ],
    "ancient": [
        {"name": "引经据典", "description": "文言说理", "cooldown": 3,
         "action_prompt": "引经据典，当面辩理。"},
    ],
    "scifi": [
        {"name": "扫描分析", "description": "仪器侦测", "cooldown": 4,
         "action_prompt": "打开手持终端，扫描分析周围能量与生命体征。"},
    ],
    "xuanhuan": [
        {"name": "聚灵凝气", "description": "积蓄灵力", "cooldown": 5,
         "action_prompt": "盘膝聚灵，凝气于丹田。"},
    ],
    "mystery": [
        {"name": "推演案情", "description": "逻辑串联", "cooldown": 4,
         "action_prompt": "在心里推演案情，把细节串成一条线。"},
    ],
}


def _mk(spec: dict, kind: str) -> Skill:
    return Skill(
        id=f"sk_{uuid4().hex[:8]}",
        name=spec["name"],
        kind=kind,
        description=spec.get("description", ""),
        cooldown=int(spec.get("cooldown", 0)),
        action_prompt=spec.get("action_prompt") or spec["name"],
    )


def build_skills_for(
    *,
    profession: str = "",
    traits: list[str] | None = None,
    genre: str = "ancient",
    name: str = "",
) -> list[Skill]:
    """Compose basic + unique skills for an agent."""
    skills = [_mk(s, "basic") for s in BASIC_ACTIONS]
    traits = traits or []
    seen = {s.name for s in skills}

    for key, specs in _PROFESSION_SKILLS:
        if key in (profession or "") or key in (name or ""):
            for sp in specs:
                if sp["name"] not in seen:
                    skills.append(_mk(sp, "unique"))
                    seen.add(sp["name"])

    for trait, sp in _TRAIT_SKILLS:
        if any(trait in t for t in traits):
            if sp["name"] not in seen:
                skills.append(_mk(sp, "unique"))
                seen.add(sp["name"])

    for sp in _GENRE_DEFAULT_UNIQUE.get(genre, []):
        if sp["name"] not in seen and sum(1 for s in skills if s.kind == "unique") < 3:
            skills.append(_mk(sp, "unique"))
            seen.add(sp["name"])

    # Ensure at least one unique
    if not any(s.kind == "unique" for s in skills):
        skills.append(_mk({
            "name": "临机一念", "description": "随机应变", "cooldown": 4,
            "action_prompt": "凭临机一念，做出意料之外的举动。",
        }, "unique"))
    return skills


def skills_to_dict(skills: list[Skill], tick: int = 0) -> list[dict]:
    out = []
    for s in skills:
        d = s.as_dict()
        d["ready"] = s.ready(tick)
        out.append(d)
    return out

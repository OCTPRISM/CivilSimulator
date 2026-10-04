"""WorldStats — five 0..100 indicators describing the simulated world.

politics  : 朝堂稳定 / 治理 (高=稳定，低=动乱)
economy   : 经济繁荣 (高=繁荣，低=萧条)
livelihood: 民生 / 民心 (高=安乐，低=苦难)
military  : 军事强度 / 战争烈度 (高=战意/兵威盛，低=偃旗息鼓)
environment: 环境与基础设施健康度 (高=稳定宜居，低=灾变/破败)
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field


@dataclass
class WorldStats:
    politics: float = 60.0
    economy: float = 55.0
    livelihood: float = 60.0
    military: float = 40.0
    environment: float = 65.0

    history: deque = field(default_factory=lambda: deque(maxlen=64))

    # one-line genre-flavoured summaries last computed
    summary: dict = field(default_factory=lambda: {
        "politics": "局势平稳。",
        "economy": "市井如常。",
        "livelihood": "百姓尚安。",
        "military": "刀兵未起。",
        "environment": "山川与聚落尚且安稳。",
    })

    def snapshot(self) -> dict:
        return {
            "politics": round(self.politics, 1),
            "economy": round(self.economy, 1),
            "livelihood": round(self.livelihood, 1),
            "military": round(self.military, 1),
            "environment": round(self.environment, 1),
            "history": list(self.history),
            "summary": dict(self.summary),
        }

    def push_history(self) -> None:
        self.history.append({
            "politics": round(self.politics, 1),
            "economy": round(self.economy, 1),
            "livelihood": round(self.livelihood, 1),
            "military": round(self.military, 1),
            "environment": round(self.environment, 1),
        })

    def evolve(self, tension: float, rng: random.Random | None = None) -> None:
        """Rule-based evolution driven by current dramatic tension (0..1).

        High tension → military up, livelihood/economy down, politics fluctuates.
        Low tension  → slow recovery toward 60.
        """
        rng = rng or random.Random()

        def clamp(v: float) -> float:
            return max(0.0, min(100.0, v))

        if tension >= 0.6:
            self.military += rng.uniform(2.0, 5.0) * (tension)
            self.livelihood -= rng.uniform(1.5, 3.5) * (tension)
            self.economy -= rng.uniform(1.0, 2.5) * (tension)
            self.politics += rng.uniform(-3.0, 1.5)
        elif tension <= 0.35:
            # peaceful drift toward equilibrium
            self.military += (40 - self.military) * 0.05 + rng.uniform(-0.6, 0.6)
            self.economy += (60 - self.economy) * 0.04 + rng.uniform(-0.4, 1.0)
            self.livelihood += (60 - self.livelihood) * 0.05 + rng.uniform(-0.3, 0.8)
            self.politics += (60 - self.politics) * 0.03 + rng.uniform(-0.5, 0.8)
        else:
            # mid-tension: small noise
            self.military += rng.uniform(-1.0, 1.5)
            self.economy += rng.uniform(-1.2, 1.2)
            self.livelihood += rng.uniform(-1.0, 1.0)
            self.politics += rng.uniform(-1.0, 1.0)

        self.politics = clamp(self.politics)
        self.economy = clamp(self.economy)
        self.livelihood = clamp(self.livelihood)
        self.military = clamp(self.military)
        self.push_history()

    def update_summaries(self, genre: str) -> None:
        self.summary = {
            "politics": _band(self.politics, _POLITICS_BANDS.get(genre, _POLITICS_BANDS["default"])),
            "economy": _band(self.economy, _ECONOMY_BANDS.get(genre, _ECONOMY_BANDS["default"])),
            "livelihood": _band(self.livelihood, _LIVELIHOOD_BANDS.get(genre, _LIVELIHOOD_BANDS["default"])),
            "military": _band(self.military, _MILITARY_BANDS.get(genre, _MILITARY_BANDS["default"])),
        }


def _band(value: float, bands: list[tuple[float, str]]) -> str:
    for upper, label in bands:
        if value <= upper:
            return label
    return bands[-1][1]


# (upper-bound, summary)
_POLITICS_BANDS = {
    "default": [(20, "朝纲崩坏，奸佞当道。"), (45, "党争渐烈，政令难通。"),
                (70, "庙堂尚稳，暗流涌动。"), (100, "君明臣贤，海内宴然。")],
    "scifi":   [(20, "议会瘫痪，企业王侯割据。"), (45, "联邦内讧，AI议事不决。"),
                (70, "联邦运转，舆情可控。"), (100, "理性议事，星海一统。")],
    "wuxia":   [(20, "朝廷倾颓，江湖混战。"), (45, "庙堂江湖各执一词。"),
                (70, "盟主仍在，规矩犹存。"), (100, "群侠归心，江湖太平。")],
    "xuanhuan":[(20, "天庭震荡，秩序崩散。"), (45, "九州道宗各立门户。"),
                (70, "天道运转，仙凡有序。"), (100, "天人合一，万法归宗。")],
    "mystery": [(20, "权力地下化，无人可信。"), (45, "明面安宁，暗处交易频繁。"),
                (70, "表象井然，疑云未散。"), (100, "诸事皆在掌握。")],
}
_ECONOMY_BANDS = {
    "default": [(20, "市井凋敝，百业俱衰。"), (45, "粮价腾贵，钱法紊乱。"),
                (70, "商旅往来，仓廪渐丰。"), (100, "万商辐辏，富甲一方。")],
    "scifi":   [(20, "供应链断裂，星港停摆。"), (45, "通胀失控，配给制启动。"),
                (70, "贸易站运转，信用稳定。"), (100, "星际贸易繁荣。")],
    "wuxia":   [(20, "镖局难行，钱庄倒闭。"), (45, "盐铁紧俏，江湖交易盛。"),
                (70, "镖路畅通，市集兴旺。"), (100, "金山银海，富可敌国。")],
    "xuanhuan":[(20, "灵脉枯竭，灵石难求。"), (45, "灵材紧俏，丹药昂贵。"),
                (70, "灵市开张，宗门富足。"), (100, "灵气充沛，万宝竞献。")],
    "mystery": [(20, "黑市横行，正道萧条。"), (45, "经济暗潮，账目可疑。"),
                (70, "明面繁荣。"), (100, "财脉光鲜，背后存疑。")],
}
_LIVELIHOOD_BANDS = {
    "default": [(20, "饿殍载道，民怨沸腾。"), (45, "苛政繁多，民有菜色。"),
                (70, "炊烟可闻，安居乐业。"), (100, "夜不闭户，路不拾遗。")],
    "scifi":   [(20, "贫民窟蔓延，反乌托邦化。"), (45, "中产挤压，焦虑弥漫。"),
                (70, "公民安居，AI辅政。"), (100, "全民富足，意识自由。")],
    "wuxia":   [(20, "义庄遍野，难民流徙。"), (45, "苛捐杂税，行旅艰难。"),
                (70, "酒馆茶肆人来人往。"), (100, "市井欢腾，侠风长存。")],
    "xuanhuan":[(20, "凡人涂炭，仙不顾下界。"), (45, "生灵承压，修行艰难。"),
                (70, "炊烟袅袅，凡仙相安。"), (100, "万民诚拜，香火鼎盛。")],
    "mystery": [(20, "失踪频发，人心惶惶。"), (45, "诡谈四起，夜不出户。"),
                (70, "市民如常，疑窦私语。"), (100, "表面平静。")],
}
_MILITARY_BANDS = {
    "default": [(20, "刀枪入库，马放南山。"), (45, "边镇戒备，未起烽烟。"),
                (70, "兵戈未息，战云密布。"), (100, "全境征伐，伏尸百万。")],
    "scifi":   [(20, "舰队休整，星空寂静。"), (45, "前哨警戒。"),
                (70, "舰队集结，战云压境。"), (100, "全面星战。")],
    "wuxia":   [(20, "刀兵入鞘，门派和议。"), (45, "暗器频出，比武不止。"),
                (70, "门派械斗，血溅五步。"), (100, "正邪大战，山河震动。")],
    "xuanhuan":[(20, "法宝封存，万灵息斗。"), (45, "宗门小斗，斗法时起。"),
                (70, "天劫将至，群仙备战。"), (100, "万法齐发，天倾地裂。")],
    "mystery": [(20, "暗杀沉寂。"), (45, "暗流涌动，组织备战。"),
                (70, "对手交锋，伤亡频传。"), (100, "明面战争已起。")],
}

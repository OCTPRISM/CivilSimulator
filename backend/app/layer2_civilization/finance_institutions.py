"""Era-matched financial institutions per civilization genre.

Each institution has a defined role in the sandbox — not decorative labels.
They modulate event transmission and appear in audit trails / reports.
"""
from __future__ import annotations

from typing import Any

# institution_type: fiscal_regulator | central_bank | exchange | guild | clearing | credit
_INSTITUTIONS: dict[str, list[dict[str, Any]]] = {
    "ancient": [
        {
            "key": "hubu",
            "name": "户部",
            "institution_type": "fiscal_regulator",
            "era_label": "唐·永和",
            "roles": ["户籍税赋", "漕运调度", "国库收支"],
            "description": "掌天下户籍、田赋、漕运与国库，调控盐铁专卖与赈济。",
            "transmission": {"policy": 1.15, "rate": 0.9, "political": 1.1},
        },
        {
            "key": "salt_iron",
            "name": "盐铁司",
            "institution_type": "monopoly",
            "era_label": "唐·专卖",
            "roles": ["盐铁专卖", "价控", "商税"],
            "description": "垄断盐铁之利，平粜抑价，战时加榷。",
            "transmission": {"price": 1.2, "supply_shock": 0.85, "policy": 1.05},
        },
        {
            "key": "guifang",
            "name": "柜坊",
            "institution_type": "credit",
            "era_label": "唐·柜坊",
            "roles": ["质库借贷", "飞钱汇兑", "保管金银"],
            "description": "唐代质库与飞钱汇兑，为商旅与官绅提供信贷与保管。",
            "transmission": {"rate": 1.1, "liquidity": 1.2, "custom": 1.0},
        },
        {
            "key": "caoyun_si",
            "name": "转运使司",
            "institution_type": "clearing",
            "era_label": "唐·漕运",
            "roles": ["漕粮调度", "仓储征发", "河运征调"],
            "description": "掌漕运调度与仓储征发，连接粮道与户部收支。",
            "transmission": {"policy": 1.05, "price": 1.08, "war": 0.92},
        },
    ],
    "wuxia": [
        {
            "key": "escort_guild",
            "name": "天下镖局联盟",
            "institution_type": "guild",
            "era_label": "江湖·明",
            "roles": ["押运保险", "跨路清算", "江湖仲裁"],
            "description": "统合镖局押运、路线保险与江湖商路信用。",
            "transmission": {"war": 0.88, "custom": 1.1, "rate": 1.05},
        },
        {
            "key": "river_hall",
            "name": "风波渡钱堂",
            "institution_type": "credit",
            "era_label": "渡口金融",
            "roles": ["船资信贷", "货栈抵押", "汇兑"],
            "description": "渡口货栈抵押与船资借贷，江湖贸易枢纽。",
            "transmission": {"liquidity": 1.2, "price": 1.05, "political": 0.95},
        },
        {
            "key": "salt_guild",
            "name": "两淮盐商公会",
            "institution_type": "guild",
            "era_label": "盐商",
            "roles": ["盐引交易", "专卖套利", "商帮信贷"],
            "description": "盐引买卖与商帮内部拆借，影响区域物价。",
            "transmission": {"price": 1.15, "policy": 1.08, "supply_shock": 0.9},
        },
    ],
    "xuanhuan": [
        {
            "key": "spirit_bank",
            "name": "灵石钱庄",
            "institution_type": "credit",
            "era_label": "修真界",
            "roles": ["灵石汇兑", "丹药抵押", "宗门信贷"],
            "description": "灵石标准汇兑与丹药质押借贷，服务宗门与散修。",
            "transmission": {"liquidity": 1.3, "rate": 1.1, "custom": 1.05},
        },
        {
            "key": "auction_hall",
            "name": "天机拍卖行",
            "institution_type": "exchange",
            "era_label": "修真拍卖",
            "roles": ["法器定价", "灵材流通", "秘境份额"],
            "description": "法器灵材公开竞价，形成区域基准价。",
            "transmission": {"price": 1.18, "product": 1.12, "earnings": 1.08},
        },
        {
            "key": "sect_treasury",
            "name": "宗门库司",
            "institution_type": "fiscal_regulator",
            "era_label": "宗门财政",
            "roles": ["资源配给", "灵脉税", "弟子俸禄"],
            "description": "宗门内部资源分配与灵脉税赋，影响凡俗界流通。",
            "transmission": {"policy": 1.12, "political": 1.05, "supply_shock": 0.95},
        },
    ],
    "mystery": [
        {
            "key": "port_bank",
            "name": "雾港信托银行",
            "institution_type": "central_bank",
            "era_label": "1931·雾港",
            "roles": ["贴现", "外汇", "港口信贷"],
            "description": "大萧条时代的港口银行，贴现汇票与航运信贷。",
            "transmission": {"rate": 1.2, "liquidity": 1.15, "political": 1.1},
        },
        {
            "key": "dock_exchange",
            "name": "码头商品交易所",
            "institution_type": "exchange",
            "era_label": "1930s",
            "roles": ["期货定价", "仓单", "航运指数"],
            "description": "棉花、橡胶等期货与仓单交易，价格发现中心。",
            "transmission": {"price": 1.22, "supply_shock": 1.05, "war": 0.9},
        },
    ],
    "modern": [
        {
            "key": "central_bank",
            "name": "都会中央银行",
            "institution_type": "central_bank",
            "era_label": "当代",
            "roles": ["货币政策", "LPR", "金融稳定"],
            "description": "制定政策利率、维护流动性、宏观审慎监管。",
            "transmission": {"rate": 1.25, "liquidity": 1.2, "policy": 1.1},
        },
        {
            "key": "stock_exchange",
            "name": "都会证券交易所",
            "institution_type": "exchange",
            "era_label": "当代",
            "roles": ["IPO", "二级市场", "指数"],
            "description": "股权融资与二级市场交易，发布综合指数。",
            "transmission": {"earnings": 1.15, "political": 1.08, "price": 1.05},
        },
        {
            "key": "cbirc",
            "name": "银行保险监管局",
            "institution_type": "fiscal_regulator",
            "era_label": "当代",
            "roles": ["资本充足率", "按揭政策", "风险处置"],
            "description": "银行保险业监管，地产与 SME 信贷政策。",
            "transmission": {"property": 1.2, "rate": 1.08, "scandal": 1.1},
        },
    ],
    "scifi": [
        {
            "key": "orbital_reserve",
            "name": "环带联邦储备",
            "institution_type": "central_bank",
            "era_label": "2387",
            "roles": ["信用点发行", "轨道关税", "能源配额"],
            "description": "殖民地信用点与能源配额调控，轨道港关税政策。",
            "transmission": {"rate": 1.2, "policy": 1.15, "supply_shock": 1.05},
        },
        {
            "key": "clearing_hub",
            "name": "轨道清算中枢",
            "institution_type": "clearing",
            "era_label": "星际清算",
            "roles": ["跨港结算", "算力期货", "船体抵押"],
            "description": "跨轨道港实时清算与算力合约结算。",
            "transmission": {"liquidity": 1.25, "price": 1.1, "product": 1.08},
        },
    ],
    "enterprise": [
        {
            "key": "vc_syndicate",
            "name": "创投联合体",
            "institution_type": "credit",
            "era_label": "2020s",
            "roles": ["A-D轮", "可转债", "并购融资"],
            "description": "聚合 VC/PE 进行轮次定价与并购融资。",
            "transmission": {"earnings": 1.2, "product": 1.15, "rate": 1.05},
        },
        {
            "key": "saas_exchange",
            "name": "创业股权托管中心",
            "institution_type": "exchange",
            "era_label": "2020s",
            "roles": ["期权池", "ESOP", "二级转让"],
            "description": "未上市股权与期权池托管、二级份额转让。",
            "transmission": {"earnings": 1.1, "scandal": 1.12, "policy": 1.05},
        },
    ],
    "securities": [
        {
            "key": "sec_regulator",
            "name": "证券监管委员会",
            "institution_type": "fiscal_regulator",
            "era_label": "当代",
            "roles": ["注册制", "信息披露", "交易监管"],
            "description": "上市审核、信息披露与交易行为监管。",
            "transmission": {"scandal": 1.25, "policy": 1.12, "political": 1.08},
        },
        {
            "key": "clearing_house",
            "name": "中央清算所",
            "institution_type": "clearing",
            "era_label": "当代",
            "roles": ["衍生品清算", "保证金", "系统性风险"],
            "description": "衍生品中央对手方清算与保证金管理。",
            "transmission": {"rate": 1.15, "liquidity": 1.18, "war": 0.92},
        },
    ],
    "military": [
        {
            "key": "arsenal_fund",
            "name": "军工产业基金",
            "institution_type": "credit",
            "era_label": "当代军工",
            "roles": ["装备采购", "研发信贷", "后勤融资"],
            "description": "装备研发与采购专项融资，战时加急拨款。",
            "transmission": {"war": 1.15, "policy": 1.2, "supply_shock": 0.88},
        },
        {
            "key": "defense_clearing",
            "name": "后勤清算局",
            "institution_type": "clearing",
            "era_label": "当代军工",
            "roles": ["军需结算", "油料配额", "弹药库存"],
            "description": "军需物资结算与战略库存调配。",
            "transmission": {"supply_shock": 1.1, "price": 1.08, "custom": 1.05},
        },
    ],
    "custom": [
        {
            "key": "civic_bank",
            "name": "文明中央银行",
            "institution_type": "central_bank",
            "era_label": "自定义",
            "roles": ["货币发行", "信贷政策", "稳定"],
            "description": "该文明通用中央银行职能。",
            "transmission": {"rate": 1.15, "liquidity": 1.15, "policy": 1.1},
        },
    ],
}

_TYPE_LABELS = {
    "fiscal_regulator": "财政/监管",
    "central_bank": "中央银行",
    "exchange": "交易所",
    "guild": "行会/公会",
    "clearing": "清算",
    "credit": "信贷/投行",
    "monopoly": "专卖",
}


def get_finance_institutions(genre: str, seed_key: str = "") -> list[dict[str, Any]]:
    rows = list(_INSTITUTIONS.get(genre) or _INSTITUTIONS["custom"])
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        row["institution_type_label"] = _TYPE_LABELS.get(row["institution_type"], row["institution_type"])
        row["civilization_key"] = seed_key
        out.append(row)
    return out


def institution_modifiers(genre: str, event_kind: str) -> dict[str, float]:
    """Aggregate transmission multipliers from all institutions for an event kind."""
    mult: dict[str, float] = {}
    for inst in get_finance_institutions(genre):
        tx = inst.get("transmission") or {}
        for ch, m in tx.items():
            if ch == event_kind or event_kind in ("custom", "political", "policy"):
                mult[ch] = mult.get(ch, 1.0) * float(m)
    return mult


def institutions_for_audit(genre: str) -> list[dict[str, str]]:
    return [
        {
            "name": i["name"],
            "era": i.get("era_label", ""),
            "roles": "、".join(i.get("roles") or []),
            "type": i.get("institution_type_label", ""),
        }
        for i in get_finance_institutions(genre)
    ]

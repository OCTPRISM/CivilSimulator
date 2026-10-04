#!/usr/bin/env python3
"""
Generate multi-city map layouts with natural separators and roadside buildings.

Rules encoded:
1. Each genre has a UNIQUE city topology + terrain seed (never the same map twice)
2. Cities separated by mountains / forests / lakes / fields
3. Buildings only along planned street edges (never on asphalt)
4. Streets are PLANNED per genre (imperial / valley / radial / harbor / metro / orbital)
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "maps"
W, H = 960, 540

# Distinct layouts: city positions, street plan, terrain mood — one identity per genre.
# City names aligned with backend/app/seeds/*.json locations.
GENRE_META = {
  "ancient": {
    "name": "九州·永和元年",
    "cities": [
      {"name": "长安·西市酒肆", "x": 220, "y": 340, "r": 100},
      {"name": "大明宫·紫宸殿外", "x": 500, "y": 120, "r": 95},
      {"name": "终南山·古观", "x": 780, "y": 380, "r": 82},
    ],
    "street_plan": "imperial_grid",
    "road": "dirt",
    "signs": ["醉仙楼", "锦绣坊", "茶寮", "药铺", "书肆", "铁匠铺", "米行", "客栈"],
    "terrain": {"seed": 1201, "maxHeight": 28, "waterLevel": -0.34, "worldScale": 1.35},
    "sep_style": "ridges_paddies",
    "vegetation": "paddy_cypress",
  },
  "wuxia": {
    "name": "江湖·风波渡",
    "cities": [
      {"name": "风波渡·渡船头", "x": 160, "y": 300, "r": 92},
      {"name": "悦来客栈·二楼天字号", "x": 480, "y": 240, "r": 88},
      {"name": "藏剑山庄·剑冢", "x": 820, "y": 200, "r": 86},
    ],
    "street_plan": "valley_spine",
    "road": "dirt",
    "signs": ["刀客客栈", "医馆", "镖局", "当铺", "茶棚", "兵器铺"],
    "terrain": {"seed": 3347, "maxHeight": 32, "waterLevel": -0.26, "worldScale": 1.15},
    "sep_style": "gorge_woods",
    "vegetation": "dense_bamboo_reed",
  },
  "xuanhuan": {
    "name": "玄幻·九霄",
    "cities": [
      {"name": "万灵坊市", "x": 180, "y": 400, "r": 92},
      {"name": "青云宗·问道峰", "x": 480, "y": 210, "r": 98},
      {"name": "北域·裂空之地", "x": 820, "y": 100, "r": 80},
    ],
    "street_plan": "radial_ring",
    "road": "dirt",
    "signs": ["丹阁", "符箓斋", "仙茶", "法宝行", "阵法阁"],
    "terrain": {"seed": 5519, "maxHeight": 38, "waterLevel": -0.48, "worldScale": 1.55},
    "sep_style": "cloud_peaks",
    "vegetation": "spirit_purple_canopy",
  },
  "mystery": {
    "name": "雾港·1931",
    "cities": [
      {"name": "码头 7 号仓库", "x": 420, "y": 430, "r": 95},
      {"name": "雾港·第七巡捕房", "x": 170, "y": 200, "r": 88},
      {"name": "百乐门·二楼包厢", "x": 800, "y": 160, "r": 84},
    ],
    "street_plan": "harbor_alleys",
    "road": "paved",
    "signs": ["旧书店", "古董行", "照相馆", "酒吧", "旅舍"],
    "terrain": {"seed": 7723, "maxHeight": 18, "waterLevel": -0.12, "worldScale": 0.92},
    "sep_style": "fog_coast",
    "vegetation": "sparse_reed_fog",
  },
  "modern": {
    "name": "都会·当代",
    "cities": [
      {"name": "中央商务区·观景天台", "x": 500, "y": 250, "r": 105},
      {"name": "市府东翼·听证厅", "x": 180, "y": 150, "r": 90},
      {"name": "滨河老街·夜市", "x": 800, "y": 400, "r": 88},
    ],
    "street_plan": "metro_grid",
    "road": "paved",
    "signs": ["便利店", "咖啡厅", "药房", "银行", "超市", "餐厅"],
    "terrain": {"seed": 9188, "maxHeight": 16, "waterLevel": -0.38, "worldScale": 1.0},
    "sep_style": "park_belt",
    "vegetation": "street_park_belt",
  },
  "scifi": {
    "name": "环带·2387",
    "cities": [
      {"name": "环带中央站·零重力市场", "x": 480, "y": 260, "r": 110},
      {"name": "方舟船『俄耳甫斯号』·主控舱", "x": 170, "y": 400, "r": 90},
      {"name": "议会穹顶", "x": 820, "y": 120, "r": 92},
    ],
    "street_plan": "orbital",
    "road": "neon",
    "signs": ["合成食堂", "芯片站", "数据吧", "义体诊所", "霓虹馆"],
    "terrain": {"seed": 6401, "maxHeight": 24, "waterLevel": -0.55, "worldScale": 1.25},
    "sep_style": "crater_rings",
    "vegetation": "minimal_coolant",
  },
  "enterprise": {
    "name": "青梧·创业纪",
    "cities": [
      {"name": "青梧园区·A座开放办公区", "x": 240, "y": 280, "r": 100},
      {"name": "资本街·路演厅", "x": 560, "y": 180, "r": 92},
      {"name": "客户总部·会议室", "x": 780, "y": 360, "r": 86},
    ],
    "street_plan": "metro_grid",
    "road": "paved",
    "signs": ["咖啡角", "打印室", "路演厅", "HR", "产品墙"],
    "terrain": {"seed": 4021, "maxHeight": 14, "waterLevel": -0.4, "worldScale": 0.88},
    "sep_style": "campus_lawns",
    "vegetation": "campus_lawn_atrium",
  },
  "securities": {
    "name": "镜湖·交易日",
    "cities": [
      {"name": "镜湖交易所·交易大厅", "x": 480, "y": 220, "r": 108},
      {"name": "券商研究所·晨会室", "x": 200, "y": 360, "r": 88},
      {"name": "滨江咖啡·散户角", "x": 780, "y": 400, "r": 82},
    ],
    "street_plan": "metro_grid",
    "road": "paved",
    "signs": ["交易所", "券商", "ATM", "资讯屏", "咖啡"],
    "terrain": {"seed": 8833, "maxHeight": 12, "waterLevel": -0.08, "worldScale": 0.85},
    "sep_style": "lake_terrace",
    "vegetation": "formal_hedge",
  },
  "military": {
    "name": "边关·对峙",
    "cities": [
      {"name": "北岭前哨·观察所", "x": 200, "y": 140, "r": 86},
      {"name": "联合作战室·沙盘厅", "x": 500, "y": 280, "r": 95},
      {"name": "后勤枢纽·仓储站", "x": 800, "y": 400, "r": 100},
    ],
    "street_plan": "valley_spine",
    "road": "dirt",
    "signs": ["弹药库", "医务所", "电台", "食堂", "车库"],
    "terrain": {"seed": 2711, "maxHeight": 36, "waterLevel": -0.45, "worldScale": 1.45},
    "sep_style": "canyon_supply",
    "vegetation": "scrub_ridge_pine",
  },
}


def stable_hash(s: str) -> int:
  """Deterministic 32-bit hash (Python's hash() is randomized per process)."""
  h = 2166136261
  for ch in s:
    h ^= ord(ch)
    h = (h * 16777619) & 0xFFFFFFFF
  return h


def rng(seed: str) -> random.Random:
  return random.Random(stable_hash(seed))


def lerp(a, b, t):
  return a + (b - a) * t


def dist(a, b):
  return math.hypot(a[0] - b[0], a[1] - b[1])


def point_in_city(x, y, city) -> bool:
  return math.hypot(x - city["x"], y - city["y"]) <= city["r"] * 0.92


def road_seg(a: tuple[float, float], b: tuple[float, float], kind: str) -> dict:
  return {
    "from": [round(a[0], 1), round(a[1], 1)],
    "to": [round(b[0], 1), round(b[1], 1)],
    "kind": kind,
  }


def clip_in_city(x: float, y: float, city: dict, pad: float = 0.88) -> tuple[float, float]:
  """Pull a point back into the city disk if it drifted out."""
  cx, cy, rad = city["x"], city["y"], city["r"] * pad
  dx, dy = x - cx, y - cy
  d = math.hypot(dx, dy) or 1.0
  if d <= rad:
    return x, y
  return cx + dx / d * rad, cy + dy / d * rad


def planned_roads(city: dict, kind: str, plan: str, r: random.Random) -> list[dict]:
  """Genre-specific planned street networks — readable blocks, not spaghetti."""
  cx, cy, rad = city["x"], city["y"], city["r"]
  roads: list[dict] = []
  half = rad * 0.82

  def add(ax, ay, bx, by):
    a = clip_in_city(ax, ay, city)
    b = clip_in_city(bx, by, city)
    if dist(a, b) < 18:
      return
    roads.append(road_seg(a, b, kind))

  if plan == "imperial_grid":
    # 十字大街 + 坊里方格（街区够宽，沿街能落房）
    add(cx, cy - half, cx, cy + half)
    add(cx - half, cy, cx + half, cy)
    for i in (-2, -1, 1, 2):
      o = i * rad * 0.34
      add(cx + o, cy - half * 0.72, cx + o, cy + half * 0.72)
      add(cx - half * 0.72, cy + o, cx + half * 0.72, cy + o)

  elif plan == "valley_spine":
    # Main E–W spine + parallel lanes + short N–S cross streets
    yaw = r.uniform(-0.12, 0.12)
    ux, uy = math.cos(yaw), math.sin(yaw)
    vx, vy = -uy, ux
    add(cx - ux * half, cy - uy * half, cx + ux * half, cy + uy * half)
    for s in (-1, 1):
      ox, oy = vx * rad * 0.32 * s, vy * rad * 0.32 * s
      add(cx - ux * half * 0.85 + ox, cy - uy * half * 0.85 + oy,
          cx + ux * half * 0.85 + ox, cy + uy * half * 0.85 + oy)
    for t in (-0.55, -0.2, 0.2, 0.55):
      px, py = cx + ux * half * t, cy + uy * half * t
      add(px - vx * rad * 0.45, py - vy * rad * 0.45,
          px + vx * rad * 0.45, py + vy * rad * 0.45)

  elif plan == "radial_ring":
    # Plaza spokes + two concentric rings
    n_spoke = 6
    for i in range(n_spoke):
      ang = i * (math.pi * 2 / n_spoke) + 0.15
      add(cx, cy, cx + math.cos(ang) * half, cy + math.sin(ang) * half)
    for ring_t in (0.42, 0.72):
      rr = half * ring_t
      pts = []
      steps = 12
      for i in range(steps):
        ang = i * (math.pi * 2 / steps)
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
      for i in range(steps):
        add(*pts[i], *pts[(i + 1) % steps])

  elif plan == "harbor_alleys":
    # Waterfront boulevard (E–W) + pier alleys (N–S) + one inland parallel
    add(cx - half, cy + rad * 0.15, cx + half, cy + rad * 0.15)
    add(cx - half * 0.9, cy - rad * 0.25, cx + half * 0.9, cy - rad * 0.25)
    for i in range(-3, 4):
      x = cx + i * rad * 0.22
      add(x, cy + rad * 0.15, x, cy - rad * 0.55)
    # Quay spur east/west ends
    add(cx - half * 0.7, cy + rad * 0.15, cx - half * 0.7, cy + rad * 0.55)
    add(cx + half * 0.7, cy + rad * 0.15, cx + half * 0.7, cy + rad * 0.55)

  elif plan == "metro_grid":
    # Clean orthogonal CBD blocks — wider lots than spaghetti towns
    step = rad * 0.4
    xs = [cx + i * step for i in range(-2, 3)]
    ys = [cy + j * step for j in range(-2, 3)]
    for x in xs:
      add(x, ys[0], x, ys[-1])
    for y in ys:
      add(xs[0], y, xs[-1], y)

  elif plan == "orbital":
    # Concentric neon rings + 8 radials
    for ring_t in (0.35, 0.58, 0.82):
      rr = half * ring_t
      pts = []
      steps = 16
      for i in range(steps):
        ang = i * (math.pi * 2 / steps)
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
      for i in range(steps):
        add(*pts[i], *pts[(i + 1) % steps])
    for i in range(8):
      ang = i * (math.pi / 4) + 0.08
      add(cx + math.cos(ang) * half * 0.2, cy + math.sin(ang) * half * 0.2,
          cx + math.cos(ang) * half, cy + math.sin(ang) * half)

  else:
    # Fallback tidy cross
    add(cx, cy - half, cx, cy + half)
    add(cx - half, cy, cx + half, cy)

  return roads


def organic_roads(city, kind: str, r: random.Random) -> list[dict]:
  """Deprecated alias — kept so older call sites do not break mid-edit."""
  return planned_roads(city, kind, "metro_grid", r)


def dist_to_roads(px: float, py: float, roads: list[dict]) -> float:
  best = 1e9
  for road in roads:
    ax, ay = road["from"]
    bx, by = road["to"]
    l2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1.0
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2))
    qx, qy = ax + t * (bx - ax), ay + t * (by - ay)
    best = min(best, math.hypot(px - qx, py - qy))
  return best


# Driveable ribbon half-width in map px.
# SmoothRoad halfW ≈ 1.25–1.55 m → ≈ 3.3–4.1 map px @ SCALE 0.38; keep a safety margin.
ROAD_SURFACE = 5
WALK_LANE = 9
EFF_HALF = 8
# Absolute ban: no footprint corner may enter this band around ANY road centerline.
ASPHALT_BAN = ROAD_SURFACE + 4  # ≈ 3.4 m world — stalls/corners stay outside ribbon


def roadside_band(fw: float, fh: float) -> tuple[float, float]:
  """(min_clear, max_clear) from road centerline — curb strip for planned blocks."""
  half = max(EFF_HALF * 0.65, math.hypot(fw, fh) * 0.14)
  # Sit just past asphalt ban so dense metro/orbital blocks still get façades
  mn = ASPHALT_BAN + 2 + half * 0.45
  mx = mn + 14
  return mn, mx


def clears_all_roads(px: float, py: float, half: float, roads: list[dict], min_clear: float) -> bool:
  """Center in roadside band; footprint corners stay off the driveable ribbon."""
  if dist_to_roads(px, py, roads) < min_clear:
    return False
  # Ribbon-only ban (not full walk lane) so planned cross-streets still leave mid-block lots
  ribbon = ROAD_SURFACE + 1.5
  samples = (
    (px - half, py), (px + half, py),
    (px, py - half), (px, py + half),
    (px - half * 0.7, py - half * 0.7), (px + half * 0.7, py + half * 0.7),
    (px - half * 0.7, py + half * 0.7), (px + half * 0.7, py - half * 0.7),
  )
  for qx, qy in samples:
    if dist_to_roads(qx, qy, roads) < ribbon:
      return False
  return True


def curb_ok(sx: float, sy: float, roads: list[dict], stall_half: float = 3.5) -> bool:
  """Stall/vendor: sit in walk lane, corners never on driveable ribbon."""
  sd = dist_to_roads(sx, sy, roads)
  if not (ASPHALT_BAN + 1.0 <= sd <= ROAD_SURFACE + WALK_LANE + 4):
    return False
  ribbon = ROAD_SURFACE + 1.5
  for qx, qy in (
    (sx - stall_half, sy), (sx + stall_half, sy),
    (sx, sy - stall_half), (sx, sy + stall_half),
  ):
    if dist_to_roads(qx, qy, roads) < ribbon:
      return False
  return True


def pick_roadside_building(genre: str, classic: bool, r: random.Random) -> tuple[str, int, int, int]:
  """Story-matched type / footprint / floors per civilization."""
  typ_roll = r.random()
  if classic:
    if genre == "xuanhuan":
      if typ_roll < 0.14:
        return "temple", 36, 32, 2
      if typ_roll < 0.22:
        return "palace", 44, 38, 3
      if typ_roll < 0.5:
        return "commercial", 30 + r.randint(0, 8), 24 + r.randint(0, 6), 1 + r.randint(0, 1)
      return "residential", 22 + r.randint(0, 6), 18 + r.randint(0, 5), 1
    if genre == "wuxia":
      if typ_roll < 0.06:
        return "temple", 32, 28, 1
      if typ_roll < 0.1:
        return "palace", 40, 34, 2
      if typ_roll < 0.48:
        return "commercial", 26 + r.randint(0, 8), 20 + r.randint(0, 6), 1 + r.randint(0, 1)
      return "residential", 20 + r.randint(0, 6), 16 + r.randint(0, 5), 1
    # ancient — imperial low-rise
    if typ_roll < 0.08:
      return "temple", 34, 30, 1
    if typ_roll < 0.14:
      return "palace", 42, 36, 2
    if typ_roll < 0.42:
      return "commercial", 28 + r.randint(0, 8), 22 + r.randint(0, 6), 1 + r.randint(0, 1)
    return "residential", 22 + r.randint(0, 6), 18 + r.randint(0, 5), 1

  if genre == "scifi":
    if typ_roll < 0.22:
      return "tower", 26 + r.randint(0, 8), 24 + r.randint(0, 8), 10 + r.randint(0, 6)
    if typ_roll < 0.45:
      return "office", 28, 24, 6 + r.randint(0, 4)
    if typ_roll < 0.72:
      return "commercial", 26, 22, 3 + r.randint(0, 2)
    return "residential", 24, 20, 3 + r.randint(0, 2)
  if genre == "enterprise":
    # campus mid-rise — glass office blocks, few towers
    if typ_roll < 0.08:
      return "tower", 30, 28, 8 + r.randint(0, 3)
    if typ_roll < 0.42:
      return "office", 32, 26, 4 + r.randint(0, 3)
    if typ_roll < 0.72:
      return "commercial", 28, 22, 2 + r.randint(0, 2)
    return "residential", 26, 22, 3 + r.randint(0, 2)
  if genre == "securities":
    # financial district — towers + broker offices
    if typ_roll < 0.28:
      return "tower", 30, 28, 12 + r.randint(0, 6)
    if typ_roll < 0.55:
      return "office", 32, 26, 7 + r.randint(0, 4)
    if typ_roll < 0.78:
      return "commercial", 26, 22, 3 + r.randint(0, 2)
    return "residential", 24, 20, 4 + r.randint(0, 2)
  if genre == "military":
    # outpost — low barracks / warehouses / radio sheds
    if typ_roll < 0.06:
      return "tower", 24, 22, 3 + r.randint(0, 2)  # watchtower
    if typ_roll < 0.28:
      return "office", 30, 24, 2 + r.randint(0, 1)  # command / mess
    if typ_roll < 0.62:
      return "commercial", 32, 26, 1 + r.randint(0, 1)  # depot / garage
    return "residential", 26, 22, 1 + r.randint(0, 1)  # barracks
  if genre == "mystery":
    if typ_roll < 0.1:
      return "tower", 26, 24, 6 + r.randint(0, 4)
    if typ_roll < 0.3:
      return "office", 28, 24, 4 + r.randint(0, 2)
    if typ_roll < 0.62:
      return "commercial", 24, 20, 2 + r.randint(0, 2)
    return "residential", 22, 18, 2 + r.randint(0, 2)
  # modern metro CBD
  if typ_roll < 0.18:
    return "tower", 28, 26, 10 + r.randint(0, 6)
  if typ_roll < 0.4:
    return "office", 30, 24, 6 + r.randint(0, 3)
  if typ_roll < 0.7:
    return "commercial", 26, 22, 3 + r.randint(0, 2)
  return "residential", 24, 20, 3 + r.randint(0, 2)


NAME_POOLS: dict[str, dict[str, list[str]]] = {
  "ancient": {
    "temple": ["祠庙", "古观", "禅院"], "palace": ["府邸", "殿阙", "衙署"],
    "commercial": ["市肆", "商铺", "铺面"], "residential": ["民居", "宅院", "厢房"],
    "tower": ["望楼", "鼓楼"], "office": ["公署", "衙门"], "shop": ["小店", "门面"],
  },
  "wuxia": {
    "temple": ["剑庐", "山庙"], "palace": ["庄院", "门楼"],
    "commercial": ["客栈", "镖局", "当铺"], "residential": ["厢房", "茅舍", "别院"],
    "tower": ["望楼", "箭楼"], "office": ["账房", "总管院"], "shop": ["兵器铺", "药铺"],
  },
  "xuanhuan": {
    "temple": ["问道殿", "丹阁", "阵法阁"], "palace": ["宗门大殿", "仙府"],
    "commercial": ["坊市", "法宝行", "符箓斋"], "residential": ["洞府", "栖居", "灵舍"],
    "tower": ["灵塔", "镇妖塔"], "office": ["执事堂", "议事厅"], "shop": ["仙茶", "丹肆"],
  },
  "mystery": {
    "temple": ["教堂", "公馆"], "palace": ["巡捕房", "公馆"],
    "commercial": ["旧书店", "酒吧", "古董行"], "residential": ["公寓", "亭子间", "洋房"],
    "tower": ["钟楼", "报馆"], "office": ["事务所", "侦缉处"], "shop": ["照相馆", "旅舍"],
  },
  "modern": {
    "temple": ["文化中心"], "palace": ["市政厅", "听证厅"],
    "commercial": ["商铺", "便利店", "餐厅"], "residential": ["公寓", "小区楼"],
    "tower": ["写字楼", "塔楼"], "office": ["办公楼", "政务厅"], "shop": ["门店", "咖啡厅"],
  },
  "scifi": {
    "temple": ["穹顶馆"], "palace": ["议会穹顶", "方舟舱"],
    "commercial": ["合成食堂", "数据吧", "芯片站"], "residential": ["栖居舱", "环带公寓"],
    "tower": ["塔柱", "中枢塔"], "office": ["管理站", "航控台"], "shop": ["义体诊所", "霓虹馆"],
  },
  "enterprise": {
    "temple": ["展示厅"], "palace": ["路演厅", "客户中心"],
    "commercial": ["咖啡角", "打印室", "产品墙"], "residential": ["宿舍楼", "人才公寓"],
    "tower": ["园区塔楼", "A座"], "office": ["开放办公", "HR楼", "研发楼"], "shop": ["前台", "茶水间"],
  },
  "securities": {
    "temple": ["资讯厅"], "palace": ["交易大厅", "交易所"],
    "commercial": ["券商门店", "资讯屏", "ATM点"], "residential": ["员工公寓", "宿舍"],
    "tower": ["交易塔", "券商大厦"], "office": ["研究所", "风控中心", "清算所"], "shop": ["滨江咖啡", "简餐"],
  },
  "military": {
    "temple": ["纪念碑"], "palace": ["作战室", "指挥所"],
    "commercial": ["弹药库", "车库", "仓储站"], "residential": ["营房", "帐篷区", "哨舍"],
    "tower": ["观察塔", "雷达站"], "office": ["医务所", "电台", "参谋部"], "shop": ["军需处", "食堂"],
  },
}


def stall_chance(genre: str) -> float:
  return {
    "ancient": 0.72, "wuxia": 0.78, "xuanhuan": 0.55, "mystery": 0.45,
    "modern": 0.35, "scifi": 0.4, "enterprise": 0.25, "securities": 0.2, "military": 0.12,
  }.get(genre, 0.5)


def roadside_buildings(
  roads: list[dict], city: dict, genre: str, signs: list[str], r: random.Random, classic: bool,
) -> list[dict]:
  """Place buildings ONLY in the roadside band; never on driveable surface."""
  buildings = []
  occupied: list[tuple[float, float, float]] = []
  idx = 0
  pools = NAME_POOLS.get(genre, NAME_POOLS["modern"])
  stall_p = stall_chance(genre)

  for ri, road in enumerate(roads):
    ax, ay = road["from"]
    bx, by = road["to"]
    length = dist((ax, ay), (bx, by)) or 1
    dx, dy = (bx - ax) / length, (by - ay) / length
    nx, ny = -dy, dx

    t = 0.06
    while t < 0.94:
      step = 0.09
      cx = lerp(ax, bx, t)
      cy = lerp(ay, by, t)
      if not point_in_city(cx, cy, city):
        t += step
        continue

      for side in (-1, 1):
        typ, fw, fh, floors = pick_roadside_building(genre, classic, r)

        mn, mx = roadside_band(fw, fh)
        setback = (mn + mx) * 0.5 + r.uniform(-3, 4)
        along = r.uniform(-4, 4)
        px = cx + nx * setback * side + dx * along
        py = cy + ny * setback * side + dy * along

        if not (40 < px < W - 40 and 40 < py < H - 40):
          continue
        if not point_in_city(px, py, city):
          continue

        d0 = dist_to_roads(px, py, roads)
        if d0 < mn or d0 > mx:
          setback = (mn + mx) * 0.5 + 2
          px = cx + nx * setback * side + dx * along
          py = cy + ny * setback * side + dy * along
          d0 = dist_to_roads(px, py, roads)
          if d0 < mn or d0 > mx:
            continue

        half = max(EFF_HALF * 0.55, math.hypot(fw, fh) * 0.16)
        if not clears_all_roads(px, py, half, roads, mn):
          continue

        rad = max(fw, fh) * 0.42
        if any(math.hypot(px - ox, py - oy) < (rad + orad) * 1.05 for ox, oy, orad in occupied):
          continue

        rot = math.atan2(dx, dy)
        if side > 0:
          rot += math.pi

        name_pool = pools.get(typ, ["建筑"])
        stall_label = {"military": "补给点", "enterprise": "外侧摊", "securities": "资讯亭", "scifi": "贩售单元"}.get(genre, "摊")
        b = {
          "name": f"{city['name']}·{name_pool[idx % len(name_pool)]}·{idx + 1}",
          "x": round(px, 1),
          "y": round(py, 1),
          "w": fw,
          "h": fh,
          "floors": floors,
          "type": typ,
          "enterable": False,
          "rot": round(rot, 3),
          "city": city["name"],
        }
        if typ in ("commercial", "shop", "office"):
          b["sign"] = signs[idx % len(signs)]
          b["banner"] = classic
        buildings.append(b)
        occupied.append((px, py, rad))
        idx += 1

        if typ in ("commercial", "shop", "residential", "office") and r.random() < stall_p:
          curb = ASPHALT_BAN + 3 + r.uniform(0, 2.5)
          sx = cx + nx * curb * side + dx * r.uniform(-3, 3)
          sy = cy + ny * curb * side + dy * r.uniform(-3, 3)
          if curb_ok(sx, sy, roads) and point_in_city(sx, sy, city):
            if not any(math.hypot(sx - ox, sy - oy) < 12 for ox, oy, orad in occupied):
              stall_signs = signs if signs else [stall_label]
              buildings.append({
                "name": f"{city['name']}·{stall_label}·{idx}",
                "x": round(sx, 1), "y": round(sy, 1),
                "w": 14, "h": 10, "floors": 1, "type": "stall",
                "enterable": False, "rot": round(rot, 3),
                "city": city["name"],
                "sign": stall_signs[idx % len(stall_signs)],
              })
              occupied.append((sx, sy, 7))
              idx += 1

      t += step

  return buildings



def separators(cities: list[dict], genre: str, style: str, r: random.Random) -> dict:
  """Mountains / forests / lakes / fields BETWEEN cities — style varies by genre."""
  trees = []
  water = []
  fields = []
  mountains = []

  for i, a in enumerate(cities):
    for b in cities[i + 1:]:
      mx = (a["x"] + b["x"]) / 2
      my = (a["y"] + b["y"]) / 2
      dx, dy = b["x"] - a["x"], b["y"] - a["y"]
      # Offset perpendicular to the city pair so ridges don't all sit on the same midline
      nx, ny = -dy, dx
      nlen = math.hypot(nx, ny) or 1.0
      nx, ny = nx / nlen, ny / nlen
      off = r.uniform(-35, 35)

      peak_r = {
        "ridges_paddies": 130, "gorge_woods": 150, "cloud_peaks": 170,
        "fog_coast": 100, "park_belt": 110, "crater_rings": 140,
        "campus_lawns": 70, "lake_terrace": 85, "canyon_supply": 180,
      }.get(style, 120)

      mountains.append({
        "name": f"界山·{a['name'][:2]}",
        "x": round(mx + nx * off + r.uniform(-12, 12), 1),
        "y": round(my + ny * off + r.uniform(-10, 10), 1),
        "r": int(peak_r + r.uniform(0, 40)),
        "color": [120, 110, 95],
        "terrain": "peak",
      })

      # Extra peak for cloud_peaks / gorge
      if style in ("cloud_peaks", "gorge_woods") and r.random() < 0.7:
        mountains.append({
          "name": f"峰·{b['name'][:2]}",
          "x": round(mx - nx * off * 0.6 + r.uniform(-25, 25), 1),
          "y": round(my - ny * off * 0.6 + r.uniform(-20, 20), 1),
          "r": int(peak_r * 0.75 + r.uniform(0, 30)),
          "color": [100, 95, 110],
          "terrain": "peak",
        })

      tree_n = {
        "ridges_paddies": 16, "gorge_woods": 28, "cloud_peaks": 14,
        "fog_coast": 10, "park_belt": 12, "crater_rings": 8,
        "campus_lawns": 22, "lake_terrace": 14, "canyon_supply": 9,
      }.get(style, 16)
      for _ in range(tree_n + r.randint(0, 8)):
        ang = r.uniform(0, math.pi * 2)
        rad = r.uniform(12, 60)
        tx = mx + math.cos(ang) * rad + r.uniform(-12, 12)
        ty = my + math.sin(ang) * rad * 0.75 + r.uniform(-10, 10)
        if 20 < tx < W - 20 and 20 < ty < H - 20:
          if all(math.hypot(tx - c["x"], ty - c["y"]) > c["r"] * 0.78 for c in cities):
            trees.append({"x": round(tx, 1), "y": round(ty, 1), "climbable": False})

      water_chance = {
        "ridges_paddies": 0.55, "gorge_woods": 0.7, "cloud_peaks": 0.4,
        "fog_coast": 0.95, "park_belt": 0.5, "crater_rings": 0.65,
        "campus_lawns": 0.35, "lake_terrace": 0.98, "canyon_supply": 0.25,
      }.get(style, 0.7)
      if r.random() < water_chance:
        water.append({
          "x": round(mx + r.uniform(-50, 50), 1),
          "y": round(my + r.uniform(-40, 40), 1),
          "rx": int((72 if style == "fog_coast" else 52) + r.uniform(0, 36)),
          "ry": int((38 if style == "fog_coast" else 30) + r.uniform(0, 20)),
          "depth": 2.1 if style == "fog_coast" else 1.5,
          "diveable": False,
          "name": "界湖" if genre in ("ancient", "wuxia", "xuanhuan") else ("港湾" if style == "fog_coast" else "外湖"),
        })

      field_n = 4 if style in ("ridges_paddies", "park_belt", "campus_lawns") else (
        5 if style == "lake_terrace" else (1 if style == "canyon_supply" else 2)
      )
      for _ in range(field_n):
        fields.append({
          "x": round(mx + r.uniform(-80, 80), 1),
          "y": round(my + r.uniform(-55, 55), 1),
          "w": int(45 + r.uniform(0, 45)),
          "h": int(28 + r.uniform(0, 28)),
          "kind": "paddy" if style in ("ridges_paddies", "gorge_woods") else (
            "plaza" if style in ("crater_rings", "lake_terrace") else (
              "drill" if style == "canyon_supply" else "park"
            )
          ),
        })

  # Genre-specific accents
  if style == "fog_coast":
    water.append({
      "x": W * 0.45, "y": H * 0.92, "rx": 220, "ry": 55,
      "depth": 2.4, "diveable": False, "name": "外海",
    })
  if style == "crater_rings":
    mountains.append({
      "name": "陨坑缘", "x": W * 0.5, "y": H * 0.55, "r": 90,
      "color": [90, 100, 120], "terrain": "peak",
    })
  if style == "cloud_peaks":
    mountains.append({
      "name": "天柱", "x": W * 0.72, "y": H * 0.22, "r": 160,
      "color": [130, 120, 140], "terrain": "peak",
    })
  if style == "campus_lawns":
    fields.append({"x": W * 0.48, "y": H * 0.42, "w": 120, "h": 70, "kind": "park"})
    water.append({
      "x": W * 0.55, "y": H * 0.55, "rx": 40, "ry": 22,
      "depth": 1.0, "diveable": False, "name": "园区镜池",
    })
  if style == "lake_terrace":
    water.append({
      "x": W * 0.5, "y": H * 0.62, "rx": 200, "ry": 70,
      "depth": 2.2, "diveable": False, "name": "镜湖",
    })
  if style == "canyon_supply":
    mountains.append({
      "name": "北岭主峰", "x": W * 0.35, "y": H * 0.2, "r": 200,
      "color": [110, 105, 90], "terrain": "peak",
    })
    mountains.append({
      "name": "南堑", "x": W * 0.7, "y": H * 0.55, "r": 160,
      "color": [100, 95, 85], "terrain": "peak",
    })
    fields.append({"x": W * 0.65, "y": H * 0.72, "w": 140, "h": 50, "kind": "drill"})

  for c in cities:
    for _ in range(10 if style != "crater_rings" else 6):
      ang = r.uniform(0, math.pi * 2)
      rad = c["r"] * r.uniform(1.08, 1.4)
      tx = c["x"] + math.cos(ang) * rad
      ty = c["y"] + math.sin(ang) * rad
      if 20 < tx < W - 20 and 20 < ty < H - 20:
        trees.append({"x": round(tx, 1), "y": round(ty, 1), "climbable": r.random() < 0.08})

  return {"trees": trees, "water": water, "fields": fields, "mountains": mountains}


def genre_rivers(cities: list[dict], genre: str, style: str) -> list[dict]:
  """Main river polylines — one signature watercourse per genre."""
  if genre == "ancient":
    return [{"name": "渭水", "points": [[60, 420], [480, 395], [900, 415]], "width": 30}]
  if genre == "wuxia":
    c0, c2 = cities[0], cities[-1]
    return [{
      "name": "怒江",
      "points": [[90, c0["y"] + 40], [480, 255], [870, c2["y"] + 30]],
      "width": 28,
    }]
  if genre == "xuanhuan":
    return [{
      "name": "灵溪",
      "points": [[820, 420], [620, 320], [420, 240], [220, 180]],
      "width": 22,
    }]
  if genre == "mystery":
    return [{
      "name": "雾河",
      "points": [[120, 460], [420, 430], [720, 400], [880, 370]],
      "width": 26,
    }]
  if genre == "modern":
    return [{
      "name": "护城河",
      "points": [[180, 380], [480, 350], [780, 320]],
      "width": 24,
    }]
  if genre == "scifi":
    return [{
      "name": "冷却渠",
      "points": [[100, 300], [480, 280], [860, 310]],
      "width": 20,
    }]
  if genre == "enterprise":
    return [{
      "name": "园区景观渠",
      "points": [[140, 360], [400, 320], [700, 300], [880, 340]],
      "width": 14,
    }]
  if genre == "securities":
    return [{
      "name": "镜湖水道",
      "points": [[80, 480], [320, 440], [560, 400], [860, 380]],
      "width": 36,
    }]
  if genre == "military":
    return [{
      "name": "补给干谷",
      "points": [[120, 200], [360, 280], [620, 340], [900, 420]],
      "width": 18,
    }]
  return []


def genre_bridges(rivers: list[dict], cities: list[dict]) -> list[dict]:
  """Bridges at river mid-segments and near city crossings."""
  bridges: list[dict] = []
  for river in rivers:
    pts = river["points"]
    width = int(river.get("width") or 22)
    for i in range(len(pts) - 1):
      ax, ay = pts[i]
      bx, by = pts[i + 1]
      for t in (0.35, 0.65):
        mx = ax + (bx - ax) * t
        my = ay + (by - ay) * t
        angle = math.atan2(bx - ax, by - ay)
        bridges.append({
          "x": round(mx, 1),
          "y": round(my, 1),
          "angle": round(angle, 3),
          "length": width + 28,
          "name": f"{river.get('name', '河')}桥",
        })
    for city in cities[:2]:
      best_t = 0.5
      best_d = 1e9
      for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        d = math.hypot(mx - city["x"], my - city["y"])
        if d < best_d:
          best_d = d
          best_t = i
      if best_d < city["r"] * 2.2:
        ax, ay = pts[best_t]
        bx, by = pts[best_t + 1]
        mx = (ax + bx) / 2
        my = (ay + by) / 2
        bridges.append({
          "x": round(mx, 1),
          "y": round(my, 1),
          "angle": round(math.atan2(bx - ax, by - ay), 3),
          "length": width + 32,
          "name": f"{city['name'][:2]}渡桥",
        })
  # De-dupe nearby bridges
  out: list[dict] = []
  for b in bridges:
    if any(math.hypot(b["x"] - o["x"], b["y"] - o["y"]) < 45 for o in out):
      continue
    out.append(b)
  return out[:6]


def shore_vegetation(
  water: list[dict], rivers: list[dict], r: random.Random,
) -> list[dict]:
  """Reeds/grass along river banks and lake shores."""
  spots: list[dict] = []
  for river in rivers:
    pts = river["points"]
    half = (river.get("width") or 20) * 0.55
    for i in range(len(pts) - 1):
      ax, ay = pts[i]
      bx, by = pts[i + 1]
      dx, dy = bx - ax, by - ay
      length = math.hypot(dx, dy) or 1.0
      nx, ny = -dy / length, dx / length
      steps = max(4, int(length / 35))
      for j in range(steps + 1):
        t = j / max(1, steps)
        px = ax + dx * t
        py = ay + dy * t
        for side in (-1, 1):
          if r.random() > 0.35:
            continue
          sx = px + nx * (half + r.uniform(3, 12)) * side
          sy = py + ny * (half + r.uniform(3, 12)) * side
          if 15 < sx < W - 15 and 15 < sy < H - 15:
            spots.append({
              "x": round(sx, 1),
              "y": round(sy, 1),
              "kind": "reed" if r.random() < 0.55 else "grass",
            })
  for lake in water:
    rx = lake.get("rx") or 40
    ry = lake.get("ry") or 24
    for ang in range(0, 360, 10):
      rad = math.radians(ang)
      sx = lake["x"] + math.cos(rad) * rx * r.uniform(0.88, 1.05)
      sy = lake["y"] + math.sin(rad) * ry * r.uniform(0.88, 1.05)
      if r.random() < 0.55:
        spots.append({"x": round(sx, 1), "y": round(sy, 1), "kind": "grass"})
  return spots


def landmark_for_city(city, genre, r: random.Random) -> dict:
  classic = genre in ("ancient", "wuxia", "xuanhuan")
  if classic:
    typ = r.choice(["palace", "temple", "commercial"])
    fw, fh = (48, 40) if typ == "palace" else ((40, 34) if typ == "temple" else (32, 26))
    floors = 3 if genre == "xuanhuan" else 2
  elif genre == "scifi":
    typ = r.choice(["tower", "palace", "ship_port"])
    fw, fh = (36, 36) if typ == "tower" else (44, 32)
    floors = 14
  elif genre == "enterprise":
    typ = r.choice(["palace", "office", "tower"])  # pitch hall / HQ
    fw, fh = (40, 34) if typ == "palace" else (34, 30)
    floors = 8 if typ == "tower" else 5
  elif genre == "securities":
    typ = r.choice(["palace", "tower", "office"])  # exchange atrium
    fw, fh = (42, 36) if typ == "palace" else (36, 34)
    floors = 16 if typ == "tower" else 10
  elif genre == "military":
    typ = r.choice(["palace", "office", "commercial"])  # ops / depot
    fw, fh = (38, 32) if typ == "palace" else (34, 28)
    floors = 3 if typ == "palace" else 2
  elif genre == "mystery":
    typ = r.choice(["palace", "office", "commercial"])
    fw, fh = (36, 30) if typ == "palace" else (30, 26)
    floors = 6
  else:
    typ = r.choice(["tower", "palace", "office"])
    fw, fh = (34, 32) if typ != "palace" else (40, 34)
    floors = 12
  return {
    "name": city["name"],
    "x": city["x"],
    "y": city["y"],
    "w": fw,
    "h": fh,
    "floors": floors,
    "type": typ if typ != "ship_port" else "ship_port",
    "enterable": True,
    "rot": r.uniform(-0.4, 0.4),
    "city": city["name"],
    "sign": city["name"],
  }


def build_genre(genre: str) -> dict:
  meta = GENRE_META[genre]
  r = rng(f"layout-{genre}-v12-water")
  classic = genre in ("ancient", "wuxia", "xuanhuan")
  cities = meta["cities"]
  plan = meta["street_plan"]

  all_roads = []
  all_buildings = []
  locations = []
  landmarks: list[dict] = []
  camera_anchors: list[dict] = []

  for city in cities:
    roads = planned_roads(city, meta["road"], plan, r)
    all_roads.extend(roads)
    blds = roadside_buildings(roads, city, genre, meta["signs"], r, classic)
    # Landmark plaza: roadside band only — never on driveable surface
    lm = landmark_for_city(city, genre, r)
    occupied = [(b["x"], b["y"], max(b["w"], b["h"]) * 0.55) for b in blds]
    if roads:
      hub = roads[0]
      ax, ay = hub["from"]
      bx, by = hub["to"]
      length = dist((ax, ay), (bx, by)) or 1
      dx, dy = (bx - ax) / length, (by - ay) / length
      nx, ny = -dy, dx
      mn, mx = roadside_band(lm["w"], lm["h"])
      placed = False
      for attempt in range(12):
        t = 0.32 + attempt * 0.05
        setback = (mn + mx) * 0.5 + attempt * 1.5
        side = 1 if attempt % 2 == 0 else -1
        cx, cy = lerp(ax, bx, min(0.85, t)), lerp(ay, by, min(0.85, t))
        px = cx + nx * setback * side
        py = cy + ny * setback * side
        if not (50 < px < W - 50 and 50 < py < H - 50):
          continue
        if not point_in_city(px, py, city):
          continue
        d0 = dist_to_roads(px, py, roads)
        if d0 < mn or d0 > mx + 8:
          continue
        half = max(EFF_HALF, math.hypot(lm["w"], lm["h"]) * 0.22)
        if not clears_all_roads(px, py, half, roads, mn):
          continue
        rad = max(lm["w"], lm["h"]) * 0.55
        if any(math.hypot(px - ox, py - oy) < (rad + orad) * 1.15 for ox, oy, orad in occupied):
          continue
        lm["x"] = round(px, 1)
        lm["y"] = round(py, 1)
        lm["rot"] = round(math.atan2(dx, dy) + (math.pi if side > 0 else 0), 3)
        placed = True
        break
      if not placed:
        mn2, mx2 = roadside_band(lm["w"], lm["h"])
        for road in sorted(roads, key=lambda rd: -dist(rd["from"], rd["to"])):
          ax, ay = road["from"]; bx, by = road["to"]
          length = dist((ax, ay), (bx, by)) or 1
          dx, dy = (bx - ax) / length, (by - ay) / length
          nx, ny = -dy, dx
          cx, cy = lerp(ax, bx, 0.5), lerp(ay, by, 0.5)
          for side in (-1, 1):
            px = cx + nx * ((mn2 + mx2) * 0.5) * side
            py = cy + ny * ((mn2 + mx2) * 0.5) * side
            if not point_in_city(px, py, city):
              continue
            half = max(EFF_HALF, math.hypot(lm["w"], lm["h"]) * 0.22)
            if not clears_all_roads(px, py, half, roads, mn2):
              continue
            lm["x"] = round(px, 1); lm["y"] = round(py, 1)
            lm["rot"] = round(math.atan2(dx, dy) + (math.pi if side > 0 else 0), 3)
            placed = True
            break
          if placed:
            break
        if not placed:
          lm = None
    if lm:
      lm["landmark"] = "primary"
      # Keep story-matched landmark floors from landmark_for_city (only bump slightly)
      lm["floors"] = max(lm.get("floors", 2), 2 if classic else (3 if genre == "military" else 6))
      all_buildings.append(lm)
      landmarks.append({
        "id": f"lm_{city['name']}",
        "name": city["name"],
        "tier": "primary",
        "x": lm["x"],
        "y": lm["y"],
        "building_type": lm.get("type", "palace"),
        "city": city["name"],
      })
    else:
      # Fallback hero landmark at city plaza when roadside placement fails
      fb = landmark_for_city(city, genre, r)
      fb["x"] = city["x"]
      fb["y"] = city["y"] - city["r"] * 0.15
      fb["landmark"] = "primary"
      fb["floors"] = max(fb.get("floors", 2), 2 if classic else (3 if genre == "military" else 6))
      all_buildings.append(fb)
      landmarks.append({
        "id": f"lm_{city['name']}",
        "name": city["name"],
        "tier": "primary",
        "x": fb["x"],
        "y": fb["y"],
        "building_type": fb.get("type", "palace"),
        "city": city["name"],
      })
    all_buildings.extend(blds)
    # Secondary landmarks — tallest commercial/temple along main roads
    sec_pool = [b for b in blds if b.get("type") in ("commercial", "temple", "tower", "office")]
    sec_pool.sort(key=lambda b: b.get("w", 0) * b.get("h", 0), reverse=True)
    for sb in sec_pool[:2]:
      sb["landmark"] = "secondary"
      landmarks.append({
        "id": f"lm_{city['name']}_{sb.get('sign', sb['name'])}",
        "name": sb.get("sign") or sb["name"],
        "tier": "secondary",
        "x": sb["x"],
        "y": sb["y"],
        "building_type": sb.get("type", "commercial"),
        "city": city["name"],
      })

    # Guarantee curb stalls per city (vendors on walk lane, never on asphalt)
    occupied_xy = [(b["x"], b["y"]) for b in all_buildings if b.get("city") == city["name"]]
    stall_n = sum(1 for b in all_buildings if b.get("city") == city["name"] and b.get("type") == "stall")
    stall_cap = {
      "ancient": 5, "wuxia": 6, "xuanhuan": 4, "mystery": 3,
      "modern": 3, "scifi": 3, "enterprise": 2, "securities": 2, "military": 1,
    }.get(genre, 4)
    stall_label = {"military": "补给点", "enterprise": "外侧摊", "securities": "资讯亭", "scifi": "贩售单元"}.get(genre, "摊")
    for road in roads:
      if stall_n >= stall_cap:
        break
      ax, ay = road["from"]
      bx, by = road["to"]
      length = dist((ax, ay), (bx, by)) or 1
      dx, dy = (bx - ax) / length, (by - ay) / length
      nx, ny = -dy, dx
      for t in (0.28, 0.5, 0.72):
        if stall_n >= stall_cap:
          break
        cx, cy = lerp(ax, bx, t), lerp(ay, by, t)
        if not point_in_city(cx, cy, city):
          continue
        side = 1 if stall_n % 2 == 0 else -1
        curb = ASPHALT_BAN + 3.5
        sx = cx + nx * curb * side
        sy = cy + ny * curb * side
        if not (40 < sx < W - 40 and 40 < sy < H - 40):
          continue
        if any(math.hypot(sx - ox, sy - oy) < 14 for ox, oy in occupied_xy):
          continue
        if not curb_ok(sx, sy, roads):
          continue
        rot = math.atan2(dx, dy) + (math.pi if side > 0 else 0)
        all_buildings.append({
          "name": f"{city['name']}·{stall_label}·g{stall_n}",
          "x": round(sx, 1), "y": round(sy, 1),
          "w": 14, "h": 10, "floors": 1, "type": "stall",
          "enterable": False, "rot": round(rot, 3),
          "city": city["name"],
          "sign": meta["signs"][stall_n % len(meta["signs"])],
        })
        occupied_xy.append((sx, sy))
        stall_n += 1

    locations.append({
      "name": city["name"],
      "x": city["x"],
      "y": city["y"],
      "building": True,
      "enterable": True,
    })

  sep = separators(cities, genre, meta.get("sep_style", "ridges_paddies"), r)

  # Ensure at least one lake separator
  if not sep["water"] and len(cities) >= 2:
    a, b = cities[0], cities[1]
    sep["water"].append({
      "x": round((a["x"] + b["x"]) / 2, 1),
      "y": round((a["y"] + b["y"]) / 2 + 30, 1),
      "rx": 55,
      "ry": 28,
      "depth": 1.6,
      "diveable": False,
      "name": "外湖",
    })

  # Dock near water for coastal cities (first city often)
  if sep["water"]:
    w0 = sep["water"][0]
    nearest = min(cities, key=lambda c: dist((c["x"], c["y"]), (w0["x"], w0["y"])))
    ang = math.atan2(w0["y"] - nearest["y"], w0["x"] - nearest["x"])
    dx = w0["x"] - math.cos(ang) * (w0["rx"] * 0.7)
    dy = w0["y"] - math.sin(ang) * (w0["ry"] * 0.7)
    all_buildings.append({
      "name": f"{nearest['name']}·渡口",
      "x": round(dx, 1),
      "y": round(dy, 1),
      "w": 40,
      "h": 16,
      "floors": 1,
      "type": "dock",
      "enterable": False,
      "rot": ang,
      "city": nearest["name"],
    })

  # Walls only for classic primary cities
  walls = []
  if classic:
    for city in cities[:2]:
      walls.append({
        "name": f"{city['name']}·城垣",
        "x": city["x"],
        "y": city["y"],
        "rx": int(city["r"] * 0.75),
        "ry": int(city["r"] * 0.58),
        "hasMoat": True,
      })

  # Factions: cities + mountain separators
  factions = []
  colors = [
    [210, 110, 110], [110, 170, 210], [200, 180, 100],
    [140, 160, 120], [160, 120, 180],
  ]
  for i, city in enumerate(cities):
    factions.append({
      "name": city["name"],
      "x": city["x"],
      "y": city["y"],
      "r": city["r"],
      "color": colors[i % len(colors)],
      "terrain": "valley",
    })
  factions.extend(sep["mountains"])

  # Animals sparse
  animals = []
  for city in cities[:2]:
    animals.append({
      "name": "游犬",
      "x": city["x"] + 20,
      "y": city["y"] + 10,
      "species": "dog",
      "behavior": "walk",
    })

  terrain = dict(meta["terrain"])
  rivers = genre_rivers(cities, genre, meta["sep_style"])
  bridges = genre_bridges(rivers, cities)
  shore_grass = shore_vegetation(sep["water"], rivers, r)

  # Camera anchors — spawn / hero framing per city (v1.4 §10 layer 7)
  for i, city in enumerate(cities):
    primary = next(
      (lm for lm in landmarks if lm.get("city") == city["name"] and lm.get("tier") == "primary"),
      None,
    )
    if primary:
      camera_anchors.append({
        "id": f"spawn_{city['name']}",
        "x": primary["x"],
        "y": primary["y"],
        "yaw": 0.0,
        "pitch": -0.32,
        "distance": 52 if classic else 44,
        "role": "spawn" if i == 0 else "scene",
        "look_at": {"x": city["x"], "y": city["y"]},
      })

  return {
    "width": W,
    "height": H,
    "name": meta["name"],
    "genre": genre,
    "locations": locations,
    "factions": factions,
    "terrain": terrain,
    "water": sep["water"],
    "rivers": rivers,
    "bridges": bridges,
    "shore_grass": shore_grass,
    "trees": sep["trees"],
    "fields": sep["fields"],
    "buildings": all_buildings,
    "animals": animals,
    "roads": all_roads,
    "walls": walls,
    "cities": [{"name": c["name"], "x": c["x"], "y": c["y"], "r": c["r"]} for c in cities],
    "landmarks": landmarks,
    "camera_anchors": camera_anchors,
    "streetPlan": plan,
  }


def main():
  OUT.mkdir(parents=True, exist_ok=True)
  for genre in GENRE_META:
    data = build_genre(genre)
    path = OUT / f"{genre}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(
      genre,
      "cities", len(data["cities"]),
      "buildings", len(data["buildings"]),
      "roads", len(data["roads"]),
      "trees", len(data["trees"]),
      "water", len(data["water"]),
      "rivers", len(data.get("rivers") or []),
      "bridges", len(data.get("bridges") or []),
      "shore", len(data.get("shore_grass") or []),
      "fields", len(data.get("fields") or []),
    )


if __name__ == "__main__":
  main()

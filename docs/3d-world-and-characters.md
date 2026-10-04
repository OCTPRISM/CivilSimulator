# 3D 世界与人物模型 — 技术规格

> **文档版本**：2026-08-30  
> **适用范围**：CivilSimulator 中所有 Three.js / R3F 3D 渲染  
> **读者**：3D 前端、美术管线、玩法开发  
> **关联文档**：[Play 会话 UI](./play-session-ui-api.md)、[文档索引](./README.md)

---

## 目录

1. [总览与使用场景](#1-总览与使用场景)
2. [Genre 与 Seed 映射](#2-genre-与-seed-映射)
3. [静态资产 URL 规范](#3-静态资产-url-规范)
4. [3D 地图 JSON 格式](#4-3d-地图-json-格式)
5. [World3D 渲染管线](#5-world3d-渲染管线)
6. [建筑 GLB 模型](#6-建筑-glb-模型)
7. [人物 GLTF 与 PBR 皮肤](#7-人物-gltf-与-pbr-皮肤)
8. [角色创建流程](#8-角色创建流程)
9. [开发预览页](#9-开发预览页)
10. [与实验平台的关系](#10-与实验平台的关系)
11. [资产生成脚本](#11-资产生成脚本)
12. [已知限制与缺口](#12-已知限制与缺口)
13. [源码索引](#13-源码索引)

---

## 1. 总览与使用场景

### 1.1 哪些页面使用 3D

| 页面 | 路由 | 3D 组件 | 说明 |
|------|------|---------|------|
| 叙事游戏 | `/play/[sid]` | `World3D` | 完整世界：地形、建筑、玩家/NPC 角色 |
| 角色创建 | `/create/[seedKey]` | `CharacterFigurePreview` | 仅人物预览（无地图） |
| 地图开发 | `/dev/maps` | `World3D` | 无 agent，可调 genre/hour |
| 人物开发 | `/dev/figures` | `CharacterFigurePreview` | 浏览 preset + 换肤 |
| 实验平台 | `/labs/*` | **无** | 纯 2D 面板 + CivilizationDashboard |
| 首页 | `/` | **无** | 仅用 `/maps/{seedKey}.png` 作卡片缩略图 |

### 1.2 组件依赖关系

```
World3D.tsx
├── Architecture.tsx      — 道路 SmoothRoad
├── KitBuildingMesh.tsx   — GLB 建筑加载
├── HumanoidFigure.tsx    — 角色入口
│   ├── GltfHumanoid.tsx  — GLTF + PBR 皮肤
│   └── ProceduralHumanoid — Suspense 降级（胶囊体 + canvas PBR）
└── figureMaterials.tsx   — 程序化材质（降级路径）

CharacterFigurePreview.tsx — 独立 R3F Canvas，用于创建页 / dev/figures
```

---

## 2. Genre 与 Seed 映射

### 2.1 两个不同的 key

| 概念 | 字段 | 用途 |
|------|------|------|
| **文明 seed** | `seed_key` / `session.seed_key` | 叙事内容、金融 seed、玩家目录 |
| **视觉 genre** | `world.genre` / `session.world.genre` | **3D 地图、建筑 kit、人物 preset 池** |

### 2.2 加载规则（无歧义）

| 资产 | URL 使用的 key | 示例 |
|------|---------------|------|
| 3D 布局 JSON | **genre** | `/maps/wuxia.json` |
| 2D Atlas PNG（首页/创建页缩略图） | **seed_key** | `/maps/wuxia.png` |
| 建筑 GLB kit | **genre** | `/models/buildings/wuxia/palace.glb` |
| 人物 preset 池 | **genre** | `presetsForGenre("wuxia")` |

**代码位置**（地图加载）：

```typescript
// World3D.tsx — genre 变化时 fetch
fetch(`/maps/${genre}.json`)
```

### 2.3 完整对照表

| seed_key | genre | 3D JSON | 2D PNG | 建筑 kit | Figure preset |
|----------|-------|---------|--------|----------|---------------|
| ancient | ancient | ✅ | ✅ | ✅ | ✅ |
| wuxia | wuxia | ✅ | ✅ | ✅ | ✅ |
| xuanhuan | xuanhuan | ✅ | ✅ | ✅ | ✅ |
| mystery | mystery | ✅ | ✅ | ✅ | ✅ |
| modern | modern | ✅ | ✅ | ✅ | ⚠️ 无专属条目 |
| scifi | scifi | ✅ | ✅ | ✅ | ✅ |
| military | military | ❌ 404 | ❌ | ❌ | ❌ |
| enterprise | enterprise | ❌ | ❌ | ❌ | ❌ |
| securities | securities | ❌ | ❌ | ❌ | ❌ |

**后果**：`military` / `enterprise` / `securities` 进入 Play 页时，World3D 会一直显示「正在生成 3D 地形…」（fetch 404）。

同 genre 的不同 seed（若将来存在）将共享**完全相同**的 3D 地理布局；叙事 `world.locations` 通过 **地点名称** 与 map 中 `locations[].name` 匹配坐标。

---

## 3. 静态资产 URL 规范

所有路径相对于 `frontend/public/`，浏览器直接访问。

### 3.1 地图

| 类型 | URL | 文件位置 |
|------|-----|---------|
| 3D 布局 | `/maps/{genre}.json` | `public/maps/ancient.json` 等 6 个 |
| 2D 缩略图 | `/maps/{seedKey}.png` | `public/maps/*.png` |
| 地面贴图 | `/textures/ground/{dirt\|asphalt\|neon}.png` | 按 genre 选用 |

### 3.2 建筑 GLB

```
/models/buildings/{genre}/{filename}.glb?v=mm5
```

- **genre**：`ancient`, `wuxia`, `xuanhuan`, `modern`, `mystery`, `scifi`
- **常见 filename**：`palace.glb`, `temple_a.glb`, `commercial_a.glb`, `residential_a.glb`, `tower_a.glb`, `dock.glb`, `office.glb`, `shop.glb`
- 注册表：`frontend/src/lib/buildingKits.ts`

### 3.3 人物 GLTF + PBR

| 资产 | URL 模式 |
|------|---------|
| 角色 body | `/models/characters/roles/{roleId}/body.glb` |
| 角色皮肤（×4） | `/models/characters/roles/{roleId}/skins/{fair\|tan\|warm\|pale}/{albedo,roughness,normal,metalness}.png` |
| 共享布料 PBR | `/models/characters/pbr/cloth_{clothPackId}/…` |
| 共享金属 PBR | `/models/characters/pbr/metal_{metalPackId}/…` |
| 资产目录 | `/models/characters/roles/catalog.json` |

**四套肤色 ID**（`RoleSkinId`）：`fair`, `tan`, `warm`, `pale`

---

## 4. 3D 地图 JSON 格式

**类型定义位置**：`frontend/src/components/World3D.tsx` → `MapData`

### 4.1 顶层结构

```typescript
{
  width: number;          // 典型 960
  height: number;         // 典型 540
  name: string;           // 地图显示名
  genre?: string;
  locations: MapLoc[];    // 叙事地点 pin
  factions: MapFac[];     // 势力区域（影响地形高度）
  terrain?: { seed?: number; maxHeight?: number; waterLevel?: number };
  water?: WaterRegion[];
  rivers?: RiverRegion[];
  bridges?: BridgeSeg[];
  shore_grass?: ShoreSpot[];
  trees?: TreeSpot[];
  buildings?: Building[];
  animals?: Animal[];
  roads?: RoadSeg[];
  walls?: CityWall[];     // 渲染代码中城墙 Extrude 已注释
  fields?: FieldPatch[];
  cities?: { name: string; x: number; y: number; r: number }[];
}
```

### 4.2 坐标系

- JSON 内坐标为 **地图像素** `(x, y)`，原点在左上角。
- 世界坐标转换：`SCALE = 0.38`

```
worldX = (px - width/2) * 0.38
worldZ = (py - height/2) * 0.38
```

### 4.3 关键子结构

**locations**（与叙事 world.locations 按 name 匹配）：

```typescript
{ name: string; x: number; y: number; building?: string; enterable?: boolean }
```

**buildings**：

```typescript
{
  name: string; x: number; y: number;
  w: number; h: number;
  enterable?: boolean;
  floors?: number;
  type?: BuildingType;  // palace|temple|commercial|...
  sign?: string; banner?: string;
  rot?: number;
  city?: string;
}
```

**roads**：

```typescript
{ from: [x, y]; to: [x, y]; kind?: "dirt" | "paved" | "neon" }
```

**terrain**：`seed` 驱动 FBM 噪声高度场；`factions` 的 `terrain: "peak"|"valley"|"hill"` 叠加局部起伏；`cities` 产生平整 pad。

### 4.4 示例

`public/maps/ancient.json`：含 `terrain.seed: 1201`、河流（如「渭水」）、数百 `buildings` 与 `cities` 等手工字段。  
可由 `backend/scripts/generate_maps.py` 从 seed 再生成/合并。

---

## 5. World3D 渲染管线

**文件**：`frontend/src/components/World3D.tsx`

### 5.1 Props（完整）

```typescript
type Props = {
  genre: string;
  worldLocations: { id: string; name: string }[];
  agents: Agent[];
  playerId: string | null;
  height?: number;                    // 默认容器高度
  cameraMode: "third" | "first";
  onCameraModeChange: (m: CameraMode) => void;
  dormant?: boolean;                  // 玩家离线时 dim
  onEnterBuilding?: (name: string) => void;
  hour?: number;                      // 0–23，日夜光照
};
```

### 5.2 加载与渲染顺序

1. `fetch(/maps/{genre}.json)` → 未成功则显示加载占位
2. **地形**：160×160 细分平面 + 顶点色 + FBM 位移；地面贴图按 genre（dirt/asphalt/neon）
3. **水体 / 河流 / 桥 / 田 / 树 / 岸草**：程序化 mesh，采样 `heightAt(x,z)`
4. **道路**：`Architecture.tsx` → `SmoothRoad`
5. **建筑**：`DetailedBuilding` → `resolveBuildingModel(genre, role, buildingName)` → `KitBuildingMesh`；失败时 procedural fallback
6. **街道行人**：道路 capsules（**非** GLTF 角色）
7. **动态 Agent**：`DynamicAgent` → `HumanoidFigure`
8. **光照 / 天空 / 雾 / 星星 / Bloom**：由 `hour` 驱动
9. **相机**：第三人称 orbit 跟随玩家；第一人称 `PointerLockControls`；键 `V` 切换
10. **室内**：点击可进入建筑 → 简单 box `InteriorRoom`

### 5.3 Agent 位置解析

优先级：

1. `agent.world_x` / `agent.world_z`（-1..1 归一化 → 世界坐标）
2. `agent.location_id` → 匹配 `worldLocations` → map `locations` 按 **name** 取 pin 坐标
3. fallback 至 map 默认点

### 5.4 Play 页集成

```typescript
// play/[sid]/page.tsx
<World3D
  genre={session.world.genre}
  worldLocations={session.world.locations || []}
  agents={session.agents}
  playerId={session.player_id}
  height={520}
  cameraMode={cameraMode}
  onCameraModeChange={setCameraMode}
  dormant={isOffline}   // presence === dormant | proxy
  hour={session.world.clock?.hour ?? 10}
/>
```

- 会话每 **4 秒** poll `GET /api/sessions/{sid}` 更新 agents 位置
- `dormant` 时玩家模型半透明/降亮

---

## 6. 建筑 GLB 模型

**注册表**：`frontend/src/lib/buildingKits.ts`

### 6.1 BuildingRole 枚举

```
commercial | residential | temple | dock | palace
tower | shop | office | ship_port | stall
```

### 6.1 解析流程

1. 地图 building 若无 `type`，`inferBuildingType(name, genre)` 按中文/英文关键词推断
2. `resolveBuildingModel(genre, role, buildingName)` 从 `GenreKit[role]` 变体列表中按 **buildingName hash** 选取
3. `KitBuildingMesh` 用 `useGLTF(url)` 加载，应用 `scale`, `y`, `tint`, `emissive`

### 6.2 GenreKit 覆盖

| genre | 文件 |
|-------|------|
| ancient | `ANCIENT_KIT` |
| wuxia | `WUXIA_KIT` |
| xuanhuan | `XUANHUAN_KIT`（含 emissive 玄幻光效） |
| modern | `MODERN_KIT` |
| mystery | `MYSTERY_KIT` |
| scifi | `SCIFI_KIT` |

### 6.3 dev/maps 预加载

`/dev/maps` 在 genre 变化时调用 `preloadKitUrls(genreKitUrls(genre))` 预热 GLB；Play 页**不做**预加载。

---

## 7. 人物 GLTF 与 PBR 皮肤

### 7.1 FigurePreset 结构

**定义**：`frontend/src/lib/characterFigures.ts`

```typescript
type FigurePreset = {
  id: string;
  label: string;
  genre: SceneGenre;           // wuxia|ancient|scifi|xuanhuan|mystery
  bodyId: string;              // = roleId，对应 body.glb 目录名
  skinVariant: RoleSkinId;     // fair|tan|warm|pale
  clothPack: ClothPackId;
  metalPack: MetalPackId;
  weapon: WeaponKind;
  style: FigureStyle;
  silhouette: Silhouette;
  build: { height: number; bulk: number };
  skin, hair, torso, legs, accent: string;  // 色值 hint
  cape?, hood?, pauldrons?, glow?, tall?;
};
```

约 **30+** preset，覆盖 wuxia/ancient/scifi/xuanhuan/mystery 及通用 NPC。

### 7.2 resolveFigure(agent, genre) 优先级

**文件**：`characterFigures.ts`

1. `agent.appearance.figure` 显式指定 → `FIGURE_PRESETS[id]`
2. 职业启发式（如 剑→swordsman，医→doctor 等）
3. `hash(name|profession)` 从 `presetsForGenre(genre)` 选取
4. 肤色：`agent.appearance.skin` → `RoleSkinId`

**modern genre**：无专属 `FIGURE_PRESETS` 条目，fallback 可能选到其他 genre 池或默认 NPC。

### 7.3 渲染栈

```
HumanoidFigure
  Suspense → 失败则 ProceduralHumanoid（胶囊 + figureMaterials）
  成功 → GltfHumanoid
    useGLTF(/models/characters/roles/{bodyId}/body.glb)
    clone SkinnedMesh
    classifyMaterialSlot(meshName) → skin | cloth | metal | hair | eye
    绑定 role skins PBR + shared cloth/metal packs
    useFrame: walk/swim bob 动画
```

**材质槽分类**：`frontend/src/lib/gltfCharacters.ts` → `classifyMaterialSlot`

### 7.4 NpcPanel 中的非 3D 展示

`NpcPanel` / `NpcChat` 使用 `resolveFigure` 生成 **2D badge**（`CharacterFigureThumb`），与 World3D 内模型一致。

---

## 8. 角色创建流程

**页面**：`/create/[seedKey]`

```
listSeeds + getPlayerCatalog(seedKey)
  → CivilizationDashboard（2D 信息）
  → CharacterPicker（选 category/variant/skin）
  → CharacterFigurePreview（3D 预览）
  → createSession({ seed_key, category_key, variant_key, skin })
  → sessionStorage sess_{sid}
  → /play/[sid]  World3D 显示所选 figure
```

- 地图缩略图：`/maps/{seedKey}.png`（2D，非 3D）
- figure ID 默认模式：`{seedKey}_{variantKey}`（如 `wuxia_wanderer`）
- 存入 `agent.appearance`: `{ figure, category, skin }`
- 后端 catalog：`backend/app/seeds/player_catalog.json` + `player_catalog.py`

---

## 9. 开发预览页

### 9.1 `/dev/maps`

**文件**：`frontend/src/app/dev/maps/page.tsx`

| 项 | 行为 |
|----|------|
| World3D | `agents=[]`, `worldLocations=[]`, `playerId=null` |
| 控件 | genre select、hour slider |
| 预加载 | `preloadKitUrls(genreKitUrls(genre))` |
| 相机 | 允许 orbit 平移（无玩家跟随） |
| 认证 | 无 gate |

### 9.2 `/dev/figures`

**文件**：`frontend/src/app/dev/figures/page.tsx`

| 项 | 行为 |
|----|------|
| 组件 | `CharacterFigurePreview` + `CharacterFigureThumb` |
| 功能 | 按 genre 筛 preset、切换 4 种 skin |
| 光照 | `genreStageMood(genre)` |
| World3D | **不使用** |

---

## 10. 与实验平台的关系

| 项 | 实验平台 `/labs/*` | 叙事 Play |
|----|-------------------|-----------|
| World3D | ❌ 不挂载 | ✅ |
| CivilizationDashboard | ✅ compact | ✅（WorldDrawer 内） |
| 金融/军事等推演 | ✅ 2D 面板 | ❌（金融入口已移除） |
| 文明选择 | `CivilizationSelector` + `openLab` | 创建时固定 seed |

实验平台切换文明**不会**加载 3D 地图；仅影响数值引擎 seed 与 dashboard 文案。

---

## 11. 资产生成脚本

| 脚本 | 输出 |
|------|------|
| `backend/scripts/generate_maps.py` | `frontend/public/maps/{genre}.json` + PNG |
| `backend/scripts/build_architecture_kits.py` | `frontend/public/models/buildings/{genre}/*.glb` |
| `backend/scripts/generate_role_bodies.py` | `frontend/public/models/characters/roles/{id}/body.glb` + skins |

**注意**：新 clone 仓库若 `public/models/` 不完整，需运行上述脚本 regenerate。

---

## 12. 已知限制与缺口

| # | 限制 | 影响 |
|---|------|------|
| 1 | 3D 地图按 genre 非 seed | 同 genre 地理完全相同 |
| 2 | military/enterprise/securities 无 map | Play 3D 永久 loading |
| 3 | modern 无 figure preset | 角色可能 appearance 不匹配 |
| 4 | 街道行人 / 动物 | 胶囊 primitive，非 GLTF |
| 5 | 城墙 walls | World3D 中 Extrude 渲染已注释 |
| 6 | GLTF 依赖生成脚本 | 缺文件时降级 ProceduralHumanoid |
| 7 | 实验平台无 3D | 金融推演与 3D 世界无联动 |

---

## 13. 源码索引

| 文件 | 职责 |
|------|------|
| `frontend/src/components/World3D.tsx` | 主 3D 视口 |
| `frontend/src/components/world/Architecture.tsx` | 道路 |
| `frontend/src/components/world/KitBuildingMesh.tsx` | GLB 加载 |
| `frontend/src/components/HumanoidFigure.tsx` | 角色入口 |
| `frontend/src/components/GltfHumanoid.tsx` | GLTF 渲染 |
| `frontend/src/components/CharacterFigurePreview.tsx` | 独立预览 Canvas |
| `frontend/src/lib/buildingKits.ts` | 建筑 URL 注册 |
| `frontend/src/lib/characterFigures.ts` | preset + resolveFigure |
| `frontend/src/lib/gltfCharacters.ts` | PBR URL + 材质槽 |
| `frontend/src/lib/figureMaterials.tsx` | 程序化降级材质 |
| `frontend/public/maps/*.json` | 3D 地图数据 |
| `frontend/public/models/buildings/` | 建筑 GLB |
| `frontend/public/models/characters/` | 角色 GLTF + PBR |
| `backend/app/seeds/*.json` | 文明 seed 源数据 |

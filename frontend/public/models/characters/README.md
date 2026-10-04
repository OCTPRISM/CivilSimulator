# Character GLTF assets

## Civilizations (selectable outfits + props)

Each built-in civilization has a curated pack:

`civilizations/{civ}/`

```
catalog.json
character/body.glb + skins/{fair|tan|warm|pale}/
outfits/{outfit_id}/meta.json     # 4 packs: clothing + props + prompt
props/{prop_slug}/prop.glb        # selectable prop meshes
```

Index: `civilizations/index.json`

Regenerate:

```bash
python3 backend/scripts/generate_civilization_assets.py
```

API: `GET /api/generator/civilizations` · `GET /api/generator/outfits?civilization=wuxia`

## Role bodies (canonical)

Each playable / NPC figure has a **unique** GLB under:

`roles/{roleId}/body.glb`

Genre silhouettes are **baked into the mesh** (not Mixamo remaps + runtime hats):

| Genre | Art direction |
|-------|----------------|
| wuxia | 射雕 / 仙剑 — 劲装、广袖、发髻、披风、兵刃 |
| ancient | 汉唐明古装 — 交领深衣、襆头、甲胄 |
| scifi | 机械 / 制服 / 特战 / 宇航硬表面 |
| xuanhuan | 西游 — 僧袍、天将甲、法器 |
| mystery | 福尔摩斯 — 猎鹿帽、披风大衣 |
| modern / enterprise / securities | 当代制服 / 街头 / 职场 |
| military | 迷彩 / 战术硬表面（复用 scifi 轮廓） |

### Skins (4 per body)

`roles/{roleId}/skins/{fair|tan|warm|pale}/`

Separated PBR: `albedo.png` `roughness.png` `normal.png` `metalness.png`

Regenerate:

```bash
python3 backend/scripts/generate_role_bodies.py
```

Catalog: `roles/catalog.json`

## Shared cloth / metal PBR (`pbr/`)

Still used to enrich Cloth / Metal material slots after load. Skin always comes from the **role-owned** pack the player selects.

## Legacy shared bodies

`soldier.glb` `xbot.glb` `michelle.glb` `rpm.glb` `robot.glb` are no longer the default path for roles.

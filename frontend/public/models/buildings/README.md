# Building model kits (CC0)

Per-civilization GLB libraries used by `World3D` via `lib/buildingKits.ts`.

## Sources (all CC0 / Public Domain)

| Pack | Author | Used for |
|------|--------|----------|
| City Kit (Commercial) | Kenney.nl | modern towers, shops, offices |
| City Kit (Suburban) | Kenney.nl | mystery residential |
| City Kit (Industrial) | Kenney.nl | scifi / mystery warehouses |
| Castle Kit | Kenney.nl | ancient / wuxia / xuanhuan temples & walls |
| Pirate Kit | Kenney.nl | wooden shops, docks, scifi ships as ports |
| Ancient assets v2 | CivSim procedural | landmarks, farmhouses, residential a–f, street props |

Attribution not required under CC0; appreciated: [Kenney.nl](https://kenney.nl).

License texts are copied under `_src/`.

## Layout

```
buildings/{genre}/*.glb
props/ancient/*.glb   # lantern, banner, table, stool, well, …
```

### Ancient hero landmarks
- `landmark_tavern.glb` — 醉仙楼 / 西市酒肆
- `landmark_palace.glb` — 紫宸殿
- `landmark_temple.glb` — 终南古观

### Ancient housing variants
- `residential_a`…`f` — town houses
- `farmhouse_a`…`d` — thatch/clay rural houses

Regenerate: `backend/.venv/bin/python backend/scripts/build_ancient_assets_v2.py`

Genres: `ancient`, `wuxia`, `xuanhuan`, `modern`, `mystery`, `scifi`.

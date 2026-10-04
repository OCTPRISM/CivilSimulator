# Map Briefs v2 — 推翻重建用详细地图提示词

本目录是 **3D 地图推翻重建** 的唯一叙述源。旧版 `layout_city_maps.py` / `public/maps/*.json` 的拓扑、尺度、建筑套件 **不得** 再作为设计输入；重建时只读本目录。

| 文件 | 用途 |
|------|------|
| `civilization_map_prompts.json` | 九文明 master prompt + `spatial_logic.distances` |
| `validation_matrix.json` | 物理 / 常识 / 剧情符合性矩阵 |

每文明 `spatial_logic.distances` 强制字段：

- `anchors`：关键锚点平面/高程坐标（米）
- `pair_distances_m`：据点与关键设施 path / straight 距离与步行（或车行）时间
- `clearances_m`：路宽、河宽、退线、防火间距等断面
- `intersections`：道路·水位·建筑·管线如何碰头（位置 + 交汇物 + 细部）
- `adjacency`：共墙 / 隔巷 / 贴临关系

`master_prompt` 末尾同步嵌入【相对距离总表】，供文生图/建造管线直接消费。

流程：提示词定稿 → 校验通过 → 再生成地形 / 道路 / 建筑 / 植被资产。

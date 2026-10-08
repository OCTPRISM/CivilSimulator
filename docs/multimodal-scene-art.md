# 生产多模态主路径：场景插画（v0.5 P-5）

选定 **Pillow 场景插画** 作为 Tech Preview → 小流量公网的生产多模态主路径。

## 为何选它

| 路径 | 依赖 | 公网可预期性 |
|------|------|----------------|
| Scene art（本路径） | Pillow，CPU | 高 |
| 浏览器 TTS / BGM | 客户端 | 辅助，非服务端 SLA |
| Hunyuan3D | 本地 GPU/重服务 | 可选离线，非主路径 |

## API

- `GET /api/multimodal/info` — `production_path: scene_art`
- `GET /api/media/scene-art?...` — 生成/命中缓存后默认 302 到内容寻址文件
- `GET /api/media/scene-art/file/{sha}.png` — 不可变缓存（`Cache-Control: immutable`）

限流：`SCENE_ART_RATE_LIMIT_PER_MINUTE`（默认 120）。关闭：`SCENE_ART_ENABLED=false`。

## Play

前端 `ScenePlate` 继续请求查询 URL；浏览器跟随 302，按 hash 文件缓存。

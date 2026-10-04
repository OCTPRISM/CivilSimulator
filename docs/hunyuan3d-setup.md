# Hunyuan3D-2 本地部署

本机推荐配置：**Apple M5 Max** → `Hunyuan3D-2mini-Turbo`（0.6B，约 6 GB 形状生成显存，FlashVDM 加速）。

## 一键安装

```bash
chmod +x backend/scripts/hunyuan3d/setup_mac.sh
./backend/scripts/hunyuan3d/setup_mac.sh
```

首次运行会从 Hugging Face 下载约 4–8 GB 模型权重。

## 启动 API 服务

```bash
chmod +x backend/scripts/hunyuan3d/start_server.sh
./backend/scripts/hunyuan3d/start_server.sh
```

默认监听 `http://127.0.0.1:8080`。CivilSimulator 后端通过 `HUNYUAN3D_URL` 环境变量连接。

## 模型选择

| 机型 | 推荐模型 | 说明 |
|------|----------|------|
| M 系列 Mac | `Hunyuan3D-2mini-Turbo` | shape-only，MPS + low_vram |
| 16GB+ 独显 | `Hunyuan3D-2-Turbo` + Paint | 形状 + 贴图（需 CUDA 光栅化扩展） |

Mac 上贴图管线（custom_rasterizer）通常需跳过；可在 `.env` 中设置 `HUNYUAN3D_TEXTURE=false`。

## CivilSimulator 集成

- 前端：`/generator` — 人物 / 地图双模式
- API：`GET /api/generator/status`，`POST /api/generator/character`，`POST /api/generator/map`
- 输出目录：`data/runtime/generator/`

## 参考

- [Tencent-Hunyuan/Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)

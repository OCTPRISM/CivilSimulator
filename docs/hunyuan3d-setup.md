# Hunyuan3D-2 本地部署

本机推荐配置：**Apple M5 Max** → `Hunyuan3D-2mini-Turbo`（0.6B，约 6 GB 形状生成显存，FlashVDM 加速）。

Hunyuan **源码与权重不进 git**（约 20–28 GB）。一键脚本负责下载并部署到 `third_party/`。

## 一键安装（推荐）

```bash
# 与前后端依赖一起：源码 + 官方权重 + MLX Paint 权重 + hy3dgen venv
./scripts/bootstrap.sh

# 只要 Hunyuan
./backend/scripts/hunyuan3d/setup_mac.sh
```

只拉源码、不拉权重：`./scripts/bootstrap.sh --skip-weights`。  
完全跳过：`./scripts/bootstrap.sh --skip-hunyuan`。

| 路径 | 内容 |
|------|------|
| `third_party/Hunyuan3D-2` | 官方 Python 源码（`api_server.py` / `hy3dgen`） |
| `third_party/Hunyuan3D-MLX` | Mac MLX Paint / Swift CLI 源码 |
| `third_party/hy3d_models/tencent/Hunyuan3D-2` | 官方 shape + paint + delight 权重 |
| `third_party/hy3d_models/tencent/Hunyuan3D-2mini` | mini / turbo shape 权重 |
| `third_party/hy3d_mlx_weights/paint` | MLX 转换后的 Paint-large 权重 |

`setup_mac.sh` 会调用 `backend/scripts/hunyuan3d/fetch_vendor.sh`（可断点续传）。  
`./scripts/start.sh` 若检测到上述目录不完整，会在起服前补拉。

gated 仓库：在 Hugging Face 接受 Tencent 许可后设置 `HF_TOKEN`。国内可用 `HF_ENDPOINT=https://hf-mirror.com`。

## 启动 API 服务

```bash
./backend/scripts/hunyuan3d/start_server.sh
# 或
./scripts/start.sh --hunyuan
```

默认监听 `http://127.0.0.1:8080`，离线读取 `HY3DGEN_MODELS=third_party/hy3d_models`。  
CivilSimulator 后端通过 `HUNYUAN3D_URL` 连接（见 `backend/.env.example`）。

源码或权重缺失时，`start_server.sh` 会先跑 `fetch_vendor.sh` / `setup_mac.sh`。

## 模型选择

| 机型 | 推荐模型 | 说明 |
|------|----------|------|
| M 系列 Mac | `Hunyuan3D-2mini-Turbo` | shape-only，MPS + low_vram |
| 16GB+ 独显 | `Hunyuan3D-2-Turbo` + Paint | 形状 + 贴图（需 CUDA 光栅化扩展） |

Mac 上贴图管线（custom_rasterizer）通常需跳过；可在 `.env` 中设置 `HUNYUAN3D_TEXTURE=false`。角色烤贴图走 MLX：`backend/scripts/hunyuan3d/paint_ancient_hy3d_mlx.sh`。

## CivilSimulator 集成

- 前端：`/generator` — 人物 / 地图双模式
- API：`GET /api/generator/status`，`POST /api/generator/character`，`POST /api/generator/map`
- 输出目录：`data/runtime/generator/`

## 参考

- [Tencent-Hunyuan/Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [ZimengXiong/Hunyuan3D-MLX](https://github.com/ZimengXiong/Hunyuan3D-MLX)

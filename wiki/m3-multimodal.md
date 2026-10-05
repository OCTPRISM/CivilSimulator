# M3：多模态（场景插画 / TTS / BGM）

状态：**已完成（Phase A — 本地轻量，不依赖 GPU）**

---

## 目标

Play 对白层增加氛围感知：场景插画、旁白朗读、背景音乐。本阶段全部本地可跑，不阻塞后续 Hunyuan / 服务端 TTS。

---

## 能力一览

| 能力 | 实现 | 开关 |
|------|------|------|
| TTS 旁白 | 浏览器 `speechSynthesis`（zh-CN） | 系统菜单「朗读」；可选语速、朗读对白 |
| BGM | WebAudio 程序化氛围（按 genre） | 系统菜单「背景音乐」；TTS 播放时自动压低 |
| 场景插画 | Pillow 氛围板（缓存 PNG） | 系统菜单「场景插画」；对白可见时叠在 3D 后 |

---

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tts/info` | 声明当前后端能力（浏览器 TTS / 程序化 BGM / Pillow 插画） |
| GET | `/api/media/scene-art?genre=&location=&summary=&hour=&tension=` | 返回缓存 PNG（`Cache-Control: max-age=86400`） |

缓存目录：`{DATA_DIR}/scene_art/{sha1[:16]}.png`

---

## 前端

| 模块 | 路径 |
|------|------|
| TTS / BGM / 翻页音 | `frontend/src/lib/audio.ts` |
| 本地设置 | `frontend/src/lib/playSettings.ts`（`bgm` / `ttsRate` / `ttsReadSpeech` / `sceneArt`） |
| 场景板 UI | `frontend/src/components/ScenePlate.tsx` |
| 系统菜单 | `frontend/src/components/play/PlayShell.tsx` → `PlaySystemMenu` |
| 接线 | `frontend/src/app/play/[sid]/page.tsx` |

---

## 后端

| 模块 | 路径 |
|------|------|
| Pillow 生成 | `backend/app/layer1_foundation/scene_art.py` |
| 路由 | `backend/app/main.py`（`/api/tts/info`、`/api/media/scene-art`） |

色板按 `genre`（ancient / wuxia / xianxia / scifi / mystery）变化；`hour` 影响昼夜，`tension` 偏暖红。

---

## 验证

```bash
cd backend && source .venv/bin/activate
QDRANT_ENABLED=false LLM_PROVIDER=mock pytest tests/test_scene_art.py -q
```

冒烟：打开 Play → Esc 系统菜单开启朗读 / BGM / 场景插画 → 推进一幕，确认对白层有氛围板、有环境音，开启 TTS 时旁白朗读且 BGM 压低。

---

## 非目标（后续）

- 服务端 TTS / 语音克隆  
- Hunyuan / 扩散模型真实场景图  
- 曲库式 BGM 资源包  

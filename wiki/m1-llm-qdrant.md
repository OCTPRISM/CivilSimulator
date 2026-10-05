# M1：本地 LLM 与 Qdrant 向量记忆

状态：**已完成**

---

## 目标

用本地推理替代纯 Mock，让叙事 / NPC / 持续模拟走真实模型；用向量检索提升 Agent 回忆质量。

---

## LLM（Ollama）

| 项 | 说明 |
|----|------|
| 默认 Provider | `LLM_PROVIDER=ollama` |
| 默认文本模型 | `qwen3.8:27b` |
| 自动回退 | `gpt-oss:20b`，再 `qwen3.6:35b-a3b` |
| Base URL | `http://localhost:11434` |
| 实现 | `backend/app/layer1_foundation/ollama_llm.py` |

启动时会探测本机已装模型；若首选缺失则按 `OLLAMA_TEXT_FALLBACKS` 选择。

对 `qwen3.*` 关闭 `think`，避免长链推理拖垮建会话超时。

### 常用环境变量

```bash
LLM_PROVIDER=ollama
OLLAMA_TEXT_MODEL=qwen3.8:27b
OLLAMA_TEXT_FALLBACKS=gpt-oss:20b,qwen3.6:35b-a3b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
```

其它：`LLM_PROVIDER=openai` + `OPENAI_API_KEY`；离线 `LLM_PROVIDER=mock`。

---

## Embedding

| 项 | 说明 |
|----|------|
| 默认模型 | `nomic-embed-text`（768 维） |
| 拉取 | `ollama pull nomic-embed-text` |
| 回退 | 未安装时用 `HashEmbedder`（仅开发用，非语义） |

---

## Qdrant 向量记忆

| 项 | 说明 |
|----|------|
| 默认模式 | 嵌入式本地目录（**无需 Docker**） |
| 路径 | `QDRANT_PATH=data/runtime/qdrant` |
| 可选服务 | `QDRANT_URL=http://localhost:6333` |
| 集合 | `civsim_memories`（按 `session_id` / `actor_id` 过滤） |
| 关闭 | `QDRANT_ENABLED=false` → 进程内余弦召回 |

实现：

- 索引：`backend/app/layer1_foundation/qdrant_memory.py`
- 存储 / 召回：`backend/app/layer3_agents/memory.py`（近期 ∪ 语义 top-k）

> 嵌入式路径同一时刻只能被一个进程打开。多 worker 请改用 `QDRANT_URL`。

---

## 验证

```bash
cd backend && source .venv/bin/activate
pytest tests/test_qdrant_memory.py -q
```

冒烟：写入「西市米价」等记忆后，用「米价/粮价」查询应优先召回相关条目。

---

## 相关配置

见仓库根目录 [README.md](../README.md) 与 `backend/app/config.py`。

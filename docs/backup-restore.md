# data/runtime 备份与恢复演练（v0.5 P-3）

目标：在进程停机后，能从备份恢复到 **能登录 → 从「我的世界」续玩**（方案 B 快照 + 用户库）。

## 备份什么

默认目录：`backend/data/runtime/`

| 内容 | 作用 |
|------|------|
| `civsim.db` | 用户、成员、方案 B 快照元数据 / 事件 |
| `qdrant/`（若启用） | 向量记忆嵌入式库 |
| `generator/` 等 | 可选生成资产 |

不在本演练范围：前端 `.next`、本机 Ollama 模型权重、Hunyuan3D 服务状态。

## 备份

后端可在运行中备份（脚本对 SQLite 优先用 `.backup`）：

```bash
chmod +x backend/scripts/backup_runtime.sh backend/scripts/restore_runtime.sh
./backend/scripts/backup_runtime.sh
# 或指定目录：
# ./backend/scripts/backup_runtime.sh ~/civsim-backups
```

产物：`backend/data/backups/civsim-runtime-<UTC>.tar.gz`（或你指定目录下的同名文件）。

## 恢复演练（建议每发一版做一次）

1. **停服**：结束 uvicorn 与 Next（避免写库冲突）。  
2. **恢复**：

```bash
./backend/scripts/restore_runtime.sh backend/data/backups/civsim-runtime-<stamp>.tar.gz
```

脚本会把现有 `data/runtime` 改名为 `data/runtime.pre-restore-<stamp>`。  
3. **起服**（与备份时相同的 `AUTH_SECRET` / `ENV`）：

```bash
cd backend && source .venv/bin/activate
# 使用原 .env；AUTH_SECRET 必须一致，否则旧 token 全部失效
LLM_PROVIDER=mock QDRANT_ENABLED=false uvicorn app.main:app --port 8000
```

4. **验收**  
   - 用备份前的账号登录成功  
   - 「我的世界」能看到原房间；有快照的可点续玩  
   - `POST /api/sessions/{sid}/step` 至少一次成功  

失败时：把 `data/runtime.pre-restore-*` 移回 `data/runtime` 即可回滚本次恢复。

## 密钥与备份

轮换 `AUTH_SECRET` 会使所有已签发 bearer token 立即失效（需重新登录）。备份会保存用户行，但 **不会** 让旧 token 在新 secret 下继续有效。轮换步骤见 [密钥轮换](./ops-secrets.md)。

## 限制（诚实）

- 多机多 worker：请对 **粘滞到同一会话状态的那台** 做 runtime 备份，或改为共享存储后再定义拓扑级备份。  
- Qdrant 在写入高峰时仍可能出现短暂不一致；演练以「可登录 + 可续玩」为准，不要求 bit-perfect 记忆。  

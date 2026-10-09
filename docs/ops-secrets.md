# 密钥与依赖审计（v0.5 P-6）

## AUTH_SECRET

- 开发默认值仅允许 `ENV=development` / `dev`（见 `assert_auth_secret_safe`）。  
- 生产：`ENV=production` + 足够长的随机 `AUTH_SECRET`。  
- Token 格式：HMAC 签名的 `user_id:exp:sig`（约 30 天）。

### 轮换步骤（含宽限期）

v0.5 起支持 **双 secret 宽限期**：新密钥签发，旧密钥在宽限期内仍可验签。

1. 选低峰；通知邀测用户「无需立刻重登，但建议尽快」。  
2. 生成新 secret：

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

3. 把**当前** `AUTH_SECRET` 挪到 `AUTH_SECRET_PREVIOUS`，再把新值写入 `AUTH_SECRET`。  
4. 滚动重启后端；旧 token 仍可进房，新登录签发新密钥签名。  
5. 宽限期结束后（建议 ≤ 会话 TTL，约 30 天）去掉 `AUTH_SECRET_PREVIOUS` 并再重启——仅新密钥有效。

约束：`AUTH_SECRET_PREVIOUS` 不得等于当前密钥，也不得使用开发默认值。

硬切换（无宽限期）仍可用：只改 `AUTH_SECRET`、不设 PREVIOUS → 全员重新登录。

## 其他敏感项

| 变量 | 说明 |
|------|------|
| `INVITE_CODE` | 生产邀测注册码；泄露则轮换并通知 |
| `OPENAI_API_KEY` | 仅 `LLM_PROVIDER=openai` |
| `REDIS_URL` | 含密码时勿写入文档或日志 |
| `QDRANT_API_KEY` | 远端 Qdrant 时使用 |
| `SENTRY_DSN` | 可选；需本机 `pip install 'sentry-sdk[fastapi]'` |

## 依赖审计

CI（P-6）在每次 push/PR 跑：

- `pip-audit -r backend/requirements.txt`
- `npm audit --omit=dev --audit-level=high`（frontend）

当前 job 为 **advisory**（`continue-on-error`）：结果可见，不单独挡功能 CI。发版 / 打 tag 前必须人工看一眼，能修则修。

本地复跑：

```bash
cd backend && source .venv/bin/activate
pip install pip-audit
pip-audit -r requirements.txt

cd ../frontend
npm audit --omit=dev --audit-level=high
```

### 已知暂缓（打 tag 前复查）

| 面 | 项 | 理由 / 跟踪 |
|----|----|-------------|
| 后端 | Starlette 随 FastAPI 0.115.x 约束的若干 advisory | 等下一轮 FastAPI 次要升级一并消化；功能 CI 已绿 |
| 后端 | Pillow 11.x → 12.x 多条 advisory | 升 12 可能牵动场景插画路径；v0.5.1 / v1.0 候选 |
| 前端 | Next 14 嵌套 `postcss@8.4.31` high | 需 Next 大版本或官方嵌套升级；勿 `npm audit fix --force` 强升 Next 16 |

高危项：能修则修并记入 CHANGELOG；暂缓须保留本表理由。

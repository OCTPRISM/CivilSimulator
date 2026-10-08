# 密钥与依赖审计（v0.5 P-6 起步）

## AUTH_SECRET

- 开发默认值仅允许 `ENV=development` / `dev`（见 `assert_auth_secret_safe`）。  
- 生产：`ENV=production` + 足够长的随机 `AUTH_SECRET`。  
- Token 格式：HMAC 签名的 `user_id:exp:sig`（约 30 天）。**更换 secret = 全员重新登录。**

### 轮换步骤

1. 选低峰；通知邀测用户将重新登录。  
2. 停后端。  
3. 生成新 secret，写入 `.env`（勿提交仓库）：

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

4. 起服；用账号密码重新登录，确认 Play / WS 正常。  
5. 旧 token 无需吊销列表——签名已无法通过校验。

尚无**双 secret 宽限期**（v1.0 候选）：当前单密钥，轮换是硬切换。

## 其他敏感项

| 变量 | 说明 |
|------|------|
| `INVITE_CODE` | 生产邀测注册码；泄露则轮换并通知 |
| `OPENAI_API_KEY` | 仅 `LLM_PROVIDER=openai` |
| `REDIS_URL` | 含密码时勿写入文档或日志 |
| `QDRANT_API_KEY` | 远端 Qdrant 时使用 |

## 依赖审计（手工）

CI（P-4）跑功能测试；发版前额外：

```bash
cd backend && source .venv/bin/activate
pip install pip-audit
pip-audit -r requirements.txt

cd ../frontend
npm audit --omit=dev
```

高危项：能修则修并记入 CHANGELOG；暂缓须在 Release 文档写明理由与跟踪。

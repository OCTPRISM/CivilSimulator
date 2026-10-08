# Contributing

CivilSimulator is maintained solely by **Zhongjiang Yao**.

## Scope

This repository is a Tech Preview under active solo development. External pull requests are not the primary contribution path right now; if you have a bug report or a concrete proposal, open a GitHub Issue with reproduction steps when possible.

## Local checks before opening an issue

```bash
cd backend && source .venv/bin/activate
QDRANT_ENABLED=false LLM_PROVIDER=mock pytest tests/ -q
```

Frontend typecheck (from `frontend/`):

```bash
npm run typecheck
```

CI (v0.5 P-4) runs the same pair on every push / PR to `main` — see `.github/workflows/ci.yml`.

## Author

Commits and releases are authored as **Zhongjiang Yao** (`yaozj_roger@163.com`).

## License

See [LICENSE](./LICENSE) (MIT).

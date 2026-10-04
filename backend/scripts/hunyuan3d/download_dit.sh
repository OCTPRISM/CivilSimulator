#!/usr/bin/env bash
# Resume / finish HunyuanDiT-v1.1-Diffusers-Distilled download (~6–8 GB total).
# Run this in a normal Terminal (outside Cursor sandbox) if HF is blocked here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV="$ROOT/backend/.venv-hunyuan3d"

# Prefer no proxy + China mirror (override with env if needed)
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
export NO_PROXY='*'
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "HF_ENDPOINT=$HF_ENDPOINT"
echo "Cache: ~/.cache/huggingface/hub/models--Tencent-Hunyuan--HunyuanDiT-v1.1-Diffusers-Distilled"
echo "Resuming download…"

python3 -u <<'PY'
from pathlib import Path
import time
from huggingface_hub import snapshot_download

t0 = time.time()
path = snapshot_download(
    repo_id="Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled",
    max_workers=4,
)
print(f"DONE in {time.time()-t0:.0f}s → {path}")
t = Path(path) / "transformer"
for f in sorted(t.rglob("*")):
    if f.is_file():
        print(f"  {f.name}: {f.stat().st_size/1e9:.3f} GB")
blobs = Path.home() / ".cache/huggingface/hub/models--Tencent-Hunyuan--HunyuanDiT-v1.1-Diffusers-Distilled/blobs"
incs = list(blobs.glob("*.incomplete"))
print(f"incomplete leftovers: {len(incs)}")
if incs:
    print("Tip: delete *.incomplete and re-run if a shard is stuck.")
PY

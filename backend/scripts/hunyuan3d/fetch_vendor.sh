#!/usr/bin/env bash
# Download Hunyuan3D source + weights into third_party/ (not git-tracked, ~20–28 GB).
#
#   ./backend/scripts/hunyuan3d/fetch_vendor.sh
#   ./backend/scripts/hunyuan3d/fetch_vendor.sh --skip-weights
#   ./backend/scripts/hunyuan3d/fetch_vendor.sh --check
#   ./backend/scripts/hunyuan3d/fetch_vendor.sh --force
#
# Env:
#   HF_ENDPOINT     default https://huggingface.co  (China: https://hf-mirror.com)
#   HF_TOKEN        Hugging Face token (required for gated Tencent repos)
#   HY3D_SKIP_MLX   1 = skip Hunyuan3D-MLX repo + mlx paint weights
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)"
TP="$ROOT/third_party"
HY3D2="$TP/Hunyuan3D-2"
MLX="$TP/Hunyuan3D-MLX"
MODELS="$TP/hy3d_models"
MLX_W="$TP/hy3d_mlx_weights"

SKIP_WEIGHTS=0
FORCE=0
CHECK=0
SKIP_MLX="${HY3D_SKIP_MLX:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-weights) SKIP_WEIGHTS=1; shift ;;
    --skip-mlx) SKIP_MLX=1; shift ;;
    --force) FORCE=1; shift ;;
    --check) CHECK=1; shift ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

has_weights() {
  local dest="$1"
  python3 - "$dest" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
if not p.is_dir():
    sys.exit(1)
min_bytes = 10 * 1024 * 1024
for f in p.rglob("*"):
    if f.is_file() and f.stat().st_size >= min_bytes:
        sys.exit(0)
sys.exit(1)
PY
}

vendor_missing() {
  local missing=()
  if [[ ! -d "$HY3D2/.git" && ! -d "$HY3D2/hy3dgen" ]]; then
    missing+=("source Hunyuan3D-2")
  fi
  if [[ "$SKIP_MLX" != "1" && ! -d "$MLX/.git" && ! -d "$MLX/python/paint" ]]; then
    missing+=("source Hunyuan3D-MLX")
  fi
  if [[ "$SKIP_WEIGHTS" != "1" ]]; then
    has_weights "$MODELS/tencent/Hunyuan3D-2" || missing+=("weights Hunyuan3D-2")
    has_weights "$MODELS/tencent/Hunyuan3D-2mini" || missing+=("weights Hunyuan3D-2mini")
    if [[ "$SKIP_MLX" != "1" ]]; then
      has_weights "$MLX_W/paint" || missing+=("weights mlx-paint-large")
    fi
  fi
  if [[ ${#missing[@]} -eq 0 ]]; then
    return 0
  fi
  printf '%s\n' "${missing[@]}"
  return 1
}

if [[ "$CHECK" == "1" ]]; then
  report="$(vendor_missing)" && {
    echo "OK  Hunyuan vendor complete under $TP"
    exit 0
  }
  echo "MISSING  Hunyuan vendor under $TP:"
  echo "$report" | sed 's/^/  - /'
  exit 1
fi

clone_repo() {
  local url="$1" dest="$2"
  if [[ -d "$dest/.git" && "$FORCE" != "1" ]]; then
    echo "OK  source $dest"
    git -C "$dest" fetch --depth 1 --quiet || true
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  if [[ -d "$dest" && ! -d "$dest/.git" ]]; then
    echo "WARN  $dest exists without .git — leaving in place"
    return 0
  fi
  if [[ -d "$dest/.git" && "$FORCE" == "1" ]]; then
    echo "Updating $dest …"
    git -C "$dest" fetch --depth 1
    git -C "$dest" reset --hard FETCH_HEAD || git -C "$dest" pull --ff-only
    return 0
  fi
  echo "Cloning $url → $dest"
  git clone --depth 1 "$url" "$dest"
}

ensure_hf() {
  if python3 -c "import huggingface_hub" >/dev/null 2>&1; then
    return 0
  fi
  echo "Installing huggingface_hub …"
  python3 -m pip install -q "huggingface_hub>=0.23"
}

hf_snapshot() {
  local repo="$1" dest="$2"
  if [[ "$FORCE" != "1" ]] && has_weights "$dest"; then
    echo "OK  weights $dest"
    return 0
  fi
  mkdir -p "$dest"
  echo "Downloading Hugging Face $repo → $dest"
  python3 - "$repo" "$dest" <<'PY'
import os, sys
from huggingface_hub import snapshot_download

repo, dest = sys.argv[1], sys.argv[2]
kwargs = {
    "repo_id": repo,
    "local_dir": dest,
    "max_workers": int(os.environ.get("HF_MAX_WORKERS", "4")),
}
token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
if token:
    kwargs["token"] = token
try:
    print(snapshot_download(**kwargs))
except Exception as exc:
    print(f"ERROR downloading {repo}: {exc}", file=sys.stderr)
    print(
        "If this repo is gated, accept the license on Hugging Face, then:\n"
        "  export HF_TOKEN=hf_...\n"
        "China mirror:\n"
        "  export HF_ENDPOINT=https://hf-mirror.com",
        file=sys.stderr,
    )
    sys.exit(1)
PY
}

mkdir -p "$TP"
echo "== Hunyuan vendor fetch =="
echo "root: $ROOT"
echo "This can use ~20–28 GB disk. Resume-safe if interrupted."

clone_repo "https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git" "$HY3D2"
if [[ "$SKIP_MLX" != "1" ]]; then
  clone_repo "https://github.com/ZimengXiong/Hunyuan3D-MLX.git" "$MLX"
fi

if [[ "$SKIP_WEIGHTS" == "1" ]]; then
  echo "Skipping weight download (--skip-weights)."
  exit 0
fi

ensure_hf
export HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"
echo "HF_ENDPOINT=$HF_ENDPOINT"

hf_snapshot "tencent/Hunyuan3D-2" "$MODELS/tencent/Hunyuan3D-2"
hf_snapshot "tencent/Hunyuan3D-2mini" "$MODELS/tencent/Hunyuan3D-2mini"

if [[ "$SKIP_MLX" != "1" ]]; then
  hf_snapshot "zimengxiong/hunyuan3d-mlx-paint-large" "$MLX_W/paint"
fi

# Compatibility link used by paint_*.py
PAINT_OFFICIAL="$MODELS/tencent/Hunyuan3D-2/hunyuan3d-paint-v2-0"
if [[ -d "$PAINT_OFFICIAL" ]]; then
  mkdir -p "$MLX_W/paint_rgb"
  ln -sfn "../../hy3d_models/tencent/Hunyuan3D-2/hunyuan3d-paint-v2-0" \
    "$MLX_W/paint_rgb/hunyuan3d-paint-v2-0"
  echo "OK  symlink paint_rgb → official hunyuan3d-paint-v2-0"
fi

echo "✓ Hunyuan source + weights are in $TP"
du -sh "$HY3D2" "$MLX" "$MODELS" "$MLX_W" 2>/dev/null || true

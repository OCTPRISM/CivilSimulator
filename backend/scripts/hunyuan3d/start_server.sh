#!/usr/bin/env bash
# Start Hunyuan3D-2mini-Turbo API.
# macOS 26+: PyTorch MPS is currently unavailable → default to CPU.
# Uses local cache under third_party/hy3d_models (offline).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENDOR="$ROOT/third_party/Hunyuan3D-2"
VENV="$ROOT/backend/.venv-hunyuan3d"
PORT="${HUNYUAN3D_PORT:-8080}"
DEVICE="${HUNYUAN3D_DEVICE:-cpu}"
MODELS="${HY3DGEN_MODELS:-$ROOT/third_party/hy3d_models}"

if [[ ! -d "$VENDOR/.git" && ! -d "$VENDOR/hy3dgen" ]]; then
  echo "Hunyuan3D-2 missing — fetching vendor then installing …"
  "$ROOT/backend/scripts/hunyuan3d/setup_mac.sh"
fi
if [[ ! -d "$VENV" ]]; then
  echo "Hunyuan venv missing — running setup_mac.sh …"
  "$ROOT/backend/scripts/hunyuan3d/setup_mac.sh"
fi
if [[ ! -d "$MODELS/tencent" ]]; then
  echo "Hunyuan weights missing — fetching …"
  "$ROOT/backend/scripts/hunyuan3d/fetch_vendor.sh"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$VENDOR"

export PYTORCH_ENABLE_MPS_FALLBACK=1
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export HY3DGEN_MODELS="$MODELS"

echo "Starting Hunyuan3D-2mini-Turbo on :$PORT (device=$DEVICE, offline cache=$MODELS) …"
exec python3 api_server.py \
  --host 0.0.0.0 \
  --port "$PORT" \
  --model_path tencent/Hunyuan3D-2mini \
  --tex_model_path tencent/Hunyuan3D-2 \
  --device "$DEVICE"

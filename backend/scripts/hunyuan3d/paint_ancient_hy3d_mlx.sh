#!/usr/bin/env bash
# Mac Apple Silicon: MLX-Swift Hunyuan Paint on existing hy3d shape GLBs.
# Usage:
#   ./backend/scripts/hunyuan3d/paint_ancient_hy3d_mlx.sh
#   ./backend/scripts/hunyuan3d/paint_ancient_hy3d_mlx.sh --only ancient_student
#   ./backend/scripts/hunyuan3d/paint_ancient_hy3d_mlx.sh --force --res 384 --tex 1024 --no-superres
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MLX_REPO="$ROOT/third_party/Hunyuan3D-MLX"
HY3D_BIN="${HY3D_BIN:-$MLX_REPO/.build/release/hy3d}"
WEIGHTS="${HY3D_PAINT_WEIGHTS:-$ROOT/third_party/hy3d_mlx_weights/paint}"
ROLES_ROOT="$ROOT/frontend/public/models/characters/roles"
RUNTIME="$ROOT/backend/data/runtime/generator/hy3d_npc"
READY="$ROOT/frontend/public/models/characters/hy3d_npc_ready.json"

ONLY=""
FORCE=0
RES=512
TEX=2048
STEPS=15
MODEL=rgb
NO_SUPERRES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) ONLY="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --res) RES="$2"; shift 2 ;;
    --tex) TEX="$2"; shift 2 ;;
    --steps) STEPS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --no-superres) NO_SUPERRES=1; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

ROLES=(
  ancient_student ancient_clerk ancient_guard ancient_archer
  ancient_trader ancient_farmer ancient_porter ancient_artisan
)

if [[ -n "$ONLY" ]]; then
  IFS=',' read -r -a ROLES <<< "$ONLY"
fi

if [[ ! -x "$HY3D_BIN" ]]; then
  echo "Building hy3d Swift CLI …"
  (cd "$MLX_REPO" && swift build -c release --product hy3d)
fi
if [[ ! -d "$WEIGHTS/hunyuan3d-paint-v2-0" ]]; then
  echo "Paint weights missing under $WEIGHTS"
  echo "Run: hf download zimengxiong/hunyuan3d-mlx-paint-large --local-dir $WEIGHTS"
  exit 1
fi

EXTRA=()
[[ "$NO_SUPERRES" == "1" ]] && EXTRA+=(--no-superres)

paint_one() {
  local rid="$1"
  local mesh="$ROLES_ROOT/$rid/hy3d/body.glb"
  local painted="$ROLES_ROOT/$rid/hy3d/body_painted.glb"
  local final="$ROLES_ROOT/$rid/hy3d/body.glb"
  local ref="$RUNTIME/$rid/ref.png"
  local shape_bak="$ROLES_ROOT/$rid/hy3d/body_shape.glb"

  if [[ ! -f "$mesh" ]]; then
    echo "SKIP $rid — missing shape mesh"; return 0
  fi
  if [[ ! -f "$ref" ]]; then
    echo "SKIP $rid — missing ref.png at $ref"; return 0
  fi
  # Already painted? (heuristic: textured glbs usually much larger + we keep marker)
  if [[ -f "$ROLES_ROOT/$rid/hy3d/painted.ok" && "$FORCE" != "1" ]]; then
    echo "SKIP $rid — already painted (use --force)"; return 0
  fi

  mkdir -p "$ROLES_ROOT/$rid/hy3d"
  if [[ ! -f "$shape_bak" ]]; then
    cp -n "$mesh" "$shape_bak" || cp "$mesh" "$shape_bak"
  fi

  echo "== paint $rid (res=$RES tex=$TEX steps=$STEPS model=$MODEL) =="
  "$HY3D_BIN" paint "$shape_bak" "$ref" -o "$painted" \
    --weights "$WEIGHTS" \
    --model "$MODEL" \
    --res "$RES" \
    --tex "$TEX" \
    --steps "$STEPS" \
    "${EXTRA[@]}"

  if [[ ! -f "$painted" ]]; then
    echo "FAIL $rid — no output"; return 1
  fi
  cp "$painted" "$final"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$ROLES_ROOT/$rid/hy3d/painted.ok"
  echo "  ok $final ($(wc -c < "$final") bytes)"
}

for rid in "${ROLES[@]}"; do
  paint_one "$rid"
done

echo "done. bump HY3D_NPC_CACHE in gltfCharacters.ts and refresh /dev/figures"

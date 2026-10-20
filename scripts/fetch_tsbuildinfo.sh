#!/usr/bin/env bash
# Place frontend/tsconfig.tsbuildinfo (gitignored incremental cache).
#
# Priority:
#   1. CIVSIM_TSBUILDINFO_URL  — download (curl/wget)
#   2. scripts/cache/tsconfig.tsbuildinfo — local cache copy
#   3. Generate via tsc --incremental
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
FRONT="$ROOT/frontend"
DEST="$FRONT/tsconfig.tsbuildinfo"
CACHE="$ROOT/scripts/cache/tsconfig.tsbuildinfo"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -f "$DEST" && "$FORCE" != "1" ]]; then
  echo "OK  $DEST"
  exit 0
fi

if [[ -z "${CIVSIM_TSBUILDINFO_URL:-}" && -f "$FRONT/.env.local" ]]; then
  CIVSIM_TSBUILDINFO_URL="$(
    grep -E '^CIVSIM_TSBUILDINFO_URL=' "$FRONT/.env.local" | tail -n 1 | cut -d= -f2- || true
  )"
fi

if [[ -n "${CIVSIM_TSBUILDINFO_URL:-}" ]]; then
  echo "Downloading tsbuildinfo from CIVSIM_TSBUILDINFO_URL …"
  mkdir -p "$FRONT"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 -o "$DEST" "$CIVSIM_TSBUILDINFO_URL"
  else
    wget -O "$DEST" "$CIVSIM_TSBUILDINFO_URL"
  fi
  echo "✓ wrote $DEST"
  exit 0
fi

if [[ -f "$CACHE" ]]; then
  echo "Copying $CACHE → $DEST"
  mkdir -p "$FRONT"
  cp "$CACHE" "$DEST"
  echo "✓ wrote $DEST"
  exit 0
fi

if [[ ! -d "$FRONT/node_modules" ]]; then
  echo "npm install (needed to generate tsbuildinfo) …"
  (cd "$FRONT" && npm install)
fi

echo "Generating $DEST via tsc --incremental …"
(cd "$FRONT" && npx tsc --incremental --pretty false --noEmit)
if [[ -f "$DEST" ]]; then
  echo "✓ generated $DEST"
  mkdir -p "$ROOT/scripts/cache"
  cp "$DEST" "$CACHE"
  echo "  cached a copy at $CACHE (optional seed for the next machine)"
else
  echo "WARN  tsc did not write $DEST"
  exit 1
fi

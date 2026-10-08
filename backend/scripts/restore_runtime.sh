#!/usr/bin/env bash
# Restore backend/data/runtime from a backup archive (v0.5 P-3).
# Stops nothing for you — shut down uvicorn/Next first.
# Usage:
#   ./backend/scripts/restore_runtime.sh /path/to/civsim-runtime-….tar.gz
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
RUNTIME="${ROOT}/backend/data/runtime"
ARCHIVE="${1:-}"

if [[ -z "${ARCHIVE}" || ! -f "${ARCHIVE}" ]]; then
  echo "Usage: $0 /path/to/civsim-runtime-YYYYMMDDThhmmssZ.tar.gz" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
tar -C "${TMP}" -xzf "${ARCHIVE}"

if [[ ! -d "${TMP}/runtime" ]]; then
  echo "ERROR: archive has no runtime/ top-level directory" >&2
  exit 1
fi

mkdir -p "$(dirname "${RUNTIME}")"
if [[ -d "${RUNTIME}" ]]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  mv "${RUNTIME}" "${RUNTIME}.pre-restore-${STAMP}"
  echo "Moved existing runtime → ${RUNTIME}.pre-restore-${STAMP}"
fi

mv "${TMP}/runtime" "${RUNTIME}"
echo "Restored ${RUNTIME} from ${ARCHIVE}"
echo "Next: start backend with the same AUTH_SECRET, then login and open 我的世界 / My Worlds."

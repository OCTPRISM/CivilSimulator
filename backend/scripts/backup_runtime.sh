#!/usr/bin/env bash
# Backup backend/data/runtime for Scheme B + auth SQLite (v0.5 P-3).
# Usage:
#   ./backend/scripts/backup_runtime.sh
#   ./backend/scripts/backup_runtime.sh /path/to/backups
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
RUNTIME="${ROOT}/backend/data/runtime"
OUT_DIR="${1:-${ROOT}/backend/data/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="${OUT_DIR}/civsim-runtime-${STAMP}.tar.gz"

if [[ ! -d "${RUNTIME}" ]]; then
  echo "ERROR: runtime dir missing: ${RUNTIME}" >&2
  echo "Start the backend once so SQLite / paths are created, then retry." >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

mkdir -p "${TMP}/runtime"
cp -a "${RUNTIME}/." "${TMP}/runtime/"

DB="${RUNTIME}/civsim.db"
if [[ -f "${DB}" ]] && command -v sqlite3 >/dev/null 2>&1; then
  # Consistent snapshot even if uvicorn holds the DB open.
  sqlite3 "${DB}" ".backup ${TMP}/runtime/civsim.db"
fi

tar -C "${TMP}" -czf "${ARCHIVE}" runtime
echo "Wrote ${ARCHIVE}"
ls -lh "${ARCHIVE}"

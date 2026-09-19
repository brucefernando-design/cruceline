#!/bin/bash
# Copia segura de la base de datos CruceLine (compatible con modo WAL).
# No toca ningún otro proyecto ni directorio de la VPS.
set -e

SRC="${CRUCELINE_DB:-/opt/cruceline/data/cruceline.db}"
DEST="${CRUCELINE_BACKUP_DIR:-/opt/cruceline/backups}"
mkdir -p "$DEST"
TARGET="$DEST/cruceline-$(date +%Y%m%d-%H%M).db"

if [ -f "$SRC" ]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$SRC" ".backup '$TARGET'"
  else
    cp "$SRC" "$TARGET"
    [ -f "$SRC-wal" ] && cp "$SRC-wal" "$TARGET-wal" || true
  fi
  # Mantener los últimos 15 respaldos
  ls -1t "$DEST"/cruceline-*.db 2>/dev/null | tail -n +16 | xargs -r rm -f --
fi

#!/bin/bash
# Copia segura de la base de datos CruceLine (compatible con modo WAL y Docker).
# No toca ningún otro proyecto ni directorio de la VPS.
set -e

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q '^cruceline$'; then
  TARGET="/backups/cruceline-$(date +%Y%m%d-%H%M).db"
  docker exec cruceline python -c "import sqlite3; con = sqlite3.connect('/data/cruceline.db'); bck = sqlite3.connect('$TARGET'); con.backup(bck); con.close(); bck.close()"
  docker exec cruceline bash -c 'ls -1t /backups/cruceline-*.db 2>/dev/null | tail -n +15 | xargs -r rm -f --'
  echo "Backup creado en volumen Docker: $TARGET"
else
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
    # Mantener los últimos 14 respaldos
    ls -1t "$DEST"/cruceline-*.db 2>/dev/null | tail -n +15 | xargs -r rm -f --
  fi
fi

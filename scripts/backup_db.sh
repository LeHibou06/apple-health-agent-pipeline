#!/usr/bin/env sh
set -eu
DB_PATH="${1:-./data/health.db}"
BACKUP_DIR="${2:-./backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/health-$STAMP.db"
python3 -c 'import sqlite3,sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close(); print(sys.argv[2])' "$DB_PATH" "$TARGET"

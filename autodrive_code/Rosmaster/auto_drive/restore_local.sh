#!/bin/bash
set -e

SRC_DIR="$HOME/.local/lib/python3.10/site-packages"
BACKUP_DIR="$HOME/.local/site-bak"

# 가장 최근 백업 찾기
LAST_BACKUP=$(ls -td $BACKUP_DIR/site-packages.* 2>/dev/null | head -n1)

if [ -z "$LAST_BACKUP" ]; then
    echo "❌ No backups found in $BACKUP_DIR"
    exit 1
fi

if [ -d "$SRC_DIR" ]; then
    echo "⚠️ $SRC_DIR already exists. Remove or rename it before restoring."
    exit 1
fi

mv "$LAST_BACKUP" "$SRC_DIR"
echo "✅ Restored $LAST_BACKUP back to $SRC_DIR"

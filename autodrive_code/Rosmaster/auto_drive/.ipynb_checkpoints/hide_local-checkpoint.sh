#!/bin/bash
set -e

BACKUP_DIR="$HOME/.local/site-bak"
SRC_DIR="$HOME/.local/lib/python3.10/site-packages"

mkdir -p "$BACKUP_DIR"

if [ -d "$SRC_DIR" ]; then
    TS=$(date +%Y%m%d_%H%M%S)
    mv "$SRC_DIR" "$BACKUP_DIR/site-packages.$TS"
    echo "✅ Moved $SRC_DIR to $BACKUP_DIR/site-packages.$TS"
else
    echo "ℹ️ Nothing to move, $SRC_DIR does not exist"
fi

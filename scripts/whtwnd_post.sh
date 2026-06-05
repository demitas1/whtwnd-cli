#!/bin/bash
CONFIG_FILE="$HOME/.config/whtwnd_cli/.bsky_config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "エラー: 設定ファイルが見つかりません: $CONFIG_FILE" >&2
    echo "  mkdir -p \"$(dirname "$CONFIG_FILE")\" && cp .bsky_config.json \"$CONFIG_FILE\"" >&2
    exit 1
fi
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "$PROJ_DIR/venv/bin/python" "$PROJ_DIR/whtwnd_post.py" --config "$CONFIG_FILE" "$@"

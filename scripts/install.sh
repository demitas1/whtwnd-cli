#!/bin/bash
set -e
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_DIR/whtwnd_post" << EOF
#!/bin/bash
CONFIG_FILE="\$HOME/.config/whtwnd_cli/.bsky_config.json"
if [ ! -f "\$CONFIG_FILE" ]; then
    echo "エラー: 設定ファイルが見つかりません: \$CONFIG_FILE" >&2
    echo "  mkdir -p ~/.config/whtwnd_cli && cp .bsky_config.json ~/.config/whtwnd_cli/" >&2
    exit 1
fi
exec "$PROJ_DIR/venv/bin/python" "$PROJ_DIR/whtwnd_post.py" --config "\$CONFIG_FILE" "\$@"
EOF

cat > "$INSTALL_DIR/bsky_post" << EOF
#!/bin/bash
CONFIG_FILE="\$HOME/.config/whtwnd_cli/.bsky_config.json"
if [ ! -f "\$CONFIG_FILE" ]; then
    echo "エラー: 設定ファイルが見つかりません: \$CONFIG_FILE" >&2
    echo "  mkdir -p ~/.config/whtwnd_cli && cp .bsky_config.json ~/.config/whtwnd_cli/" >&2
    exit 1
fi
exec "$PROJ_DIR/venv/bin/python" "$PROJ_DIR/bsky_post.py" --config "\$CONFIG_FILE" "\$@"
EOF

chmod +x "$INSTALL_DIR/whtwnd_post" "$INSTALL_DIR/bsky_post"

echo "インストール完了:"
echo "  $INSTALL_DIR/whtwnd_post  →  $PROJ_DIR/whtwnd_post.py"
echo "  $INSTALL_DIR/bsky_post    →  $PROJ_DIR/bsky_post.py"
echo ""
echo "設定ファイルの配置:"
echo "  mkdir -p ~/.config/whtwnd_cli"
echo "  cp .bsky_config.json ~/.config/whtwnd_cli/"

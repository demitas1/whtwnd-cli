# whtwnd-cli スキル

Claude Code のグローバルスキルとして利用するためのコマンドファイル群。

## スキル一覧

```
~/.claude/commands/
├── whtwnd-post.md           ← メイン投稿ワークフロー
└── translate-markdown.md    ← 翻訳スキル（whtwnd-post から呼び出される）
```

## 前提条件

- Claude Code インストール済み
- whtwnd-cli インストール済み（`~/.local/bin/whtwnd_post` が存在すること）

## インストール手順

### 1. 設定ファイルの配置

```bash
mkdir -p ~/.config/whtwnd_cli
cp .bsky_config.json ~/.config/whtwnd_cli/
```

`.bsky_config.json` の形式：
```json
{
  "handle": "yourname.bsky.social",
  "password": "アプリパスワード"
}
```

> アプリパスワードは Bluesky の設定 → プライバシーとセキュリティ → アプリパスワード で発行する。

動作確認：
```bash
whtwnd_post config show
```

### 2. スキルファイルのコピー

```bash
mkdir -p ~/.claude/commands
cp docs/skills/whtwnd-post.md ~/.claude/commands/
cp docs/skills/translate-markdown.md ~/.claude/commands/
```

### 3. 動作確認

Claude Code を起動し、`/` を入力してコマンド候補に `whtwnd-post` と `translate-markdown` が表示されれば完了。

## 使い方

```
/whtwnd-post <ファイルパス>      ← 投稿済み日本語記事の英語版を翻訳・投稿
/whtwnd-post <rkey または URL>

/translate-markdown <ファイルパス> <言語>   ← Markdown を単独で翻訳
```

## スキルの更新

`docs/skills/` を編集した後、再度コピーして反映する：

```bash
cp docs/skills/whtwnd-post.md ~/.claude/commands/
cp docs/skills/translate-markdown.md ~/.claude/commands/
```

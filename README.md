# whtwnd-cli

CLIからWhiteWind（whtwnd.com）にMarkdown記事を投稿するPythonツール。

[WhiteWind](https://whtwnd.com) はAT Protocol（Blueskyと同じプロトコル）上に構築されたMarkdownブログサービスです。記事データはBluesky PDS上に保存され、ユーザー自身が完全に所有します。

## 機能

- Markdownファイルをそのまま投稿
- ローカル画像の自動アップロード＆URL置換
- 公開設定の制御（全体公開 / URL限定 / 自分のみ / 下書き）
- タイトルの自動抽出（MarkdownのH1から）
- 投稿済み記事一覧の表示

## セットアップ

### 1. リポジトリのクローンと依存パッケージのインストール

```bash
git clone https://github.com/yourname/whtwnd-cli.git
cd whtwnd-cli
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 認証情報の設定

Bluesky の[アプリパスワード](https://bsky.app/settings/app-passwords)を発行してから、設定ファイルを作成します。

**ホームディレクトリに作成する場合（推奨）:**

```bash
cat > ~/.whtwnd_config.json << 'EOF'
{
  "handle": "yourname.bsky.social",
  "password": "xxxx-xxxx-xxxx-xxxx"
}
EOF
chmod 600 ~/.whtwnd_config.json
```

**プロジェクトディレクトリに作成する場合:**

```bash
cat > .whtwnd_config.json << 'EOF'
{
  "handle": "yourname.bsky.social",
  "password": "xxxx-xxxx-xxxx-xxxx"
}
EOF
```

> **注意:** メインパスワードではなく**アプリパスワード**を使用してください。プロジェクト内に置く場合は `.gitignore` により Git の追跡対象から除外されています。

カレントディレクトリの `.whtwnd_config.json` が優先されます。見つからない場合は `~/.whtwnd_config.json` を参照します。

## 使い方

以下のコマンドは `venv` 環境を有効化した状態、またはプロジェクトディレクトリで実行します。

### 記事を投稿

```bash
# タイトルをMarkdownのH1から自動取得して全体公開
python whtwnd_post.py post article.md

# タイトルを明示して投稿
python whtwnd_post.py post article.md --title "記事タイトル"

# 下書きとして保存（自分のみ閲覧可）
python whtwnd_post.py post article.md --draft

# URLを知っている人だけ閲覧可能
python whtwnd_post.py post article.md --visibility url

# 画像アップロードをスキップ
python whtwnd_post.py post article.md --no-images
```

**公開設定オプション (`--visibility`):**

| 値 | 説明 |
|---|---|
| `public` | 全体公開（デフォルト） |
| `url` | URLを知っている人のみ閲覧可 |
| `author` | 自分のみ閲覧可 |

`--draft` は `--visibility author` と同等です。

### 記事一覧を確認

```bash
python whtwnd_post.py list
```

出力例:

```
────────────────────────────────────────────────────────────
タイトル                           公開設定       作成日
────────────────────────────────────────────────────────────
私のブログ記事                      public     2026-02-19  (3mf6kmdywdz2q)
────────────────────────────────────────────────────────────
```

### Markdownでの画像の書き方

ローカル画像ファイルへの相対パスをそのまま書くだけでOKです。

```markdown
# 記事タイトル

本文テキスト...

![キャプション](./images/screenshot.png)
![図1](../assets/fig1.jpg)
```

投稿時にPDSへ自動アップロードされ、公開URLに置き換わります。
`https://` や `http://` 始まりのURLはそのまま使用されます。

## 仕組み

WhiteWindの記事はAT Protocolのレコードとして自分のPDSに保存されます。

```
1. Bluesky PDS に認証         com.atproto.server.createSession
2. ローカル画像をアップロード   com.atproto.repo.uploadBlob
3. 記事レコードを作成          com.atproto.repo.createRecord
                               (コレクション: com.whtwnd.blog.entry)
4. WhiteWind に通知            com.whtwnd.blog.notifyOfNewEntry
                               ※現在常に失敗するが、firehose 経由で自動検出される
```

## セルフホストPDS

`whtwnd_post.py` 冒頭の `PDS_HOST` 定数を変更してください。

```python
PDS_HOST = "https://your-pds.example.com"
```

## ライセンス

MIT

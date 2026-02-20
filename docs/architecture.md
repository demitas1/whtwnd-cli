# アーキテクチャ設計メモ

## プロジェクト概要

**whtwnd-cli** — CLIからWhiteWind（whtwnd.com）にMarkdown記事を投稿するPythonツール。

WhiteWindはBluesky/AT Protocolベースのブログサービス。記事はユーザー自身のPDS（Personal Data Server）に `com.whtwnd.blog.entry` コレクションのレコードとして保存される。

---

## 現在のファイル構成

```
whtwnd-cli/
  whtwnd_post.py        # WhiteWind 投稿スクリプト
  bsky_post.py          # Bluesky スキート投稿スクリプト
  requirements.txt      # 依存パッケージ（requests のみ）
  README.md             # ユーザー向けドキュメント
  CLAUDE.md             # Claude Code 向け指示書
  .gitignore
  docs/
    architecture.md     # このファイル
  examples/             # サンプルMarkdown（未作成）
  tests/                # テスト（未作成）
  venv/                 # Python 仮想環境
```

---

## 現在の実装（whtwnd_post.py）

### 処理フロー

```
CLIコマンド
    │
    ├─ post コマンド
    │     1. 設定ファイル読み込み（load_config）
    │     2. ATProto 認証（create_session）
    │     3. Markdown 読み込み・H1タイトル抽出
    │     4. ローカル画像を検出 → PDS に uploadBlob → URL 置換
    │        （process_markdown_images）
    │     5. com.whtwnd.blog.entry レコード作成（post_entry）
    │     6. WhiteWind AppView に通知（notify_whitewind）
    │
    └─ list コマンド
          1. 設定ファイル読み込み
          2. ATProto 認証
          3. com.atproto.repo.listRecords で一覧取得・表示
```

### 主要関数

| 関数 | 役割 |
|---|---|
| `load_config()` | カレントディレクトリ優先で設定ファイルを読み込む |
| `create_session()` | `com.atproto.server.createSession` でアクセストークン取得 |
| `upload_blob()` | `com.atproto.repo.uploadBlob` で画像をPDSにアップロード |
| `blob_to_public_url()` | blob CIDをPDS経由の公開URLに変換 |
| `process_markdown_images()` | Markdown内のローカル画像を検出・アップロード・URL置換 |
| `post_entry()` | `com.atproto.repo.createRecord` でレコード作成 |
| `notify_whitewind()` | `com.whtwnd.blog.notifyOfNewEntry` でAppViewに通知（失敗しても非致命的） |
| `list_entries()` | `com.atproto.repo.listRecords` で一覧取得・表示 |

### 設定ファイル

`~/.whtwnd_config.json` または実行ディレクトリの `.whtwnd_config.json`（カレントディレクトリ優先）:

```json
{
  "handle": "yourname.bsky.social",
  "password": "xxxx-xxxx-xxxx-xxxx"
}
```

パスワードはBlueskyの**アプリパスワード**を使用する（メインパスワードは不可）。

### 依存ライブラリ

- `requests` のみ（標準ライブラリ以外）

---

## 動作確認済みの挙動

### whtwnd_post.py（2026-02-19）

| 機能 | 状態 | 備考 |
|---|---|---|
| 認証 | ✅ 正常 | `bsky.social` PDS |
| 記事投稿 | ✅ 正常 | 公開設定・タイトル自動抽出も動作 |
| 記事一覧 | ✅ 正常 | |
| ローカル画像アップロード | ✅ 実装済み（未テスト） | |
| WhiteWind 通知 | ⚠️ 常に失敗 | WhiteWind 側の CloudFront が POST を拒否している。WhiteWind がリレーの firehose 経由で自動検出するため実害なし |

### bsky_post.py（2026-02-20）

| 機能 | 状態 | 備考 |
|---|---|---|
| テキスト投稿 | ✅ 正常 | 引数・ファイル・stdin の3通り |
| ハッシュタグ facet | ✅ 正常 | バイト位置の計算も正確 |
| URL facet | ✅ 実装済み | |
| @メンション facet | ✅ 実装済み | DID 解決つき（存在しないハンドルはスキップ） |
| 画像添付 | ✅ 実装済み（未テスト） | 最大4枚 |
| 言語タグ（--lang） | ✅ 実装済み | |

---

## 既知の問題・制限事項

### WhiteWind 通知の失敗

`com.whtwnd.blog.notifyOfNewEntry` エンドポイントは WhiteWind の CloudFront ディストリビューションが POST リクエストを拒否するため常に失敗する。WhiteWind は Bluesky リレーの firehose を監視して自動的に新規エントリを検出するため、実際の運用上の問題はない。公開後は数分以内に WhiteWind 上に反映される。

### アクセストークンの有効期限

`accessJwt` の有効期限は約2時間。現在の実装は単発実行を前提としているため問題ないが、長時間のバッチ処理を追加する場合はリフレッシュ処理が必要。

### エラーハンドリングの粗さ

現状 `sys.exit(1)` で一律終了。HTTPステータスコード別のメッセージや、ネットワークエラー時のリトライ処理は未実装。

---

## 今後の実装予定

### Priority 1: 基本的な信頼性

#### 1-1. エラーハンドリングの強化
- ネットワークエラー（タイムアウト等）のリトライ処理
- HTTPステータスコード別の明確なエラーメッセージ
  - 401: アプリパスワードが誤り
  - 429: レート制限 → バックオフして再試行
  - 5xx: サーバーエラー
- `uploadBlob` 失敗時のロールバック設計
- 設定ファイルが壊れている場合の検出と案内

#### 1-2. 記事の更新（put）

```
python whtwnd_post.py update <rkey_or_url> article.md
python whtwnd_post.py update --title "既存タイトル" article.md
```

- `com.atproto.repo.putRecord` を使用（rkey指定が必要）
- `--title` 指定時は `com.whtwnd.blog.getEntryMetadataByName` でAT URIを取得してrkeyを取り出す

#### 1-3. 記事の削除

```
python whtwnd_post.py delete <rkey_or_url>
python whtwnd_post.py delete --title "記事タイトル"
```

- `com.atproto.repo.deleteRecord` を使用
- 削除前に確認プロンプト（`--yes` / `-y` フラグで省略可）

---

### Priority 2: ユーザビリティ

#### 2-1. フロントマターサポート

```markdown
---
title: 記事タイトル
visibility: public
draft: false
---
```

- `python-frontmatter` パッケージを使用
- CLIオプションはフロントマターより優先

#### 2-2. 設定コマンド

```
python whtwnd_post.py config --handle yourname.bsky.social --password xxxx
python whtwnd_post.py config --show
```

対話的に `~/.whtwnd_config.json` を作成・更新できるようにする。

#### 2-3. プレビュー機能

```
python whtwnd_post.py preview article.md
```

投稿せずにタイトル・文字数・画像数・ローカル画像パスの存在確認を表示する。

#### 2-4. list コマンドの強化

- `--format json` オプションでJSON出力
- AT URIとWhiteWind URLを表示
- カーソルページネーション対応（50件以上）

---

### Priority 3: 発展機能

#### 3-1. パッケージ化

`pyproject.toml` を作成してCLIツールとして `pip install` できるようにする。

ディレクトリ構成（予定）:

```
whtwnd-cli/
  src/
    whtwnd_cli/
      __init__.py
      main.py       # argparse、サブコマンドのエントリーポイント
      auth.py       # セッション管理
      upload.py     # blob アップロード
      markdown.py   # Markdown処理、画像置換
      api.py        # AT Protocol / WhiteWind API呼び出し
      config.py     # 設定ファイル管理
  tests/
  pyproject.toml
  requirements.txt
```

#### 3-2. テスト

- `tests/` ディレクトリにユニットテストを追加
- フレームワーク: `pytest`
- HTTP呼び出しは `unittest.mock.patch` でモック化
- 実際のAPIを叩くテストは `tests/integration/` に分離し `pytest -m "not integration"` でスキップ可能にする

---

## AT Protocol / WhiteWind APIリファレンス

### 使用エンドポイント一覧

| エンドポイント | メソッド | 用途 |
|---|---|---|
| `com.atproto.server.createSession` | POST | 認証・アクセストークン取得 |
| `com.atproto.repo.uploadBlob` | POST | 画像アップロード |
| `com.atproto.repo.createRecord` | POST | レコード（記事）作成 |
| `com.atproto.repo.putRecord` | POST | レコード（記事）更新（未実装） |
| `com.atproto.repo.deleteRecord` | POST | レコード（記事）削除（未実装） |
| `com.atproto.repo.listRecords` | GET | レコード一覧取得 |
| `com.whtwnd.blog.getEntryMetadataByName` | GET | タイトルからAT URI取得（未実装） |
| `com.whtwnd.blog.notifyOfNewEntry` | POST | AppViewへの通知（常に失敗・無害） |

### PDS ホスト

デフォルト: `https://bsky.social`
セルフホストPDSの場合は `whtwnd_post.py` の `PDS_HOST` 定数を変更する。

### com.whtwnd.blog.entry レコードスキーマ

```json
{
  "$type": "com.whtwnd.blog.entry",
  "content": "string (必須, 最大100000文字)",
  "title": "string (省略可, 最大1000文字)",
  "createdAt": "ISO 8601 datetime",
  "visibility": "public | url | author",
  "theme": "github-light",
  "blobs": [
    { "blobref": "<uploadBlobのレスポンス>", "name": "filename.png" }
  ]
}
```

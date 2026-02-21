# アーキテクチャ設計メモ

## プロジェクト概要

**whtwnd-cli** — CLIからWhiteWind（whtwnd.com）にMarkdown記事を投稿し、Blueskyにスキートを投稿するPythonツール群。

WhiteWindはBluesky/AT Protocolベースのブログサービス。記事はユーザー自身のPDS（Personal Data Server）に `com.whtwnd.blog.entry` コレクションのレコードとして保存される。

---

## 現在のファイル構成

```
whtwnd-cli/
  atproto.py            # ★ 共通モジュール: AT Protocol 基本操作
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

## モジュール設計

### 依存関係

```
whtwnd_post.py ──┐
                 ├──→ atproto.py  （共通: 認証・設定・blob操作）
bsky_post.py  ──┘
```

### atproto.py（共通モジュール）

両スクリプトで重複していたコードを集約する。

| 要素 | 内容 |
|---|---|
| `PDS_HOST` | `"https://bsky.social"`（定数） |
| `_LOCAL_CONFIG` | `Path(".bsky_config.json")`（カレントディレクトリ） |
| `_HOME_CONFIG` | `Path.home() / ".bsky_config.json"` |
| `load_config()` | 設定ファイルを読み込む（カレントディレクトリ優先） |
| `create_session()` | `com.atproto.server.createSession` で認証 |
| `upload_blob()` | `com.atproto.repo.uploadBlob` で画像アップロード |
| `blob_to_public_url()` | blob CIDをPDS経由の公開URLに変換 |
| `resolve_handle_to_did()` | ハンドルをDIDに解決 |

### whtwnd_post.py（WhiteWind 固有）

`atproto` をインポートして認証・blob操作を委譲する。

| 関数 | 内容 |
|---|---|
| `process_markdown_images()` | Markdown内ローカル画像を検出・アップロード・URL置換 |
| `post_entry()` | `com.atproto.repo.createRecord` で WhiteWind 記事を作成 |
| `notify_whitewind()` | AppViewに通知（失敗しても非致命的） |
| `entry_url()` | WhiteWind 記事URLを生成 |
| `list_entries()` | 記事一覧を取得・表示 |

### bsky_post.py（Bluesky 固有）

`atproto` をインポートして認証・blob操作・DID解決を委譲する。

| 関数 | 内容 |
|---|---|
| `detect_facets()` | URL・@メンション・#ハッシュタグをバイト位置で検出 |
| `post_skeet()` | `com.atproto.repo.createRecord` でスキートを作成 |

---

## 設定ファイル

**ファイル名:** `.bsky_config.json`（旧: `.whtwnd_config.json`）

カレントディレクトリのファイルを優先し、なければホームディレクトリを参照する。

```json
{
  "handle": "yourname.bsky.social",
  "password": "xxxx-xxxx-xxxx-xxxx"
}
```

パスワードはBlueskyの**アプリパスワード**を使用する（メインパスワードは不可）。

`.gitignore` にも `.bsky_config.json` を追加する。

---

## 処理フロー

### whtwnd_post.py post コマンド

```
1. atproto.load_config()
2. atproto.create_session()
3. Markdown 読み込み・H1タイトル抽出
4. process_markdown_images()
     └─ atproto.upload_blob() × 画像数
5. post_entry()
6. notify_whitewind()
```

### bsky_post.py post コマンド

```
1. atproto.load_config()
2. atproto.create_session()
3. テキスト取得（引数 / ファイル / stdin）
4. detect_facets()
     └─ atproto.resolve_handle_to_did() × @メンション数
5. (画像があれば) atproto.upload_blob() × 枚数
6. post_skeet()
```

---

## 動作確認済みの挙動

### whtwnd_post.py（2026-02-19）

| 機能 | 状態 | 備考 |
|---|---|---|
| 認証 | ✅ 正常 | `bsky.social` PDS |
| 記事投稿 | ✅ 正常 | 公開設定・タイトル自動抽出も動作 |
| 記事一覧 | ✅ 正常 | |
| ローカル画像アップロード | ✅ 実装済み（未テスト） | |
| WhiteWind 通知 | ⚠️ 常に失敗 | WhiteWind 側の CloudFront が POST を拒否している。firehose 経由で自動検出されるため実害なし |

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

#### ~~1-1. エラーハンドリングの強化~~ ✅ 完了（2026-02-20）

- `atproto.api_request()` にリトライロジックを実装
  - Timeout / ConnectionError: エクスポネンシャルバックオフで最大3回リトライ
  - 429 レート制限: `Retry-After` ヘッダーを尊重してリトライ
  - 5xx サーバーエラー: バックオフでリトライ
- HTTPステータスコード別の明確なエラーメッセージ（401・400・413 等）
- 設定ファイルの JSON 形式不正を検出して案内（`json.JSONDecodeError`）
- `upload_blob` 失敗時に孤立 blob は PDS の GC で自動削除される旨を表示
- `post_entry` が RuntimeError を送出する設計に変更し、`cmd_post` で blob 孤立警告を表示

#### ~~1-2. 記事の更新（put）~~ ✅ 完了（2026-02-20）

- `update` サブコマンドを実装（`com.atproto.repo.putRecord` を使用）
- rkey / AT URI の直接指定に対応
- `--title` 指定時は PDS の `listRecords` を全件検索してタイトルが一致する rkey を取得
  - WhiteWind の `getEntryMetadataByName` は CloudFront/Next.js に吸収されて 500 を返すため PDS 直接検索に変更
- `update_entry()` は失敗時に RuntimeError を送出し `cmd_update` でblobの孤立警告を表示

#### ~~1-3. 記事の削除~~ ✅ 完了（2026-02-20）

- `delete` サブコマンドを実装（`com.atproto.repo.deleteRecord` を使用）
- rkey / AT URI の直接指定と `--title` 指定に対応（`find_rkey_by_title` を共用）
- 削除前に確認プロンプトを表示し、`--yes` / `-y` フラグで省略可能

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

対話的に `.bsky_config.json` を作成・更新できるようにする。

#### 2-3. プレビュー機能

```
python whtwnd_post.py preview article.md
```

投稿せずにタイトル・文字数・画像数・ローカル画像パスの存在確認を表示する。

#### 2-4. list コマンドの強化

- `--format json` オプションでJSON出力
- AT URIとWhiteWind URLを表示
- カーソルページネーション対応（50件以上）

#### 2-5. Bluesky 動画アップロード対応

→ 詳細設計: [docs/new-features.md](new-features.md#priority-2-5-bluesky-動画アップロード対応)

- `bsky_post.py` に `--video` / `--alt` オプションを追加
- アップロードフロー: サービス認証トークン取得 → `video.bsky.app` へアップロード → ジョブポーリング → `app.bsky.embed.video` でスキート投稿
- `atproto.py` に `get_service_auth()` を追加
- ffprobe（システム依存）でアスペクト比を取得
- `--video` と `--image` は排他

---

### Priority 3: 発展機能

#### 3-1. パッケージ化

`pyproject.toml` を作成してCLIツールとして `pip install` できるようにする。

ディレクトリ構成（予定）:

```
whtwnd-cli/
  src/
    bsky_cli/
      __init__.py
      main_whtwnd.py    # whtwnd サブコマンドのエントリーポイント
      main_bsky.py      # bsky サブコマンドのエントリーポイント
      atproto.py        # 共通: 認証・設定・blob操作
      whtwnd.py         # WhiteWind 固有ロジック
      bsky.py           # Bluesky 固有ロジック
      markdown.py       # Markdown処理、画像置換
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
| `com.atproto.repo.createRecord` | POST | レコード作成（記事・スキート） |
| `com.atproto.repo.putRecord` | POST | レコード更新（未実装） |
| `com.atproto.repo.deleteRecord` | POST | レコード削除（未実装） |
| `com.atproto.repo.listRecords` | GET | レコード一覧取得 |
| `com.atproto.identity.resolveHandle` | GET | ハンドル→DID解決 |
| `com.whtwnd.blog.getEntryMetadataByName` | GET | タイトルからAT URI取得（未実装） |
| `com.whtwnd.blog.notifyOfNewEntry` | POST | AppViewへの通知（常に失敗・無害） |

### PDS ホスト

デフォルト: `https://bsky.social`
セルフホストPDSの場合は `atproto.py` の `PDS_HOST` 定数を変更する。

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

### app.bsky.feed.post レコードスキーマ

```json
{
  "$type": "app.bsky.feed.post",
  "text": "string (必須, 最大300 grapheme)",
  "createdAt": "ISO 8601 datetime",
  "langs": ["ja"],
  "facets": [
    {
      "index": { "byteStart": 0, "byteEnd": 10 },
      "features": [
        { "$type": "app.bsky.richtext.facet#link", "uri": "https://..." }
      ]
    }
  ],
  "embed": {
    "$type": "app.bsky.embed.images",
    "images": [
      { "image": "<blob>", "alt": "" }
    ]
  }
}
```

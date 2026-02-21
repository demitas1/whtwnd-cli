# 新機能設計メモ

## Priority 2-5: Bluesky 動画アップロード対応

`bsky_post.py` に `--video` オプションを追加し、動画つきスキートを投稿できるようにする。

---

### 制限・仕様（API調査結果）

| 項目 | 値 |
|---|---|
| 最大ファイルサイズ | **100 MB** |
| 最大動画時間 | **3分（180秒）** |
| 対応フォーマット | MP4, MOV, M4V, MPG, MPEG, WebM |
| 日次アップロード制限 | **25本/日・合計10 GB/日** |
| 動画と画像 | 同一投稿には**どちらか一方のみ**（排他） |
| アップロード先 | `https://video.bsky.app/xrpc/` （通常の `bsky.social` とは別サービス） |

---

### CLI インターフェース設計

```bash
# 動画付きスキート
python bsky_post.py post "動画を投稿しました" --video clip.mp4

# alt テキスト付き（アクセシビリティ）
python bsky_post.py post "動画です" --video clip.mp4 --alt "猫が走っている動画"

# 言語タグ指定
python bsky_post.py post "テスト" --video clip.mp4 --lang ja

# テキストのみの場合と同様に --file / stdin も使用可能
python bsky_post.py post --file message.txt --video clip.mp4
```

**制約:**
- `--video` と `--image` は排他。同時指定はエラー
- `--video` は1つのみ指定可能

---

### 依存関係

#### システム依存: ffprobe（ffmpegに同梱）

アスペクト比（`aspectRatio`）の取得に使用する。省略するとBluesky側でレイアウト崩れが起きる場合があるため、可能な限り取得する。

```bash
# Ubuntu / Debian
sudo apt install ffmpeg

# macOS (Homebrew)
brew install ffmpeg
```

**ffprobe が見つからない場合:** 警告を表示して `aspectRatio` なしで続行する（投稿は可能）。

コマンド例:
```bash
ffprobe -v error -select_streams v:0 \
        -show_entries stream=width,height \
        -of json clip.mp4
```

#### Python 依存

追加パッケージなし（`requests` のみ）。ffprobe は `subprocess` で呼び出す。

---

### アップロードフロー

```
1. ファイルバリデーション
   - 拡張子チェック（mp4/mov/m4v/mpg/mpeg/webm）
   - ファイルサイズチェック（100MB未満）

2. 日次制限確認
   GET https://video.bsky.app/xrpc/app.bsky.video.getUploadLimits
   Authorization: Bearer <accessJwt>
   → { "canUpload": true, "remainingDailyVideos": 25, "remainingDailyBytes": 10737418240 }
   canUpload=false の場合はエラー終了

3. サービス認証トークン取得
   POST https://bsky.social/xrpc/com.atproto.server.getServiceAuth
   Authorization: Bearer <accessJwt>
   { "aud": "did:web:video.bsky.app", "lxm": "com.atproto.repo.uploadBlob" }
   → { "token": "..." }

4. 動画アップロード
   POST https://video.bsky.app/xrpc/app.bsky.video.uploadVideo
     ?did=<ユーザーDID>&name=<ファイル名>
   Authorization: Bearer <サービストークン>
   Content-Type: video/mp4（実際のMIMEタイプ）
   Body: バイナリ動画データ
   → { "jobId": "...", "state": "JOB_STATE_CREATED" }

5. ジョブ完了待機（ポーリング）
   GET https://video.bsky.app/xrpc/app.bsky.video.getJobStatus?jobId=<jobId>
   ジョブ状態: JOB_STATE_CREATED → JOB_STATE_ENCODING → JOB_STATE_SCANNING → JOB_STATE_COMPLETED
   JOB_STATE_FAILED の場合はエラー終了
   完了まで 1〜2秒間隔でポーリング（タイムアウト: 5分）
   → { "jobId": ..., "state": "JOB_STATE_COMPLETED", "blob": { <blob オブジェクト> } }

6. アスペクト比取得（ffprobe）
   ffprobe で width/height を取得。失敗した場合は aspectRatio を省略

7. スキート投稿
   embed に app.bsky.embed.video を指定
```

---

### レコードスキーマ（投稿時）

```json
{
  "$type": "app.bsky.feed.post",
  "text": "動画を投稿しました",
  "createdAt": "2026-02-21T00:00:00.000Z",
  "embed": {
    "$type": "app.bsky.embed.video",
    "video": {
      "$type": "blob",
      "ref": { "$link": "bafk..." },
      "mimeType": "video/mp4",
      "size": 12345678
    },
    "aspectRatio": {
      "width": 1920,
      "height": 1080
    },
    "alt": "動画の説明テキスト"
  }
}
```

---

### 実装計画

#### atproto.py への追加

| 関数 | シグネチャ | 内容 |
|---|---|---|
| `get_service_auth()` | `(session, aud, lxm) -> str` | サービス認証トークンを取得して返す |

#### bsky_post.py への追加・変更

| 関数 | シグネチャ | 内容 |
|---|---|---|
| `get_video_dimensions()` | `(file_path) -> tuple[int,int] \| None` | ffprobe で動画の width/height を取得。失敗時は None |
| `check_upload_limits()` | `(session) -> dict` | 日次制限を確認。`canUpload=False` なら RuntimeError |
| `upload_video()` | `(session, file_path) -> dict` | フロー全体（バリデーション〜ジョブ完了待機）を実行し blob オブジェクトを返す |
| `post_skeet()` | video 引数を追加 | `video` が指定された場合 `app.bsky.embed.video` を使用する |
| `cmd_post()` | `--video` / `--alt` 引数を処理 | `upload_video()` を呼び出して blob を取得し `post_skeet()` に渡す |

#### argparse 変更

```
post サブコマンドに追加:
  --video FILE    動画ファイルのパス（--image と排他）
  --alt TEXT      動画の代替テキスト（アクセシビリティ用）
```

`--video` と `--image` は `add_mutually_exclusive_group()` で排他制御する。

#### エラーケース

| 状況 | メッセージ・挙動 |
|---|---|
| 非対応フォーマット | `「{拡張子}」は対応していません。対応形式: mp4, mov, m4v, mpg, mpeg, webm` |
| サイズ超過 | `ファイルサイズが100MBを超えています（{サイズ}MB）` |
| 日次制限超過 | `本日の動画アップロード上限に達しています（残り0本 / 0 GB）` |
| ジョブ失敗 | `動画処理に失敗しました: {error}` |
| ジョブタイムアウト | `動画処理がタイムアウトしました（5分）` |
| ffprobe 未インストール | `ffprobe が見つかりません。aspectRatio なしで続行します。` （警告のみ） |

---

### 変更対象ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `atproto.py` | 追加 | `get_service_auth()` |
| `bsky_post.py` | 追加・変更 | 動画関連関数、`post_skeet()` 拡張、argparse 更新 |
| `README.md` | 追加 | 動画投稿の使い方セクション |
| `requirements.txt` | 変更なし | Python 追加依存なし |
| `docs/architecture.md` | 更新 | 使用エンドポイント・bsky_post 関数一覧に追記 |

"""
atproto.py - AT Protocol 共通操作モジュール

whtwnd_post.py / bsky_post.py から共通で使用する。
- 設定ファイルの読み込み
- セッション認証
- blob（画像）アップロード
- ハンドル→DID解決
- HTTPリクエスト共通処理（リトライ・エラーハンドリング）
"""

import json
import mimetypes
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests が必要です: pip install requests")
    sys.exit(1)

PDS_HOST = "https://bsky.social"  # セルフホストPDSの場合はここを変更

# 設定ファイル: カレントディレクトリ優先、なければホーム
_LOCAL_CONFIG = Path(".bsky_config.json")
_HOME_CONFIG = Path.home() / ".bsky_config.json"


# ──────────────────────────────────────────────
# HTTP共通処理（リトライ）
# ──────────────────────────────────────────────

def api_request(method: str, url: str, *, max_retries: int = 3, **kwargs) -> requests.Response:
    """
    HTTPリクエストを実行する。
    以下の場合にエクスポネンシャルバックオフでリトライする:
      - ネットワークエラー（Timeout / ConnectionError）
      - 429 レート制限
      - 5xx サーバーエラー
    """
    for attempt in range(max_retries):
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                _backoff("タイムアウト", attempt, max_retries)
                continue
            print("エラー: 接続タイムアウトが続いています。ネットワーク環境を確認してください。")
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                _backoff("接続エラー", attempt, max_retries)
                continue
            print("エラー: サーバーに接続できません。ネットワーク環境を確認してください。")
            sys.exit(1)

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            if attempt < max_retries - 1:
                _backoff("レート制限", attempt, max_retries, wait)
                continue
            print("エラー: レート制限に達しました。しばらく時間をおいてから再試行してください。")
            sys.exit(1)

        if resp.status_code >= 500 and attempt < max_retries - 1:
            _backoff(f"サーバーエラー ({resp.status_code})", attempt, max_retries)
            continue

        return resp

    return resp  # max_retries=0 など到達しないケースの保険


def _backoff(reason: str, attempt: int, max_retries: int, wait: int | None = None):
    """リトライ待機のアナウンスとsleep"""
    if wait is None:
        wait = 2 ** attempt
    print(f"  {reason}: {wait}秒後にリトライします... ({attempt + 1}/{max_retries})")
    time.sleep(wait)


# ──────────────────────────────────────────────
# 設定読み込み
# ──────────────────────────────────────────────

def load_config() -> dict:
    """設定ファイルを読み込む。カレントディレクトリを優先し、なければホームを参照する"""
    config_path = _LOCAL_CONFIG if _LOCAL_CONFIG.exists() else _HOME_CONFIG
    if not config_path.exists():
        print("設定ファイルが見つかりません。")
        print("以下のいずれかに作成してください:")
        print(f"  {_LOCAL_CONFIG.resolve()}")
        print(f"  {_HOME_CONFIG}")
        print("内容:")
        print(json.dumps(
            {"handle": "yourname.bsky.social", "password": "your-app-password"},
            ensure_ascii=False, indent=2,
        ))
        sys.exit(1)
    try:
        with open(config_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"エラー: 設定ファイルのJSON形式が不正です: {config_path}")
        print(f"  詳細: {e}")
        print("以下の形式で修正してください:")
        print(json.dumps(
            {"handle": "yourname.bsky.social", "password": "your-app-password"},
            ensure_ascii=False, indent=2,
        ))
        sys.exit(1)


# ──────────────────────────────────────────────
# AT Protocol 認証
# ──────────────────────────────────────────────

def create_session(handle: str, password: str) -> dict:
    """Bluesky/ATProto セッションを作成してアクセストークンとDIDを返す"""
    resp = api_request(
        "POST",
        f"{PDS_HOST}/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=15,
    )
    if resp.status_code == 401:
        print("ログイン失敗: ハンドルまたはアプリパスワードが正しくありません")
        sys.exit(1)
    if resp.status_code == 400:
        print(f"ログイン失敗: リクエストが不正です ({resp.text})")
        sys.exit(1)
    if not resp.ok:
        print(f"ログイン失敗: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    print(f"✓ ログイン成功: {data['handle']} (DID: {data['did']})")
    return data


# ──────────────────────────────────────────────
# blob（画像）アップロード
# ──────────────────────────────────────────────

def upload_blob(session: dict, file_path: Path) -> dict:
    """ローカルファイルをPDSにアップロードして blob オブジェクトを返す"""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    with open(file_path, "rb") as f:
        data = f.read()

    resp = api_request(
        "POST",
        f"{PDS_HOST}/xrpc/com.atproto.repo.uploadBlob",
        headers={
            "Authorization": f"Bearer {session['accessJwt']}",
            "Content-Type": mime_type,
        },
        data=data,
        timeout=60,
    )
    if resp.status_code == 401:
        print(f"アップロード失敗 ({file_path.name}): 認証トークンが無効です。再ログインしてください。")
        sys.exit(1)
    if resp.status_code == 413:
        print(f"アップロード失敗 ({file_path.name}): ファイルサイズが大きすぎます。")
        sys.exit(1)
    if not resp.ok:
        print(f"アップロード失敗 ({file_path.name}): {resp.status_code} {resp.text}")
        print("  ※ アップロード済みのファイルはPDSのGCにより自動削除されます。")
        sys.exit(1)

    blob = resp.json()["blob"]
    cid = blob["ref"]["$link"]
    print(f"  ✓ アップロード完了: {file_path.name} → CID: {cid[:16]}…")
    return blob


def blob_to_public_url(did: str, cid: str) -> str:
    """blob CIDをPDS経由の公開URLに変換する"""
    return f"{PDS_HOST}/xrpc/com.atproto.sync.getBlob?did={did}&cid={cid}"


# ──────────────────────────────────────────────
# ハンドル解決
# ──────────────────────────────────────────────

def resolve_handle_to_did(handle: str) -> str | None:
    """ハンドルをDIDに解決する。失敗時はNoneを返す"""
    resp = api_request(
        "GET",
        f"{PDS_HOST}/xrpc/com.atproto.identity.resolveHandle",
        params={"handle": handle},
        timeout=10,
    )
    if resp.ok:
        return resp.json().get("did")
    return None

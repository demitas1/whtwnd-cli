#!/usr/bin/env python3
"""
whtwnd_post.py - CLIからWhiteWindにMarkdown記事を投稿するスクリプト

使い方:
  python whtwnd_post.py post article.md --title "記事タイトル"
  python whtwnd_post.py post article.md --title "タイトル" --visibility public
  python whtwnd_post.py post article.md --title "タイトル" --draft
  python whtwnd_post.py list   # 投稿済み記事一覧

設定 (.bsky_config.json または ~/.bsky_config.json):
  {
    "handle": "yourname.bsky.social",
    "password": "your-app-password"
  }

Markdownの画像について:
  ローカル画像ファイルのパスを ![alt](path/to/image.png) のように書くと
  自動的にPDSにアップロードして公開URLに置き換えます。
  例:
    ![スクリーンショット](./screenshot.png)
    ![図1](images/fig1.jpg)
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import frontmatter as fm
import atproto


# ──────────────────────────────────────────────
# frontmatter 解析
# ──────────────────────────────────────────────

def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """
    YAML frontmatter を解析して (metadata, body) を返す。
    frontmatter がない場合は (None, content) を返す。
    """
    post = fm.loads(content)
    if not post.metadata:
        return None, content
    return dict(post.metadata), post.content


_FRONTMATTER_EXAMPLE = """\
  ---
  title: 記事タイトル
  tags: [タグ1, タグ2]
  visibility: public
  ---"""


def _resolve_post_params(args, metadata: dict) -> tuple[str | None, str, bool]:
    """
    frontmatter と CLI オプションから (title, visibility, is_draft) を解決する。
    優先順: --draft CLI > --visibility CLI > frontmatter draft > frontmatter visibility > default
    """
    title = args.title or metadata.get("title")

    if args.draft:
        visibility, is_draft = "author", True
    elif args.visibility is not None:
        visibility, is_draft = args.visibility, False
    elif metadata.get("draft", False):
        visibility, is_draft = "author", True
    else:
        visibility = metadata.get("visibility", "public")
        is_draft = False

    return title, visibility, is_draft


# ──────────────────────────────────────────────
# Markdown 処理 (画像パスの置換)
# ──────────────────────────────────────────────

def process_markdown_images(content: str, md_dir: Path, session: dict) -> tuple[str, list]:
    """
    Markdown内のローカル画像参照を検出してアップロードし、
    公開URLに置き換えたcontent文字列とblobsリストを返す。

    対象: ![alt](./relative/path.png) 形式のローカルパス
    対象外: ![alt](https://...) 形式のリモートURL (そのまま)
    """
    blobs = []
    uploaded_cache = {}  # 同じファイルを重複アップロードしないキャッシュ

    pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    def replace_image(match):
        alt = match.group(1)
        path_str = match.group(2).strip()

        # リモートURLはそのまま
        if path_str.startswith(("http://", "https://", "data:")):
            return match.group(0)

        # ローカルパスを解決
        img_path = (md_dir / path_str).resolve()
        if not img_path.exists():
            print(f"  ⚠ 画像ファイルが見つかりません (スキップ): {img_path}")
            return match.group(0)

        path_key = str(img_path)
        if path_key in uploaded_cache:
            blob_obj, public_url = uploaded_cache[path_key]
        else:
            blob_obj = atproto.upload_blob(session, img_path)
            cid = blob_obj["ref"]["$link"]
            public_url = atproto.blob_to_public_url(session["did"], cid)
            uploaded_cache[path_key] = (blob_obj, public_url)
            blobs.append({"blobref": blob_obj, "name": img_path.name})

        return f"![{alt}]({public_url})"

    new_content = pattern.sub(replace_image, content)
    return new_content, blobs


# ──────────────────────────────────────────────
# WhiteWind記事投稿
# ──────────────────────────────────────────────

def post_entry(session: dict, title: str, content: str, blobs: list,
               visibility: str = "public", draft: bool = False) -> str:
    """
    com.whtwnd.blog.entry レコードを作成してAT URIを返す。
    失敗時は RuntimeError を送出する。
    """
    record = {
        "$type": "com.whtwnd.blog.entry",
        "content": content,
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "visibility": "author" if draft else visibility,
        "theme": "github-light",
    }
    if title:
        record["title"] = title
    if blobs:
        record["blobs"] = blobs

    resp = atproto.api_request(
        "POST",
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "record": record,
        },
        timeout=15,
    )
    if resp.status_code == 400:
        raise RuntimeError(f"レコード作成失敗: リクエストが不正です ({resp.text})")
    if resp.status_code == 401:
        raise RuntimeError("レコード作成失敗: 認証トークンが無効です。再ログインしてください。")
    if not resp.ok:
        raise RuntimeError(f"レコード作成失敗: {resp.status_code} {resp.text}")

    at_uri = resp.json()["uri"]
    print(f"✓ レコード作成成功: {at_uri}")
    return at_uri


def update_entry(session: dict, rkey: str, title: str, content: str, blobs: list,
                 visibility: str = "public", draft: bool = False) -> str:
    """
    com.whtwnd.blog.entry レコードを更新してAT URIを返す。
    失敗時は RuntimeError を送出する。
    """
    record = {
        "$type": "com.whtwnd.blog.entry",
        "content": content,
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "visibility": "author" if draft else visibility,
        "theme": "github-light",
    }
    if title:
        record["title"] = title
    if blobs:
        record["blobs"] = blobs

    resp = atproto.api_request(
        "POST",
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.putRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "rkey": rkey,
            "record": record,
        },
        timeout=15,
    )
    if resp.status_code == 400:
        raise RuntimeError(f"レコード更新失敗: リクエストが不正です ({resp.text})")
    if resp.status_code == 401:
        raise RuntimeError("レコード更新失敗: 認証トークンが無効です。再ログインしてください。")
    if not resp.ok:
        raise RuntimeError(f"レコード更新失敗: {resp.status_code} {resp.text}")

    at_uri = resp.json()["uri"]
    print(f"✓ レコード更新成功: {at_uri}")
    return at_uri


def notify_whitewind(session: dict, at_uri: str):
    """WhiteWind AppViewにインデックスを依頼する"""
    resp = atproto.api_request(
        "POST",
        "https://whtwnd.com/xrpc/com.whtwnd.blog.notifyOfNewEntry",
        headers={
            "Authorization": f"Bearer {session['accessJwt']}",
            "Content-Type": "application/json",
        },
        json={"entryUri": at_uri},
        timeout=15,
    )
    if resp.ok:
        print("✓ WhiteWind通知完了")
    else:
        # 通知失敗は致命的ではない。WhiteWindはリレーの firehose 経由で自動検出する
        print(f"  (WhiteWind通知: {resp.status_code} — 自動検出されるため問題ありません)")


def entry_url(handle: str, at_uri: str, title: str) -> str:
    """記事のWhiteWind URLを生成する"""
    rkey = at_uri.split("/")[-1]
    if title:
        safe_title = title.replace(" ", "%20")
        return f"https://whtwnd.com/{handle}/entries/{safe_title}"
    return f"https://whtwnd.com/{handle}/{rkey}"


# ──────────────────────────────────────────────
# 記事一覧
# ──────────────────────────────────────────────

def list_entries(session: dict):
    """投稿済み記事の一覧を表示する"""
    resp = atproto.api_request(
        "GET",
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.listRecords",
        params={
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "limit": 50,
        },
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        timeout=15,
    )
    if resp.status_code == 401:
        print("一覧取得失敗: 認証トークンが無効です。再ログインしてください。")
        sys.exit(1)
    if not resp.ok:
        print(f"一覧取得失敗: {resp.status_code} {resp.text}")
        sys.exit(1)

    records = resp.json().get("records", [])
    if not records:
        print("記事がありません。")
        return

    print(f"\n{'─'*60}")
    print(f"{'タイトル':<30} {'公開設定':<10} {'作成日'}")
    print(f"{'─'*60}")
    for r in records:
        v = r["value"]
        title = v.get("title", "(無題)")[:28]
        vis = v.get("visibility", "public")
        created = v.get("createdAt", "")[:10]
        rkey = r["uri"].split("/")[-1]
        print(f"{title:<30} {vis:<10} {created}  ({rkey})")
    print(f"{'─'*60}\n")


# ──────────────────────────────────────────────
# サブコマンド
# ──────────────────────────────────────────────

def find_rkey_by_title(session: dict, title: str) -> str:
    """
    PDS の listRecords を検索してタイトルに一致する記事の rkey を返す。
    カーソルを使って全件検索する。見つからない場合は RuntimeError を送出する。
    """
    cursor = None
    while True:
        params = {
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "limit": 100,
        }
        if cursor:
            params["cursor"] = cursor

        resp = atproto.api_request(
            "GET",
            f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.listRecords",
            params=params,
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            timeout=15,
        )
        if not resp.ok:
            raise RuntimeError(f"記事一覧の取得に失敗しました: {resp.status_code}")

        data = resp.json()
        for r in data.get("records", []):
            if r["value"].get("title") == title:
                return r["uri"].split("/")[-1]

        cursor = data.get("cursor")
        if not cursor:
            break

    raise RuntimeError(f"記事が見つかりません: タイトル「{title}」")


def _extract_rkey_from_whtwnd_url(url: str, session_handle: str) -> str:
    """
    https://whtwnd.com/{handle}/{rkey} 形式の URL から rkey を抽出する。
    handle が設定と一致しない場合、または URL 形式が不正な場合は RuntimeError を送出する。
    """
    prefix = "https://whtwnd.com/"
    path = url[len(prefix):]
    parts = path.split("/")

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise RuntimeError(
            f"WhiteWind URL の形式が不正です: {url}\n"
            f"  正しい形式: https://whtwnd.com/{{handle}}/{{rkey}}"
        )

    url_handle, rkey = parts

    if url_handle != session_handle:
        raise RuntimeError(
            f"URL のハンドル ({url_handle}) が設定のハンドル ({session_handle}) と一致しません。"
        )

    return rkey


def resolve_rkey(session: dict, target: str | None, title: str | None) -> str:
    """
    rkey を解決して返す。
    - target が "at://" 始まりの AT URI ならその末尾を使用
    - target が "https://whtwnd.com/" 始まりの URL ならハンドル検証の上 rkey を抽出
    - target が rkey 文字列ならそのまま使用
    - title 指定時は listRecords を全件検索してタイトルが一致する rkey を返す
    """
    if title:
        return find_rkey_by_title(session, title)
    if target:
        if target.startswith("at://"):
            return target.split("/")[-1]
        if target.startswith("https://whtwnd.com/"):
            return _extract_rkey_from_whtwnd_url(target, session["handle"])
        return target
    raise RuntimeError("rkey または --title のいずれかを指定してください")


def cmd_post(args):
    config = atproto.load_config()
    session = atproto.create_session(config["handle"], config["password"])

    md_file = Path(args.file)
    if not md_file.exists():
        print(f"ファイルが見つかりません: {md_file}")
        sys.exit(1)

    raw_content = md_file.read_text(encoding="utf-8")

    # frontmatter 解析
    if args.no_frontmatter:
        metadata, body = {}, raw_content
    else:
        metadata, body = parse_frontmatter(raw_content)
        if metadata is None:
            print("エラー: frontmatter が見つかりません。")
            print("  記事ファイルの先頭に frontmatter を追加してください:")
            print(_FRONTMATTER_EXAMPLE)
            print("  frontmatter なしで投稿するには --no-frontmatter を指定してください。")
            sys.exit(1)

    # タイトル・公開設定を解決
    title, visibility, is_draft = _resolve_post_params(args, metadata)
    if not title:
        h1_match = re.match(r"^#\s+(.+)", body.strip(), re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
            print(f"  タイトルをMarkdownのH1から取得: {title}")

    # 画像処理
    print("\n[画像のアップロード]")
    blobs: list = []
    if not args.no_images:
        content, blobs = process_markdown_images(body, md_file.parent, session)
        if not blobs:
            print("  (ローカル画像なし)")
    else:
        content = body
        print("  (--no-images: スキップ)")

    # 記事投稿
    print("\n[記事の投稿]")
    try:
        at_uri = post_entry(
            session,
            title=title or md_file.stem,
            content=content,
            blobs=blobs,
            visibility=visibility,
            draft=is_draft,
        )
    except RuntimeError as e:
        print(f"エラー: {e}")
        if blobs:
            print("  ⚠ 画像はアップロード済みですが、記事の作成に失敗しました。")
            print("    アップロード済みの画像はPDSのGCにより自動削除されます。")
        sys.exit(1)

    # WhiteWind通知
    notify_whitewind(session, at_uri)

    # 結果表示
    url = entry_url(config["handle"], at_uri, title or md_file.stem)
    status = "下書き" if is_draft else visibility
    print(f"\n{'='*50}")
    print(f"✅ 投稿完了!")
    print(f"   タイトル : {title or md_file.stem}")
    print(f"   公開設定 : {status}")
    print(f"   URL      : {url}")
    print(f"   AT URI   : {at_uri}")
    print(f"{'='*50}\n")


def cmd_update(args):
    config = atproto.load_config()
    session = atproto.create_session(config["handle"], config["password"])

    # rkey の解決
    try:
        rkey = resolve_rkey(session, args.target, args.title)
    except RuntimeError as e:
        print(f"エラー: {e}")
        sys.exit(1)
    print(f"  更新対象 rkey: {rkey}")

    md_file = Path(args.file)
    if not md_file.exists():
        print(f"ファイルが見つかりません: {md_file}")
        sys.exit(1)

    raw_content = md_file.read_text(encoding="utf-8")

    # frontmatter 解析
    if args.no_frontmatter:
        metadata, body = {}, raw_content
    else:
        metadata, body = parse_frontmatter(raw_content)
        if metadata is None:
            print("エラー: frontmatter が見つかりません。")
            print("  記事ファイルの先頭に frontmatter を追加してください:")
            print(_FRONTMATTER_EXAMPLE)
            print("  frontmatter なしで更新するには --no-frontmatter を指定してください。")
            sys.exit(1)

    # タイトル・公開設定を解決（--new-title > frontmatter title > H1 > ファイル名）
    _, visibility, is_draft = _resolve_post_params(args, metadata)
    new_title = args.new_title or metadata.get("title")
    if not new_title:
        h1_match = re.match(r"^#\s+(.+)", body.strip(), re.MULTILINE)
        if h1_match:
            new_title = h1_match.group(1).strip()
            print(f"  タイトルをMarkdownのH1から取得: {new_title}")

    # 画像処理
    print("\n[画像のアップロード]")
    blobs: list = []
    if not args.no_images:
        content, blobs = process_markdown_images(body, md_file.parent, session)
        if not blobs:
            print("  (ローカル画像なし)")
    else:
        content = body
        print("  (--no-images: スキップ)")

    # 記事更新
    print("\n[記事の更新]")
    try:
        at_uri = update_entry(
            session,
            rkey=rkey,
            title=new_title or md_file.stem,
            content=content,
            blobs=blobs,
            visibility=visibility,
            draft=is_draft,
        )
    except RuntimeError as e:
        print(f"エラー: {e}")
        if blobs:
            print("  ⚠ 画像はアップロード済みですが、記事の更新に失敗しました。")
            print("    アップロード済みの画像はPDSのGCにより自動削除されます。")
        sys.exit(1)

    # WhiteWind通知
    notify_whitewind(session, at_uri)

    # 結果表示
    url = entry_url(config["handle"], at_uri, new_title or md_file.stem)
    status = "下書き" if is_draft else visibility
    print(f"\n{'='*50}")
    print(f"✅ 更新完了!")
    print(f"   タイトル : {new_title or md_file.stem}")
    print(f"   公開設定 : {status}")
    print(f"   URL      : {url}")
    print(f"   AT URI   : {at_uri}")
    print(f"{'='*50}\n")


def fetch_entry_title(session: dict, rkey: str) -> str | None:
    """rkey でレコードを取得してタイトルを返す。取得できない場合は None を返す。"""
    resp = atproto.api_request(
        "GET",
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.getRecord",
        params={
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "rkey": rkey,
        },
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        timeout=15,
    )
    if resp.ok:
        return resp.json().get("value", {}).get("title")
    return None


def cmd_delete(args):
    config = atproto.load_config()
    session = atproto.create_session(config["handle"], config["password"])

    # rkey の解決
    try:
        rkey = resolve_rkey(session, args.target, args.title)
    except RuntimeError as e:
        print(f"エラー: {e}")
        sys.exit(1)

    # 削除前確認
    if not args.yes:
        title = fetch_entry_title(session, rkey)
        print(f"以下の記事を削除します:")
        if title:
            print(f"  タイトル: {title}")
        print(f"  rkey: {rkey}")
        print(f"  AT URI: at://{session['did']}/com.whtwnd.blog.entry/{rkey}")
        answer = input("削除してよいですか？ [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("削除をキャンセルしました。")
            sys.exit(0)

    resp = atproto.api_request(
        "POST",
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.deleteRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "rkey": rkey,
        },
        timeout=15,
    )
    if resp.status_code == 401:
        print("削除失敗: 認証トークンが無効です。再ログインしてください。")
        sys.exit(1)
    if not resp.ok:
        print(f"削除失敗: {resp.status_code} {resp.text}")
        sys.exit(1)

    print(f"✓ 削除完了: {rkey}")


def cmd_list(args):
    config = atproto.load_config()
    session = atproto.create_session(config["handle"], config["password"])
    list_entries(session)


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="WhiteWindにMarkdown記事をCLIから投稿するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本的な投稿
  python whtwnd_post.py post article.md --title "私のブログ記事"

  # タイトル省略 (Markdownの最初の # 見出しを使用)
  python whtwnd_post.py post article.md

  # 下書きとして保存
  python whtwnd_post.py post article.md --draft

  # URLを知っている人だけ閲覧可能
  python whtwnd_post.py post article.md --visibility url

  # 記事一覧
  python whtwnd_post.py list

設定ファイル (.bsky_config.json または ~/.bsky_config.json):
  {
    "handle": "yourname.bsky.social",
    "password": "アプリパスワード"
  }

  ※ Blueskyの設定 → プライバシーとセキュリティ → アプリパスワード で発行
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # post サブコマンド
    p_post = sub.add_parser("post", help="Markdownファイルを投稿")
    p_post.add_argument("file", help="Markdownファイルのパス")
    p_post.add_argument("--title", "-t", help="記事タイトル（frontmatter の title より優先）")
    p_post.add_argument(
        "--visibility", "-v",
        choices=["public", "url", "author"],
        default=None,
        help="公開設定: public=全体公開, url=URLのみ, author=自分のみ（frontmatter の visibility より優先）",
    )
    p_post.add_argument("--draft", "-d", action="store_true", help="下書きとして保存（frontmatter の設定より優先）")
    p_post.add_argument("--no-images", action="store_true", help="画像アップロードをスキップ")
    p_post.add_argument("--no-frontmatter", action="store_true",
                        help="frontmatter なしで投稿（CLI オプションのみ使用、後方互換モード）")
    p_post.set_defaults(func=cmd_post)

    # update サブコマンド
    p_update = sub.add_parser("update", help="既存記事を更新")
    p_update.add_argument("target", nargs="?", help="rkey、AT URI、または WhiteWind URL（--title 指定時は省略可）")
    p_update.add_argument("file", help="更新内容のMarkdownファイルのパス")
    p_update.add_argument("--title", "-t", dest="title", help="更新対象をタイトルで指定")
    p_update.add_argument("--new-title", dest="new_title", help="更新後のタイトル（frontmatter の title より優先）")
    p_update.add_argument(
        "--visibility", "-v",
        choices=["public", "url", "author"],
        default=None,
        help="公開設定（frontmatter の visibility より優先）",
    )
    p_update.add_argument("--draft", "-d", action="store_true", help="下書きとして保存（frontmatter の設定より優先）")
    p_update.add_argument("--no-images", action="store_true", help="画像アップロードをスキップ")
    p_update.add_argument("--no-frontmatter", action="store_true",
                          help="frontmatter なしで更新（CLI オプションのみ使用、後方互換モード）")
    p_update.set_defaults(func=cmd_update)

    # delete サブコマンド
    p_delete = sub.add_parser("delete", help="記事を削除")
    p_delete.add_argument("target", nargs="?", help="rkey、AT URI、または WhiteWind URL（--title 指定時は省略可）")
    p_delete.add_argument("--title", "-t", help="削除対象をタイトルで指定")
    p_delete.add_argument("--yes", "-y", action="store_true", help="確認プロンプトをスキップ")
    p_delete.set_defaults(func=cmd_delete)

    # list サブコマンド
    p_list = sub.add_parser("list", help="投稿済み記事の一覧を表示")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

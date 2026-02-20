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

import atproto

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
    """com.whtwnd.blog.entry レコードを作成してAT URIを返す"""
    import requests

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

    resp = requests.post(
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "record": record,
        },
        timeout=15,
    )
    if not resp.ok:
        print(f"レコード作成失敗: {resp.status_code} {resp.text}")
        sys.exit(1)

    at_uri = resp.json()["uri"]
    print(f"✓ レコード作成成功: {at_uri}")
    return at_uri


def notify_whitewind(session: dict, at_uri: str):
    """WhiteWind AppViewにインデックスを依頼する"""
    import requests

    resp = requests.post(
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
    import requests

    resp = requests.get(
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.listRecords",
        params={
            "repo": session["did"],
            "collection": "com.whtwnd.blog.entry",
            "limit": 50,
        },
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        timeout=15,
    )
    if not resp.ok:
        print(f"一覧取得失敗: {resp.status_code}")
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

def cmd_post(args):
    config = atproto.load_config()
    session = atproto.create_session(config["handle"], config["password"])

    md_file = Path(args.file)
    if not md_file.exists():
        print(f"ファイルが見つかりません: {md_file}")
        sys.exit(1)

    raw_content = md_file.read_text(encoding="utf-8")

    # タイトルが未指定の場合、Markdownの先頭H1から取得
    title = args.title
    if not title:
        h1_match = re.match(r"^#\s+(.+)", raw_content.strip(), re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
            print(f"  タイトルをMarkdownのH1から取得: {title}")

    # 画像処理
    print("\n[画像のアップロード]")
    if not args.no_images:
        content, blobs = process_markdown_images(raw_content, md_file.parent, session)
        if not blobs:
            print("  (ローカル画像なし)")
    else:
        content, blobs = raw_content, []
        print("  (--no-images: スキップ)")

    # 記事投稿
    print("\n[記事の投稿]")
    at_uri = post_entry(
        session,
        title=title or md_file.stem,
        content=content,
        blobs=blobs,
        visibility=args.visibility,
        draft=args.draft,
    )

    # WhiteWind通知
    notify_whitewind(session, at_uri)

    # 結果表示
    url = entry_url(config["handle"], at_uri, title or md_file.stem)
    status = "下書き" if args.draft else args.visibility
    print(f"\n{'='*50}")
    print(f"✅ 投稿完了!")
    print(f"   タイトル : {title or md_file.stem}")
    print(f"   公開設定 : {status}")
    print(f"   URL      : {url}")
    print(f"   AT URI   : {at_uri}")
    print(f"{'='*50}\n")


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
    p_post.add_argument("--title", "-t", help="記事タイトル (省略時はMarkdownのH1を使用)")
    p_post.add_argument(
        "--visibility", "-v",
        choices=["public", "url", "author"],
        default="public",
        help="公開設定: public=全体公開, url=URLのみ, author=自分のみ (default: public)",
    )
    p_post.add_argument("--draft", "-d", action="store_true", help="下書きとして保存 (visibility=author と同等)")
    p_post.add_argument("--no-images", action="store_true", help="画像アップロードをスキップ")
    p_post.set_defaults(func=cmd_post)

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

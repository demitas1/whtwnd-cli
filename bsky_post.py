#!/usr/bin/env python3
"""
bsky_post.py - CLIからBlueskyにスキートを投稿するスクリプト

使い方:
  python bsky_post.py post "テキスト内容"
  python bsky_post.py post "テキスト" --image photo.jpg
  python bsky_post.py post --file message.txt

設定 (.bsky_config.json または ~/.bsky_config.json):
  {
    "handle": "yourname.bsky.social",
    "password": "your-app-password"
  }

Bluesky の仕様:
  - 投稿上限: 300 grapheme（日本語も1文字=1grapheme）
  - 画像: 最大4枚（JPEG / PNG / WebP / GIF）
  - URL・@メンション・#ハッシュタグはリッチテキスト（facet）として自動認識
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import atproto

MAX_GRAPHEMES = 300  # Bluesky の投稿文字数上限


# ──────────────────────────────────────────────
# Facet 検出（リッチテキスト）
# ──────────────────────────────────────────────

def detect_facets(text: str) -> list:
    """
    テキスト内の URL・@メンション・#ハッシュタグを検出して facets を返す。

    Bluesky の facet はバイト位置（UTF-8）で指定する必要がある。
    """
    facets = []

    # URL: http:// または https:// から空白・句読点・括弧まで
    url_re = re.compile(
        r'https?://'
        r'[^\s\u3000\u3001\u3002\uff0c\uff0e\u300c-\u301f\uff08\uff09\uff3b\uff3d\u300a\u300b]+'
    )
    for m in url_re.finditer(text):
        byte_start = len(text[:m.start()].encode("UTF-8"))
        byte_end = len(text[:m.end()].encode("UTF-8"))
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group()}],
        })

    # @メンション: @handle.domain 形式
    mention_re = re.compile(
        r'(?<![a-zA-Z0-9])'
        r'@([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
        r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+)'
    )
    for m in mention_re.finditer(text):
        handle = m.group(1)
        did = atproto.resolve_handle_to_did(handle)
        if did is None:
            continue  # 解決できないハンドルはスキップ
        byte_start = len(text[:m.start()].encode("UTF-8"))
        byte_end = len(text[:m.end()].encode("UTF-8"))
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#mention", "did": did}],
        })

    # #ハッシュタグ: 先頭・空白の後の # から英数字・日本語の連続
    tag_re = re.compile(r'(?<!\w)#([\w\u3040-\u30ff\u4e00-\u9fff]+)')
    for m in tag_re.finditer(text):
        byte_start = len(text[:m.start()].encode("UTF-8"))
        byte_end = len(text[:m.end()].encode("UTF-8"))
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}],
        })

    return facets


# ──────────────────────────────────────────────
# スキート投稿
# ──────────────────────────────────────────────

def post_skeet(
    session: dict,
    text: str,
    images: list[Path] | None = None,
    langs: list[str] | None = None,
) -> str:
    """app.bsky.feed.post レコードを作成して AT URI を返す"""
    record: dict = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }

    # リッチテキスト（URL・メンション・タグ）
    facets = detect_facets(text)
    if facets:
        record["facets"] = facets

    # 言語タグ
    if langs:
        record["langs"] = langs

    # 画像埋め込み（最大4枚）
    if images:
        embed_images = []
        for img_path in images[:4]:
            blob = atproto.upload_blob(session, img_path)
            embed_images.append({
                "image": blob,
                "alt": "",  # alt テキストは空（指定する場合は --alt オプションを追加）
            })
        record["embed"] = {
            "$type": "app.bsky.embed.images",
            "images": embed_images,
        }

    resp = atproto.api_request(
        "POST",
        f"{atproto.PDS_HOST}/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        timeout=15,
    )
    if resp.status_code == 401:
        print("投稿失敗: 認証トークンが無効です。再ログインしてください。")
        sys.exit(1)
    if not resp.ok:
        print(f"投稿失敗: {resp.status_code} {resp.text}")
        sys.exit(1)

    return resp.json()["uri"]


# ──────────────────────────────────────────────
# サブコマンド
# ──────────────────────────────────────────────

def cmd_post(args):
    # テキスト取得: 引数 → ファイル → stdin の順
    if args.text:
        text = args.text
    elif args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"ファイルが見つかりません: {path}")
            sys.exit(1)
        text = path.read_text(encoding="utf-8").strip()
    else:
        print("投稿テキストを入力してください (Ctrl+D で確定):")
        text = sys.stdin.read().strip()

    if not text:
        print("テキストが空です。")
        sys.exit(1)

    # 文字数チェック（grapheme 単位の簡易計算）
    grapheme_count = len(text)
    if grapheme_count > MAX_GRAPHEMES:
        print(f"テキストが長すぎます: {grapheme_count}文字（上限 {MAX_GRAPHEMES}文字）")
        sys.exit(1)

    # 画像ファイルの検証
    images: list[Path] = []
    if args.image:
        if len(args.image) > 4:
            print(f"画像は最大4枚です（指定: {len(args.image)}枚）")
            sys.exit(1)
        for img_str in args.image:
            img_path = Path(img_str)
            if not img_path.exists():
                print(f"画像ファイルが見つかりません: {img_path}")
                sys.exit(1)
            images.append(img_path)

    langs = args.lang if args.lang else None

    config = atproto.load_config()
    session = atproto.create_session(config["handle"], config["password"])

    print("\n[スキートの投稿]")
    at_uri = post_skeet(session, text, images=images or None, langs=langs)

    rkey = at_uri.split("/")[-1]
    url = f"https://bsky.app/profile/{config['handle']}/post/{rkey}"

    print(f"\n{'='*50}")
    print(f"✅ 投稿完了!")
    print(f"   文字数 : {grapheme_count}文字")
    if images:
        print(f"   画像数 : {len(images)}枚")
    print(f"   URL    : {url}")
    print(f"   AT URI : {at_uri}")
    print(f"{'='*50}\n")


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="BlueskyにCLIからスキートを投稿するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # テキストを直接指定
  python bsky_post.py post "今日も良い天気です #bluesky"

  # ファイルから読み込み
  python bsky_post.py post --file message.txt

  # 画像付き（最大4枚）
  python bsky_post.py post "写真を投稿しました" --image photo.jpg

  # 言語タグを指定
  python bsky_post.py post "Hello!" --lang en

  # 複数画像・複数言語
  python bsky_post.py post "テスト" --image a.jpg --image b.jpg --lang ja --lang en

リッチテキスト（自動検出）:
  - URL (https://...) → クリック可能なリンク
  - @ハンドル.ドメイン  → メンションリンク
  - #ハッシュタグ       → タグリンク
        """,
    )
    sub = parser.add_subparsers(dest="command")

    p_post = sub.add_parser("post", help="スキートを投稿")
    p_post.add_argument("text", nargs="?", help="投稿テキスト（省略時は --file またはstdinから読み込む）")
    p_post.add_argument("--file", "-f", metavar="FILE", help="テキストファイルのパス")
    p_post.add_argument(
        "--image", "-i",
        action="append",
        metavar="FILE",
        help="添付画像のパス（最大4枚、複数回指定可）",
    )
    p_post.add_argument(
        "--lang", "-l",
        action="append",
        metavar="LANG",
        help="言語コード（例: ja, en）複数回指定可",
    )
    p_post.set_defaults(func=cmd_post)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

# whtwnd-post skill

WhiteWindに投稿済みの日本語記事を元に英語版を翻訳・投稿し、
両記事に言語リンクを追加する。

## 前提環境
- whtwnd-cli が ~/.local/bin/ にインストール済み

## 使用方法

```
whtwnd-post <ファイルパス>
whtwnd-post <rkey or URL>
```

---

## Step 0: 作業準備

### 0-1. handle取得

```bash
whtwnd_post config show
```

出力の `handle` 行から値を取得し `HANDLE` として記録する。

例:
```
  handle : demiplus.bsky.social
```
→ `HANDLE = demiplus.bsky.social`

### 0-2. 入力の種別判定

- **ファイルパス指定の場合**: そのファイルを `JA_FILE` とする → 0-4へ
- **rkey / URL指定の場合**: `JA_RKEY` を記録し → 0-3へ

### 0-3. rkey/URL指定時 — 元原稿ファイルを要求

```
日本語版の元原稿ファイルのパスを入力してください。
（Step 5で日本語版を更新するために必要です）
```

入力されたパスを `JA_FILE` とする。

### 0-4. 元原稿とrkey/URLの整合性チェック

**ファイルパス指定の場合:**
1. `JA_FILE` のfrontmatter または H1 から `JA_TITLE` を取得する
2. `whtwnd_post list` を実行し `JA_TITLE` に一致する記事を探す
3. 一致した場合: `JA_RKEY` を記録して Step 1 へ進む
4. 一致しない場合:

```
投稿済み記事にタイトル「<JA_TITLE>」が見つかりませんでした。

投稿一覧:
<listの出力>

rkey または WhiteWind URL を直接入力してください。
または「キャンセル」で中止できます。
```

入力された rkey/URL を `JA_RKEY` として記録して進む。

**rkey/URL指定の場合:**
1. `whtwnd_post list` を実行し `JA_RKEY` に一致する記事タイトルを取得 → `LIST_TITLE`
2. `JA_FILE` のfrontmatter または H1 から `JA_TITLE` を取得する
3. 比較する：
   - **一致 / 類似**: そのまま進む
   - **不一致**:

```
⚠️ タイトルの不一致を検出しました。

  投稿済み記事のタイトル : <LIST_TITLE>
  原稿ファイルのタイトル : <JA_TITLE>

原稿ファイルが正しいか確認してください。
続行する場合は「続行」、ファイルを変更する場合は新しいパスを入力してください。
```

---

## Step 1: 作業サマリーの確認

```
作業内容を確認してください。

  日本語版タイトル : <JA_TITLE>
  日本語版rkey    : <JA_RKEY>
  日本語版URL     : https://whtwnd.com/<HANDLE>/<JA_RKEY>
  元原稿ファイル   : <JA_FILE>

翻訳・投稿を開始するには「OK」を入力してください。
```

---

## Step 2: 英語版MDを生成

`translate-markdown` スキルを使用する。

- 入力: `JA_FILE`、ターゲット言語 `en`
- Step 1 で確認済みのため、スキル内の確認プロンプト（translate-markdown の Step 2）はスキップする
- 出力を `EN_FILE` として記録する
- 出力frontmatterの `visibility` を `author`、`draft` を `true` で上書きする
- `TRANSLATED_TITLE` を `EN_TITLE` として記録する

`translate-markdown` スキルの場所:
- `~/.claude/commands/translate-markdown.md` を参照する
- 見つからない場合はユーザーに場所を確認する

---

## Step 3: 英語版をdraftとして投稿

```bash
whtwnd_post post <EN_FILE>
```

投稿後の出力から `EN_RKEY` を取得して記録する。
- `EN_URL = https://whtwnd.com/<HANDLE>/<EN_RKEY>`

---

## Step 4: ユーザーレビュー

```
英語版をdraftとして投稿しました。

  日本語版      : https://whtwnd.com/<HANDLE>/<JA_RKEY>
  英語版(draft) : https://whtwnd.com/<HANDLE>/<EN_RKEY>

WhiteWindで英語版をご確認ください。
修正が必要な場合は指示してください。
問題なければ「OK」と入力してください。
```

修正指示があった場合:
- `EN_FILE` を修正する
- `whtwnd_post update <EN_RKEY> <EN_FILE>` で更新する
- 再度確認を求める

---

## Step 5: 言語リンクを両記事に追加してupdate

OKが出たら、両ファイルのH1直後（frontmatterの外）に言語リンクを挿入する。

**JA_FILE への追加:**
```markdown
# <JA_TITLE>

*[English](https://whtwnd.com/<HANDLE>/<EN_RKEY>)*

（元の本文）
```

**EN_FILE への追加:**
```markdown
# <EN_TITLE>

*[日本語](https://whtwnd.com/<HANDLE>/<JA_RKEY>)*

（翻訳本文）
```

両ファイルを保存後、updateを実行する：

```bash
whtwnd_post update <JA_RKEY> <JA_FILE>
whtwnd_post update <EN_RKEY> <EN_FILE>
```

完了後、最終確認を求める：

```
言語リンクを両記事に追加しました。

  日本語版      : https://whtwnd.com/<HANDLE>/<JA_RKEY>
  英語版(draft) : https://whtwnd.com/<HANDLE>/<EN_RKEY>

両記事をご確認ください。
英語版を公開してよければ「publish」と入力してください。
```

---

## Step 6: 英語版をpublicに変更

「publish」が入力されたら `EN_FILE` のfrontmatterを書き換える：

```yaml
---
title: "<EN_TITLE>"
lang: en
visibility: public
draft: false
---
```

```bash
whtwnd_post update <EN_RKEY> <EN_FILE>
```

```
英語版を公開しました。

  日本語版 : https://whtwnd.com/<HANDLE>/<JA_RKEY>
  英語版   : https://whtwnd.com/<HANDLE>/<EN_RKEY>
```

---

## 注意事項
- Step 1・Step 4・Step 6 の確認を省略しない
- `EN_FILE` は削除しない（update・再翻訳時に必要）
- タイトル不一致は必ずユーザーに確認を取る
- エラー時はメッセージを表示してユーザーに判断を仰ぐ

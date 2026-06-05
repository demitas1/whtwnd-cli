# translate-markdown skill

frontmatter付きMarkdownファイルを指定言語に翻訳し、新しいファイルとして保存する。

## 使用方法

```
translate-markdown <ファイルパス> <ターゲット言語>
```

**ターゲット言語の指定例:**
- `en` / `english` / `英語`
- `zh` / `chinese` / `中国語`
- `ko` / `korean` / `韓国語`
- `fr` / `french` / `フランス語`
- など自然言語での指定も可

---

## 処理手順

### Step 1: ファイルの読み込みと解析

1. 指定ファイルを読み込む
2. frontmatterとbodyを分離して解析する
3. 以下を記録する：
   - `SRC_TITLE`: frontmatterの `title` フィールド、なければH1
   - `SRC_LANG`: frontmatterの `lang` フィールド、なければ本文から推定して記録
   - `SRC_VISIBILITY`: frontmatterの `visibility`（なければ `public`）
   - `SRC_DRAFT`: frontmatterの `draft`（なければ `false`）
   - `TARGET_LANG`: 指定されたターゲット言語の正式名と言語コード

### Step 2: 翻訳方針の決定

以下をユーザーに提示して確認を求める：

```
翻訳内容を確認してください。

  入力ファイル     : <ファイルパス>
  原文タイトル     : <SRC_TITLE>
  推定ソース言語   : <SRC_LANG>
  翻訳先言語       : <TARGET_LANG>
  出力ファイル     : <出力ファイルパス（後述）>

続行するには「OK」、キャンセルは「キャンセル」を入力してください。
```

### Step 3: 翻訳実行

以下の方針で翻訳する：

**翻訳する対象:**
- frontmatterの `title` フィールド → `TRANSLATED_TITLE` として記録
- Markdownの本文テキスト
- 見出し（H1〜H6）
- 画像のaltテキスト（`![ここ](url)`）

**翻訳しない対象:**
- frontmatterの `title` 以外のフィールド（visibility, draft, tags等）
- コードブロック（``` ``` ``` で囲まれた部分）
- インラインコード（`` ` `` で囲まれた部分）
- URL（`https://...` 等）
- 画像パス・リンクのURL部分

**文体の方針:**
- 技術ブログとして自然な文体
- 専門用語は一般的な訳語を使用する
- コマンド名・固有名詞はそのまま維持する

### Step 4: 出力ファイルの生成

**出力ファイル名:**
```
<元ファイルのベース名>.<言語コード>.md
```
例: `my-post.md` → `my-post.en.md` / `my-post.zh.md`

**出力frontmatter:**
```yaml
---
title: "<TRANSLATED_TITLE>"
lang: "<言語コード>"
visibility: <SRC_VISIBILITYを引き継ぐ>
draft: <SRC_DRAFTを引き継ぐ>
---
```
※ その他のフィールド（tags等）も元のfrontmatterからそのまま引き継ぐ  
※ `title` に `:` `#` `[` `{` 等のYAML特殊文字が含まれる場合は必ずダブルクォートで囲む

元ファイルと同じディレクトリに保存する。

### Step 5: 完了報告

```
翻訳が完了しました。

  原文     : <入力ファイルパス>  （<SRC_TITLE>）
  翻訳版   : <出力ファイルパス>  （<TRANSLATED_TITLE>）
  言語     : <SRC_LANG> → <TARGET_LANG>
```

---

## エラーハンドリング

- ファイルが存在しない場合: エラーを表示して終了する
- frontmatterがない場合: H1をタイトルとして扱い、その旨を表示して続行する
- 同名の出力ファイルが既に存在する場合: 上書き確認を求める

```
⚠️ <出力ファイルパス> は既に存在します。
上書きしますか？ [y/N]
```

---

## 呼び出し例

```
# 単独使用
translate-markdown ~/blog/drafts/my-post.md en
translate-markdown ~/blog/drafts/my-post.md 中国語

# 他スキル・ワークフローからの呼び出し
# → JA_FILE と TARGET_LANG を渡し、EN_FILE と EN_TITLE を受け取る
```

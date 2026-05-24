import openai
from openai import OpenAI
import anthropic
import json
import re
import sys
import yaml
from pathlib import Path

SYSTEM_PROMPT = """
あなたはSNS投稿の校正アシスタントです。
与えられた下書きを、以下の方針で整えてください。

- 読みやすさを高める（句読点・改行・表記統一）
- 技術的正確さを保つ
- ハッシュタグを追加する

出力はJSON形式で、以下のスキーマに従ってください：
{
  "variants": [
    { "body": "本文" },
  ]
}
JSONのみを返し、前置きや説明は一切含めないでください。
""".strip()


def _die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def _load_secrets() -> dict:
    secrets_path = Path(__file__).parent / ".secrets"
    try:
        with open(secrets_path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        _die(f".secrets ファイルが見つかりません: {secrets_path}")
    except PermissionError:
        _die(f".secrets ファイルの読み取り権限がありません: {secrets_path}")
    except yaml.YAMLError as e:
        _die(f".secrets の YAML 構文エラー: {e}")
    if not isinstance(data, dict):
        _die(".secrets の内容が不正です（キーと値のマッピングが必要です）")
    return data


def _require_secret(secrets: dict, key: str) -> str:
    try:
        return secrets[key]
    except KeyError:
        _die(f".secrets に '{key}' が設定されていません")


def _parse_json(text: str) -> dict:
    # マークダウンのコードブロックを除去する
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"エラー: JSONのパースに失敗しました: {e}", file=sys.stderr)
        print(f"モデルの生レスポンス:\n{text}", file=sys.stderr)
        sys.exit(1)


def polish_post(draft: str, provider: str, model: str) -> dict:
    secrets = _load_secrets()

    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=_require_secret(secrets, "anthropic_api_key"))
        try:
            message = client.messages.create(
                model=model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": f"以下の下書きを整えてください：\n\n{draft}"}
                ],
            )
        except anthropic.AuthenticationError:
            _die("Anthropic の認証に失敗しました。APIキーを確認してください。")
        except anthropic.RateLimitError:
            _die("Anthropic のレート制限に達しました。しばらく待ってから再試行してください。")
        except anthropic.APIConnectionError as e:
            _die(f"Anthropic への接続に失敗しました: {e}")
        except anthropic.APIStatusError as e:
            _die(f"Anthropic API エラー (HTTP {e.status_code}): {e.message}")
        result = _parse_json(message.content[0].text)

    elif provider == "openai":
        client = OpenAI(api_key=_require_secret(secrets, "openai_api_key"))
        try:
            response = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"以下の下書きを整えてください：\n\n{draft}"}
                ]
            )
        except openai.AuthenticationError:
            _die("OpenAI の認証に失敗しました。APIキーを確認してください。")
        except openai.RateLimitError:
            _die("OpenAI のレート制限に達しました。しばらく待ってから再試行してください。")
        except openai.APIConnectionError as e:
            _die(f"OpenAI への接続に失敗しました: {e}")
        except openai.APIStatusError as e:
            _die(f"OpenAI API エラー (HTTP {e.status_code}): {e.message}")
        result = _parse_json(response.choices[0].message.content)

    else:
        _die(f"プロバイダー '{provider}' はサポートされていません。(anthropic / openai)")

    result["provider"] = provider
    result["model"] = model
    return result


def main():
    draft = """
    KAIRリポジトリにあるノイズ除去モデルの比較。順に原画、SCUNet(sigma=15), BSRGAN。
    GANはかなり良い結果が得られているように見えるが、アート画像ではなく自然画像のみによる
    学習のためか存在しない陰影が出ているようにも見える
    """.strip()

    secrets = _load_secrets()
    provider = _require_secret(secrets, "provider")
    model = _require_secret(secrets, "model")

    result = polish_post(draft, provider=provider, model=model)

    print(f"provider: {result['provider']}, model: {result['model']}")
    print()
    for variant in result["variants"]:
        print(variant["body"])
        print()


if __name__ == "__main__":
    main()

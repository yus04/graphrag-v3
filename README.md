# graphrag-v3

Python 3.12 + [graphrag](https://github.com/microsoft/graphrag) v3.0.6 を [uv](https://docs.astral.sh/uv/) で管理するプロジェクトです。

> ⚠️ GraphRAG は LLM リソースを大量に消費する可能性があります。まずチュートリアル用データセットで動作を確認し、大規模なインデックス作業の前に安価なモデルで試すことを強く推奨します。

## 要件

- [uv](https://docs.astral.sh/uv/) がインストールされていること
- Python 3.12（uv が自動管理）

## セットアップ

### 1. リポジトリのクローン／ディレクトリへ移動

```bash
cd graphrag-v3
```

### 2. 依存パッケージのインストール

```bash
uv sync
```

`uv sync` を実行すると `.venv` が作成され、`graphrag==3.0.6` を含むすべての依存パッケージがインストールされます。

## GraphRAG の初期化

```bash
uv run graphrag init
```

プロンプトに従い、使用するチャットモデルと埋め込みモデルを指定します。  
実行後、以下のファイル・ディレクトリが生成されます。

| パス | 説明 |
|------|------|
| `input/` | GraphRAG が処理するテキストファイルの置き場所 |
| `.env` | API キーなどの環境変数（`GRAPHRAG_API_KEY=<API_KEY>` を設定） |
| `settings.yaml` | パイプラインの設定ファイル |

## サンプルテキストの取得

```bash
curl https://www.gutenberg.org/cache/epub/24022/pg24022.txt -o ./input/book.txt
```

## 環境変数の設定

### OpenAI を使う場合

`.env` の `GRAPHRAG_API_KEY` に OpenAI の API キーを設定します。

```env
GRAPHRAG_API_KEY=<your-openai-api-key>
```

### Azure OpenAI を使う場合

`.env` に API キーを設定した上で、`settings.yaml` のモデル設定を編集します。

```yaml
type: chat
model_provider: azure
model: gpt-4.1
deployment_name: <AZURE_DEPLOYMENT_NAME>
api_base: https://<instance>.openai.azure.com
api_version: 2024-02-15-preview
```

### Azure マネージド ID を使う場合

`settings.yaml` の `auth_type` を変更し、`api_key` の行を削除します。

```yaml
auth_type: azure_managed_identity
```

その後、以下のコマンドでログインしてください。

```bash
az login
```

## インデックスの構築

```bash
uv run graphrag index
```

完了後、`./output/` に Parquet ファイル群が生成されます。

## クエリの実行

### グローバル検索（高レベルな質問）

```bash
uv run graphrag query "What are the top themes in this story?"
```

### ローカル検索（特定の登場人物など）

```bash
uv run graphrag query \
  "Who is Scrooge and what are his main relationships?" \
  --method local
```

## 参考リンク

- [GraphRAG ドキュメント](https://microsoft.github.io/graphrag/)
- [設定リファレンス](https://microsoft.github.io/graphrag/config/init/)
- [CLI リファレンス](https://microsoft.github.io/graphrag/cli/)
- [クエリエンジン](https://microsoft.github.io/graphrag/query/overview/)

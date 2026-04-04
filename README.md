# graphrag-v3

Python 3.12 + [graphrag](https://github.com/microsoft/graphrag) v3.0.6 を [uv](https://docs.astral.sh/uv/) で管理するプロジェクトです。  
GraphRAG のクエリ機能を [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) ツールとして公開します。  
**ローカル（stdio）と Azure App Service（HTTP）の両環境で動作します。**

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
model_provider: azure
auth_method: api_key
api_key: ${GRAPHRAG_API_KEY}
api_base: https://<instance>.openai.azure.com
```

### Azure マネージド ID を使う場合

`settings.yaml` の `auth_method` を変更し、`api_key` の行を削除します。

```yaml
auth_method: azure_managed_identity
```

その後、以下のコマンドでログインしてください。

```bash
az login
```

## インデックスの構築

```bash
uv run graphrag index --root .
```

完了後、`./output/` に Parquet ファイル群が生成されます。

### インデックスの更新（差分のみ）

新しいドキュメントを追加したあとは `standard-update` または `fast-update` で差分のみ更新できます。

```bash
uv run graphrag index --root . --method standard-update
```

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

## MCP サーバー

GraphRAG のクエリ機能を [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) ツールとして公開します。  
Claude Desktop・Cursor・VS Code などの MCP 対応クライアントや、HTTP 経由で呼び出せます。

### 公開されるツール

| ツール名 | 説明 |
|----------|------|
| `graphrag_global_search` | コミュニティサマリー全体を横断する広域検索（テーマ・傾向の質問に最適） |
| `graphrag_local_search` | エンティティ周辺コンテキストを使った局所検索（人物・組織の詳細に最適） |
| `graphrag_drift_search` | グローバル＋ローカルのハイブリッド DRIFT 検索 |
| `graphrag_basic_search` | テキストチャンクへのベクトル類似度検索（最も軽量） |

すべてのツールは `response_type` パラメーターで回答形式を指定できます（例: `"Multiple Paragraphs"`, `"List of 3-7 Points"` など）。

### サーバーの起動（stdio トランスポート）

ローカルの MCP クライアント（Claude Desktop / Cursor / VS Code）向け。

```bash
uv run graphrag-mcp
# または
uv run python main.py
```

プロジェクトのルートディレクトリを変更する場合:

```bash
GRAPHRAG_ROOT=/path/to/project uv run graphrag-mcp
```

### サーバーの起動（HTTP トランスポート / Azure App Service）

Azure App Service や任意の HTTP サーバーとして公開する場合は `MCP_TRANSPORT` 環境変数を設定します。

```bash
MCP_TRANSPORT=streamable-http uv run graphrag-mcp
# ポートを指定する場合
MCP_TRANSPORT=streamable-http PORT=8080 uv run graphrag-mcp
```

接続先エンドポイント: `http://localhost:8000/mcp`

### 環境変数（MCP サーバー）

| 環境変数 | デフォルト | 説明 |
|----------|-----------|------|
| `GRAPHRAG_ROOT` | `.`（カレントディレクトリ） | GraphRAG プロジェクトのルートパス |
| `MCP_TRANSPORT` | `stdio` | トランスポート種別: `stdio` または `streamable-http` |
| `PORT` | `8000` | HTTP モード時のリスンポート（Azure App Service は自動設定） |
| `MCP_PORT` | `8000` | `PORT` が未設定の場合に参照する代替ポート変数 |

### Claude Desktop への登録例（stdio）

`claude_desktop_config.json` に以下を追加します。

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "uv",
      "args": ["--directory", "/path/to/graphrag-v3", "run", "graphrag-mcp"],
      "env": {
        "GRAPHRAG_ROOT": "/path/to/graphrag-v3"
      }
    }
  }
}
```

### HTTP クライアントからの接続例

HTTP トランスポートで起動している場合、任意の MCP 対応 HTTP クライアントから接続できます。

```bash
# MCP Inspector で検証
npx @modelcontextprotocol/inspector
# → Inspector UI で http://localhost:8000/mcp へ接続
```

---

## Azure 環境での利用

### ストレージ・データベース・ベクトルストアの Azure 移行

`settings.yaml` には各セクションにローカルと Azure 向けの設定がコメントで記載されています。  
使用するサービスに応じてコメントを切り替えてください。

#### Azure Blob Storage（入出力・キャッシュ・レポート）

```yaml
input_storage:
  type: blob
  connection_string: ${AZURE_STORAGE_CONNECTION_STRING}
  container_name: graphrag-input
  # マネージド ID を使う場合は connection_string の代わりに account_url を指定
  # account_url: https://<storageaccount>.blob.core.windows.net
```

同様に `output_storage`、`reporting`、`cache.storage` も変更します。

#### Azure AI Search（ベクトルストア）

```yaml
vector_store:
  type: azure_ai_search
  url: https://<searchservice>.search.windows.net
  api_key: ${AZURE_SEARCH_API_KEY}   # マネージド ID 使用時は省略可
  # audience: https://search.azure.com  # マネージド ID 使用時に指定
```

#### CosmosDB（ベクトルストア）

```yaml
vector_store:
  type: cosmosdb
  url: https://<account>.documents.azure.com
  connection_string: ${COSMOSDB_CONNECTION_STRING}
  database_name: graphrag
```

### Azure App Service へのデプロイ

HTTP トランスポートを有効にした状態で Azure App Service にデプロイできます。

1. App Service の「アプリケーション設定」で以下の環境変数を設定します。

   | 名前 | 値 |
   |------|-----|
   | `MCP_TRANSPORT` | `streamable-http` |
   | `GRAPHRAG_ROOT` | `/home/site/wwwroot`（またはデータパス） |
   | `GRAPHRAG_API_KEY` | Azure OpenAI の API キー |
   | `GRAPHRAG_API_BASE` | Azure OpenAI エンドポイント |

2. App Service は自動的に `PORT` 環境変数を設定します。サーバーはこれを自動検出します。

3. スタートアップコマンドを設定します:

   ```bash
   uv run graphrag-mcp
   ```

---

## グラフデータベースの定期更新（GitHub Actions）

`.github/workflows/graphrag-index.yml` に GraphRAG CLI を使った自動インデックス作成ワークフローが含まれています。

### スケジュール

デフォルトでは **毎週日曜 UTC 02:00** に実行されます。  
`cron` 式を変更することでスケジュールをカスタマイズできます。

### 手動実行

GitHub Actions の UI から **「Run workflow」** をクリックして手動実行できます。  
インデックス方法（`standard` / `fast` / `standard-update` / `fast-update`）を選択できます。

### 必要な GitHub Secrets

リポジトリの **Settings → Secrets and variables → Actions** に以下を登録してください。

| Secret 名 | 説明 |
|-----------|------|
| `GRAPHRAG_API_KEY` | Azure OpenAI または OpenAI の API キー |
| `GRAPHRAG_API_BASE` | Azure OpenAI エンドポイント URL |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage 使用時（任意） |

### Azure OIDC フェデレーション認証（推奨）

API キーの代わりに OpenID Connect（OIDC）でマネージド ID 認証を使う場合は、  
ワークフローファイル内の `Azure Login (OIDC)` ステップのコメントを外し、  
`AZURE_CLIENT_ID`、`AZURE_TENANT_ID`、`AZURE_SUBSCRIPTION_ID` Secrets を設定してください。

---

## 開発・テスト

### 開発用依存パッケージのインストール

```bash
uv sync --group dev
```

### リンター（Ruff）の実行

```bash
uv run ruff check .
uv run ruff format --check .
```

### テストの実行

```bash
uv run pytest
```

### 自動フォーマット

```bash
uv run ruff format .
uv run ruff check --fix .
```

---

## 参考リンク

- [GraphRAG ドキュメント](https://microsoft.github.io/graphrag/)
- [GraphRAG CLI リファレンス](https://microsoft.github.io/graphrag/cli/)
- [設定リファレンス](https://microsoft.github.io/graphrag/config/yaml/)
- [クエリエンジン](https://microsoft.github.io/graphrag/query/overview/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Azure App Service ドキュメント](https://learn.microsoft.com/azure/app-service/)
- [Azure AI Search ドキュメント](https://learn.microsoft.com/azure/search/)

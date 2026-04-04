"""GraphRAG MCP Server

GraphRAG のクエリ機能を MCP ツールとして公開します。
stdio（ローカル）と Streamable HTTP（Azure App Service 等）の両トランスポートに対応しています。

利用可能なツール:
  - graphrag_global_search  : コミュニティサマリーを横断した広域検索
  - graphrag_local_search   : エンティティ中心の局所的な検索
  - graphrag_drift_search   : グローバル+ローカルのハイブリッド検索
  - graphrag_basic_search   : テキストチャンクへのベクトル類似度検索

起動方法（stdio）:
  uv run graphrag-mcp          # pyproject.toml のスクリプト経由
  python main.py               # 直接実行

起動方法（HTTP / Azure App Service）:
  MCP_TRANSPORT=streamable-http uv run graphrag-mcp
  MCP_TRANSPORT=streamable-http PORT=8000 python main.py

環境変数:
  GRAPHRAG_ROOT   GraphRAG プロジェクトのルートディレクトリ（デフォルト: カレントディレクトリ）
  MCP_TRANSPORT   トランスポート種別: stdio（デフォルト）または streamable-http
  PORT            HTTP モード時のリスンポート（デフォルト: 8000）。Azure App Service は自動設定
  MCP_PORT        PORT の代替環境変数（PORT が未設定の場合に参照）
"""

import os
from pathlib import Path

import graphrag.api as api
import pandas as pd

# --- 公開 API で提供されているシンボル ----------------------------------------
from graphrag.data_model import DataReader
from graphrag_storage import create_storage
from mcp.server.fastmcp import FastMCP

# --- 内部 API（v3.0.6 時点で公開 API が存在しない）--------------------------
# graphrag.config および graphrag_storage の内部パスはバージョン変更で移動する可能性あり
try:
    from graphrag.config.load_config import load_config
except ImportError as e:
    raise ImportError(
        "graphrag.config.load_config が見つかりません。"
        " graphrag のバージョンが変わり内部パスが移動した可能性があります。"
        f" (graphrag=={__import__('importlib.metadata', fromlist=['version']).version('graphrag')})"
    ) from e

try:
    from graphrag.config.models.graph_rag_config import GraphRagConfig
except ImportError as e:
    raise ImportError(
        "graphrag.config.models.graph_rag_config.GraphRagConfig が見つかりません。"
        " graphrag のバージョンが変わり内部パスが移動した可能性があります。"
    ) from e

try:
    from graphrag_storage.tables.table_provider_factory import create_table_provider
except ImportError as e:
    raise ImportError(
        "graphrag_storage.tables.table_provider_factory.create_table_provider が見つかりません。"
        " graphrag-storage のバージョンが変わり内部パスが移動した可能性があります。"
    ) from e

# ---------------------------------------------------------------------------
# サーバーとグローバル状態
# ---------------------------------------------------------------------------

mcp = FastMCP("graphrag")

_ROOT_DIR = Path(os.environ.get("GRAPHRAG_ROOT", "."))

_config: GraphRagConfig | None = None
_df_cache: dict[str, pd.DataFrame | None] = {}
_df_loaded: set[str] = set()

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _get_config() -> GraphRagConfig:
    """settings.yaml から設定を読み込む（初回のみ）。"""
    global _config
    if _config is None:
        _config = load_config(root_dir=_ROOT_DIR)
    return _config


async def _load_dataframes(
    required: list[str],
    optional: list[str] | None = None,
) -> None:
    """未ロードの Parquet ファイルを _df_cache に読み込む。"""
    to_fetch = [n for n in required if n not in _df_loaded]
    opt_to_fetch = [n for n in (optional or []) if n not in _df_loaded]

    if not to_fetch and not opt_to_fetch:
        return

    config = _get_config()
    storage = create_storage(config.output_storage)
    table_provider = create_table_provider(config.table_provider, storage=storage)
    reader = DataReader(table_provider)

    # DataReader のメソッドを明示的に呼び出し
    _READER_METHODS: dict[str, str] = {
        "entities": "entities",
        "communities": "communities",
        "community_reports": "community_reports",
        "text_units": "text_units",
        "relationships": "relationships",
        "covariates": "covariates",
    }

    async def _call_reader(r: DataReader, name: str) -> pd.DataFrame:
        method = _READER_METHODS.get(name)
        if method is None:
            raise ValueError(f"未定義のデータフレーム名: {name!r}")
        fn = getattr(r, method, None)
        if fn is None:
            raise AttributeError(
                f"DataReader に '{method}' メソッドが存在しません。"
                " graphrag のバージョンが変わった可能性があります。"
            )
        return await fn()

    for name in to_fetch:
        _df_cache[name] = await _call_reader(reader, name)
        _df_loaded.add(name)

    for name in opt_to_fetch:
        if await table_provider.has(name):
            _df_cache[name] = await _call_reader(reader, name)
        else:
            _df_cache[name] = None
        _df_loaded.add(name)


# ---------------------------------------------------------------------------
# MCP ツール
# ---------------------------------------------------------------------------


@mcp.tool()
async def graphrag_global_search(
    query: str,
    community_level: int | None = None,
    dynamic_community_selection: bool = False,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """コミュニティサマリーを横断してデータセット全体に関わる質問に答える（グローバル検索）。

    テーマや傾向など、データセット全体に関わる広域的な質問に適しています。

    Parameters
    ----------
    query:
        自然言語の質問文。
    community_level:
        検索するコミュニティ階層の上限（None で自動選択）。
    dynamic_community_selection:
        True にすると固定レベルではなく動的にコミュニティを選択する。
    response_type:
        回答形式。例: "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points", "Single Page", "Multi-Page Report"。
    """
    config = _get_config()
    await _load_dataframes(["entities", "communities", "community_reports"])

    response, _ = await api.global_search(
        config=config,
        entities=_df_cache["entities"],
        communities=_df_cache["communities"],
        community_reports=_df_cache["community_reports"],
        community_level=community_level,
        dynamic_community_selection=dynamic_community_selection,
        response_type=response_type,
        query=query,
    )
    return str(response)


@mcp.tool()
async def graphrag_local_search(
    query: str,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """エンティティ周辺のコンテキストを使って特定の質問に答える（ローカル検索）。

    特定の人物・組織・イベントなど、具体的な対象についての質問に適しています。

    Parameters
    ----------
    query:
        自然言語の質問文。
    community_level:
        コンテキストとして使うコミュニティ階層レベル。
    response_type:
        回答形式。例: "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points"。
    """
    config = _get_config()
    await _load_dataframes(
        required=["entities", "communities", "community_reports", "text_units", "relationships"],
        optional=["covariates"],
    )

    response, _ = await api.local_search(
        config=config,
        entities=_df_cache["entities"],
        communities=_df_cache["communities"],
        community_reports=_df_cache["community_reports"],
        text_units=_df_cache["text_units"],
        relationships=_df_cache["relationships"],
        covariates=_df_cache.get("covariates"),
        community_level=community_level,
        response_type=response_type,
        query=query,
    )
    return str(response)


@mcp.tool()
async def graphrag_drift_search(
    query: str,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """グローバル検索とローカル検索を組み合わせた DRIFT 検索で質問に答える。

    広域的なコンテキストとエンティティ固有の詳細を統合した包括的な回答が得られます。

    Parameters
    ----------
    query:
        自然言語の質問文。
    community_level:
        コンテキストとして使うコミュニティ階層レベル。
    response_type:
        回答形式。例: "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points"。
    """
    config = _get_config()
    await _load_dataframes(
        required=["entities", "communities", "community_reports", "text_units", "relationships"],
    )

    response, _ = await api.drift_search(
        config=config,
        entities=_df_cache["entities"],
        communities=_df_cache["communities"],
        community_reports=_df_cache["community_reports"],
        text_units=_df_cache["text_units"],
        relationships=_df_cache["relationships"],
        community_level=community_level,
        response_type=response_type,
        query=query,
    )
    return str(response)


@mcp.tool()
async def graphrag_basic_search(
    query: str,
    response_type: str = "Multiple Paragraphs",
) -> str:
    """テキストチャンクへのベクトル類似度検索で質問に答える（ベーシック検索）。

    グラフ探索なしで埋め込みベクトルによる関連チャンク取得のみを行う最もシンプルな検索です。

    Parameters
    ----------
    query:
        自然言語の質問文。
    response_type:
        回答形式。例: "Multiple Paragraphs", "Single Paragraph",
        "List of 3-7 Points"。
    """
    config = _get_config()
    await _load_dataframes(["text_units"])

    response, _ = await api.basic_search(
        config=config,
        text_units=_df_cache["text_units"],
        response_type=response_type,
        query=query,
    )
    return str(response)


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------


def main() -> None:
    """MCP サーバーを起動（stdio または HTTP トランスポート）。

    環境変数 MCP_TRANSPORT で起動モードを切り替えます。

    - MCP_TRANSPORT=stdio (デフォルト):
        標準入出力を使った MCP クライアント（Claude Desktop / Cursor 等）向け。
    - MCP_TRANSPORT=streamable-http:
        Azure App Service や任意の HTTP サーバーとして公開する場合に使用。
        PORT（または MCP_PORT）環境変数でリスンポートを指定します。
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()

    if transport == "streamable-http":
        port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", "8000")))
        # Azure App Service では 0.0.0.0 へのバインドが必要
        mcp.settings.host = "0.0.0.0"  # noqa: S104
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

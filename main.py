"""GraphRAG MCP Server

GraphRAG のクエリ機能を MCP ツールとして公開します（stdio トランスポート）。

利用可能なツール:
  - graphrag_global_search  : コミュニティサマリーを横断した広域検索
  - graphrag_local_search   : エンティティ中心の局所的な検索
  - graphrag_drift_search   : グローバル+ローカルのハイブリッド検索
  - graphrag_basic_search   : テキストチャンクへのベクトル類似度検索

起動方法:
  uv run graphrag-mcp          # pyproject.toml のスクリプト経由
  python main.py               # 直接実行
  GRAPHRAG_ROOT=/path/to/proj python main.py  # ルートディレクトリを指定

環境変数:
  GRAPHRAG_ROOT  GraphRAG プロジェクトのルートディレクトリ（デフォルト: カレントディレクトリ）
"""

import os
from pathlib import Path

import pandas as pd
from mcp.server.fastmcp import FastMCP

import graphrag.api as api
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.data_model.data_reader import DataReader
from graphrag_storage import create_storage
from graphrag_storage.tables.table_provider_factory import create_table_provider

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

    for name in to_fetch:
        _df_cache[name] = await getattr(reader, name)()
        _df_loaded.add(name)

    for name in opt_to_fetch:
        if await table_provider.has(name):
            _df_cache[name] = await getattr(reader, name)()
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
    """MCP サーバーを起動する（stdio トランスポート）。"""
    mcp.run()


if __name__ == "__main__":
    main()

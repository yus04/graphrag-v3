"""GraphRAG MCP サーバーの統合テスト

実際に stdio トランスポートで MCP サーバーをサブプロセス起動し、
MCP クライアントセッション経由でツールの動作を検証します。

前提条件:
  - output/ に GraphRAG インデックス（Parquet ファイル群）が存在すること
  - 環境変数 GRAPHRAG_API_KEY / GRAPHRAG_API_BASE が設定されていること

インデックスが存在しない環境ではテストをスキップします。
"""

import os
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# テスト対象ツール
EXPECTED_TOOLS = {
    "graphrag_global_search",
    "graphrag_local_search",
    "graphrag_drift_search",
    "graphrag_basic_search",
}

# インデックス存在確認に使うファイル
_INDEX_SENTINEL = Path(__file__).parent.parent / "output" / "entities.parquet"

# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def server_params() -> StdioServerParameters:
    """graphrag-mcp を stdio プロセスとして起動するパラメーター。"""
    return StdioServerParameters(
        command="uv",
        args=["run", "graphrag-mcp"],
        env={**os.environ},
    )


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def skip_if_no_index():
    """インデックスが存在しない場合はテストをスキップするマーカー。"""
    return pytest.mark.skipif(
        not _INDEX_SENTINEL.exists(),
        reason="output/entities.parquet が存在しません。先に graphrag index を実行してください。",
    )


# ---------------------------------------------------------------------------
# テスト: 接続・ツール一覧（インデックス不要）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize(server_params):
    """MCP セッションを確立して initialize が成功すること。"""
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            result = await session.initialize()
            assert result.serverInfo.name == "graphrag"


@pytest.mark.asyncio
async def test_list_tools(server_params):
    """期待するツールがすべて登録されていること。"""
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.list_tools()
            registered = {t.name for t in result.tools}
            assert EXPECTED_TOOLS <= registered, (
                f"未登録のツール: {EXPECTED_TOOLS - registered}"
            )


@pytest.mark.asyncio
async def test_tool_has_description(server_params):
    """各ツールに description が設定されていること。"""
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.list_tools()
            for tool in result.tools:
                if tool.name in EXPECTED_TOOLS:
                    assert tool.description, f"{tool.name} に description がありません"


# ---------------------------------------------------------------------------
# テスト: ツール呼び出し（インデックスが必要）
# ---------------------------------------------------------------------------


@skip_if_no_index()
@pytest.mark.asyncio
async def test_global_search_returns_text(server_params):
    """graphrag_global_search が文字列レスポンスを返すこと。"""
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(
                "graphrag_global_search",
                {"query": "What are the top themes in this story?"},
            )
            assert result.content, "レスポンスが空です"
            text = result.content[0].text
            assert isinstance(text, str) and len(text) > 0


@skip_if_no_index()
@pytest.mark.asyncio
async def test_local_search_returns_text(server_params):
    """graphrag_local_search が文字列レスポンスを返すこと。"""
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(
                "graphrag_local_search",
                {"query": "What machines or devices are described?"},
            )
            assert result.content
            assert isinstance(result.content[0].text, str)


@skip_if_no_index()
@pytest.mark.asyncio
async def test_global_search_response_type(server_params):
    """response_type パラメーターを指定しても正常に動作すること。"""
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(
                "graphrag_global_search",
                {
                    "query": "Summarize the key topics.",
                    "response_type": "Single Paragraph",
                },
            )
            assert result.content
            assert isinstance(result.content[0].text, str)

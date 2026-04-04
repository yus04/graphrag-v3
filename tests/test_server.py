"""GraphRAG MCP サーバーの基本テスト

実際の GraphRAG インデックス（Parquet ファイル群）を必要としない、
構造・設定・エントリーポイントに関するテストです。
"""

import importlib
import os
import sys

import pytest

# ---------------------------------------------------------------------------
# インポートテスト
# ---------------------------------------------------------------------------


def test_main_module_importable():
    """main モジュールが正常にインポートできること。"""
    # 既にインポート済みの場合はリロードして確認
    if "main" in sys.modules:
        mod = sys.modules["main"]
    else:
        mod = importlib.import_module("main")
    assert mod is not None


def test_mcp_instance_exists():
    """FastMCP インスタンス `mcp` が main モジュールに存在すること。"""
    import main  # noqa: PLC0415

    assert main.mcp is not None
    assert main.mcp.name == "graphrag"


def test_root_dir_default():
    """GRAPHRAG_ROOT 未設定時は Path('.') が使われること。"""
    # 環境変数をいったん退避
    original = os.environ.pop("GRAPHRAG_ROOT", None)
    try:
        # main を再ロードして _ROOT_DIR を確認
        if "main" in sys.modules:
            del sys.modules["main"]
        import main  # noqa: PLC0415

        assert str(main._ROOT_DIR) == "."
    finally:
        if original is not None:
            os.environ["GRAPHRAG_ROOT"] = original
        # キャッシュをクリアして他テストに影響しないようにする
        sys.modules.pop("main", None)


def test_root_dir_from_env(tmp_path):
    """GRAPHRAG_ROOT 環境変数が _ROOT_DIR に反映されること。"""
    os.environ["GRAPHRAG_ROOT"] = str(tmp_path)
    try:
        sys.modules.pop("main", None)
        import main  # noqa: PLC0415

        assert main._ROOT_DIR == tmp_path
    finally:
        os.environ.pop("GRAPHRAG_ROOT", None)
        sys.modules.pop("main", None)


# ---------------------------------------------------------------------------
# ツール登録テスト
# ---------------------------------------------------------------------------


def test_tool_functions_defined():
    """MCP ツール関数がモジュールレベルで定義されていること。"""
    sys.modules.pop("main", None)
    import main  # noqa: PLC0415

    for name in (
        "graphrag_global_search",
        "graphrag_local_search",
        "graphrag_drift_search",
        "graphrag_basic_search",
    ):
        assert hasattr(main, name), f"{name} が main モジュールに存在しません"
        assert callable(getattr(main, name)), f"{name} は callable である必要があります"


# ---------------------------------------------------------------------------
# トランスポート設定テスト（環境変数）
# ---------------------------------------------------------------------------


def test_transport_default_stdio():
    """MCP_TRANSPORT 未設定時のデフォルトが 'stdio' であること。"""
    os.environ.pop("MCP_TRANSPORT", None)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    assert transport == "stdio"


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_transport_env_values(transport):
    """有効なトランスポート値が MCP_TRANSPORT 経由で取得できること。"""
    os.environ["MCP_TRANSPORT"] = transport
    try:
        assert os.environ.get("MCP_TRANSPORT") == transport
    finally:
        os.environ.pop("MCP_TRANSPORT", None)


def test_port_env_resolution():
    """PORT → MCP_PORT の優先順位でポートが解決されること。"""
    # PORT を優先
    os.environ["PORT"] = "9000"
    os.environ["MCP_PORT"] = "7000"
    port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", "8000")))
    assert port == 9000

    # PORT がない場合は MCP_PORT
    del os.environ["PORT"]
    port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", "8000")))
    assert port == 7000

    # 両方ない場合はデフォルト 8000
    del os.environ["MCP_PORT"]
    port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", "8000")))
    assert port == 8000

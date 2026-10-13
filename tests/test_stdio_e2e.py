"""End-to-end: launch the real server as a subprocess and talk to it over stdio,
exactly as Claude Desktop does. Uses the offline hash embedder, so no model download."""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


def _env(index_dir):
    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(ROOT / "src"),
        "RAG_EMBEDDER": "hash",
        "RAG_INDEX_DIR": str(index_dir),
        "RAG_DATA_DIR": str(ROOT / "sample_data"),
    }


def test_stdio_server_answers_a_search(tmp_path):
    env = _env(tmp_path / "index")

    # 1. Build the index with the CLI.
    cli = subprocess.run([sys.executable, "-m", "rag_mcp.ingest"], env=env,
                         capture_output=True, text=True, timeout=120)
    assert cli.returncode == 0, cli.stderr
    assert "Indexed" in cli.stdout

    # 2. Start the server and use it through a real MCP client.
    params = StdioServerParameters(command=sys.executable, args=["-m", "rag_mcp"], env=env)

    async def go():
        async with Client(params) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            result = await client.call_tool("search_documents", {"query": "Deck 2 Laboratories", "top_k": 1})
            return tools, result

    tools, result = asyncio.run(asyncio.wait_for(go(), timeout=60))
    assert "search_documents" in tools
    assert not result.is_error
    assert result.structured_content["result"][0]["source"] == "manuals/blueprint_notes.txt"

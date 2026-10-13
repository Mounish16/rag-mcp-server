"""Protocol-level tests: a real MCP client talking to the server in-process."""
import asyncio
import json

from mcp import Client

from rag_mcp.server import create_server

READ_ONLY_TOOLS = {"search_documents", "get_document_chunk", "list_sources", "index_stats"}


def run(server, action):
    async def _go():
        async with Client(server) as client:
            return await action(client)

    return asyncio.run(_go())


def tool_data(result):
    """Structured output for the tool (list results are wrapped as {'result': [...]})."""
    assert not result.is_error, result.content
    data = result.structured_content
    return data["result"] if set(data) == {"result"} else data


def test_server_lists_expected_tools(indexed_store, settings):
    server = create_server(indexed_store, settings)
    tools = run(server, lambda c: c.list_tools()).tools
    assert {t.name for t in tools} == READ_ONLY_TOOLS | {"rebuild_index"}


def test_tool_annotations_mark_read_only_and_destructive(indexed_store, settings):
    server = create_server(indexed_store, settings)
    tools = {t.name: t for t in run(server, lambda c: c.list_tools()).tools}
    for name in READ_ONLY_TOOLS:
        assert tools[name].annotations.read_only_hint is True
    assert tools["rebuild_index"].annotations.destructive_hint is True


def test_rebuild_index_accepts_no_arguments(indexed_store, settings):
    """It must not take a path, so it can never be pointed at arbitrary files."""
    server = create_server(indexed_store, settings)
    tools = {t.name: t for t in run(server, lambda c: c.list_tools()).tools}
    assert tools["rebuild_index"].input_schema.get("properties", {}) == {}


def test_search_documents_returns_cited_hits(indexed_store, settings):
    server = create_server(indexed_store, settings)
    result = run(server, lambda c: c.call_tool(
        "search_documents", {"query": "What is on Deck 2?", "top_k": 2}))
    hits = tool_data(result)
    assert len(hits) == 2
    assert hits[0]["source"] == "manuals/blueprint_notes.txt"
    assert hits[0]["citation"] == "[1]"


def test_search_documents_clamps_top_k(indexed_store, settings):
    server = create_server(indexed_store, settings)
    one = tool_data(run(server, lambda c: c.call_tool("search_documents", {"query": "deck", "top_k": 0})))
    many = tool_data(run(server, lambda c: c.call_tool("search_documents", {"query": "deck", "top_k": 100000})))
    assert len(one) == 1
    assert 1 < len(many) <= 20


def test_search_documents_respects_source_filter(indexed_store, settings):
    server = create_server(indexed_store, settings)
    hits = tool_data(run(server, lambda c: c.call_tool(
        "search_documents", {"query": "incident", "source": "security/incident_reports.json"})))
    assert hits and {h["source"] for h in hits} == {"security/incident_reports.json"}


def test_get_document_chunk_ok_and_not_found(indexed_store, settings):
    server = create_server(indexed_store, settings)
    ok = tool_data(run(server, lambda c: c.call_tool(
        "get_document_chunk", {"source": "manuals/blueprint_notes.txt", "chunk": 0})))
    assert ok["status"] == "ok" and ok["has_previous"] is False
    missing = tool_data(run(server, lambda c: c.call_tool(
        "get_document_chunk", {"source": "manuals/blueprint_notes.txt", "chunk": 999})))
    assert missing["status"] == "not_found"


def test_rebuild_index_repopulates_an_empty_store(empty_store, settings):
    server = create_server(empty_store, settings)
    assert empty_store.count() == 0
    summary = tool_data(run(server, lambda c: c.call_tool("rebuild_index", {})))
    assert summary["documents"] > 0
    assert empty_store.count() == summary["chunks"] > 0


def test_resources_return_json(indexed_store, settings):
    server = create_server(indexed_store, settings)
    uris = {str(r.uri) for r in run(server, lambda c: c.list_resources()).resources}
    assert uris == {"rag://sources", "rag://stats"}
    stats = run(server, lambda c: c.read_resource("rag://stats"))
    assert json.loads(stats.contents[0].text)["chunks"] == indexed_store.count()


def test_prompts_are_listed_and_filled_in(indexed_store, settings):
    server = create_server(indexed_store, settings)
    names = {p.name for p in run(server, lambda c: c.list_prompts()).prompts}
    assert names == {"grounded_answer", "summarize_source"}
    prompt = run(server, lambda c: c.get_prompt("grounded_answer", {"question": "Who is the captain?"}))
    assert "Who is the captain?" in prompt.messages[0].content.text

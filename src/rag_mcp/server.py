"""MCP server exposing a local ChromaDB knowledge base.

The server only does retrieval. The connected model (for example Claude)
writes the answer from the retrieved, cited chunks.
"""
import json
import logging
import sys
from typing import Any, Optional

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from rag_mcp.config import Settings
from rag_mcp.embedding import make_embedder
from rag_mcp.ingest import build_index
from rag_mcp.store import VectorStore

logger = logging.getLogger("rag-mcp")

MAX_TOP_K = 20

INSTRUCTIONS = (
    "This server searches a local knowledge base. Call `search_documents` to find "
    "relevant passages before answering questions about the indexed documents, "
    "answer only from the returned text, and cite sources as [n] with the file name. "
    "If nothing relevant comes back, say so instead of guessing."
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


def create_server(store: VectorStore, settings: Settings) -> MCPServer:
    mcp = MCPServer("rag-knowledge-base", instructions=INSTRUCTIONS)

    # ------------------------------------------------------------------ tools
    @mcp.tool(annotations=READ_ONLY)
    def search_documents(query: str, top_k: int = 5, source: Optional[str] = None) -> list[dict[str, Any]]:
        """Semantic search over the knowledge base.

        Args:
            query: What to look for, in natural language.
            top_k: How many passages to return (1-20).
            source: Optional file path (as listed by `list_sources`) to restrict the search to.

        Returns passages with a citation label, source file, chunk number and distance
        (lower means more similar).
        """
        top_k = max(1, min(int(top_k), MAX_TOP_K))
        return store.search(query, top_k=top_k, source=source or None)

    @mcp.tool(annotations=READ_ONLY)
    def get_document_chunk(source: str, chunk: int) -> dict[str, Any]:
        """Fetch one exact chunk by source file and chunk number, e.g. to read the text around a search hit."""
        found = store.get_chunk(source, chunk)
        if found is None:
            return {"status": "not_found", "source": source, "chunk": chunk}
        found["status"] = "ok"
        found["has_previous"] = store.get_chunk(source, chunk - 1) is not None
        found["has_next"] = store.get_chunk(source, chunk + 1) is not None
        return found

    @mcp.tool(annotations=READ_ONLY)
    def list_sources() -> list[dict[str, Any]]:
        """List every indexed source file with its number of chunks."""
        return store.list_sources()

    @mcp.tool(annotations=READ_ONLY)
    def index_stats() -> dict[str, Any]:
        """Return the collection name and the number of indexed chunks and sources."""
        return store.stats()

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
        )
    )
    def rebuild_index() -> dict[str, Any]:
        """Re-index the configured data directory, replacing the current index.

        Takes no path on purpose: it can only read the directory the server was
        configured with, never arbitrary locations on disk.
        """
        logger.info("Rebuilding index from %s", settings.data_dir)
        return build_index(store, settings.data_dir, settings.chunk_words, settings.overlap_words)

    # -------------------------------------------------------------- resources
    @mcp.resource("rag://sources", name="sources", mime_type="application/json",
                  description="All indexed source files and their chunk counts")
    def sources_resource() -> str:
        return json.dumps(store.list_sources(), indent=2)

    @mcp.resource("rag://stats", name="stats", mime_type="application/json",
                  description="Index statistics")
    def stats_resource() -> str:
        return json.dumps(store.stats(), indent=2)

    # ---------------------------------------------------------------- prompts
    @mcp.prompt(description="Answer a question using only the knowledge base, with citations")
    def grounded_answer(question: str) -> str:
        return (
            f"Answer this question using the knowledge base: {question}\n\n"
            "1. Call `search_documents` (try a second, differently worded query if the first "
            "results look weak).\n"
            "2. Answer using only the returned passages.\n"
            "3. Cite each claim as [n] and list the source files at the end.\n"
            "4. If the passages do not contain the answer, say you could not find it."
        )

    @mcp.prompt(description="Summarise one indexed source file")
    def summarize_source(source: str) -> str:
        return (
            f"Summarise the document `{source}`.\n\n"
            f"Use `search_documents` with source=\"{source}\" and several broad queries, or "
            "`get_document_chunk` to read it chunk by chunk. Give a short summary and "
            "list the key facts, citing chunk numbers."
        )

    return mcp


def build_store(settings: Settings) -> VectorStore:
    return VectorStore(
        settings.index_dir,
        settings.collection,
        make_embedder(settings.embedder, settings.embed_model),
    )


def main() -> None:
    # stdout carries the MCP protocol, so all logging must go to stderr.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    logger.info("Starting RAG MCP server (index=%s)", settings.index_dir)
    create_server(build_store(settings), settings).run()


if __name__ == "__main__":
    main()

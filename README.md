# RAG MCP Server

**An [MCP](https://modelcontextprotocol.io) server that gives any MCP client (an AI assistant or agent) semantic search over a local ChromaDB knowledge base, with citations.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)
![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB-orange)
![Tests](https://img.shields.io/badge/tests-25%20passing-brightgreen)

Companion to [astraeus-rag-assistant](https://github.com/Mounish16/astraeus-rag-assistant), which answers questions with a local model and a Streamlit UI. This project takes the opposite approach: the server only does **retrieval**, and the model you connect it to writes the answer.

## Why retrieval-only?

An MCP host (an AI assistant or agent app) already has a strong language model. The server's job is to hand it the right passages, with sources, and to stay out of the way:

```
 You ask the assistant a question
          │
          ▼
 MCP client (LLM) ─── calls tool ──►  rag-mcp-server
          ▲                                  │  embed query
          │                                  ▼
          └──── cited passages ◄──────  ChromaDB  (cosine-style vector search)
          │
          ▼
 Answer written by the LLM, citing [1], [2] ...
```

No second model to host, no prompt template to maintain, and the answer quality improves whenever the connected model does.

## What it exposes

| Kind | Name | What it does |
|---|---|---|
| Tool | `search_documents(query, top_k, source?)` | Semantic search; returns passages with citation label, source file, chunk number and distance |
| Tool | `get_document_chunk(source, chunk)` | Fetch one exact chunk, with `has_previous` / `has_next` for reading around a hit |
| Tool | `list_sources()` | Indexed files and their chunk counts |
| Tool | `index_stats()` | Collection size |
| Tool | `rebuild_index()` | Re-index the configured data directory (marked destructive) |
| Resource | `rag://sources`, `rag://stats` | The same information as JSON resources |
| Prompt | `grounded_answer(question)` | Instructs the model to search, answer only from results and cite |
| Prompt | `summarize_source(source)` | Summarise one indexed file |

## Quick start

```bash
git clone https://github.com/Mounish16/rag-mcp-server.git
cd rag-mcp-server
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Index the bundled sample data (the fictional Astraeus-9 spaceship corpus)
python -m rag_mcp.ingest
```

The first run downloads the `all-MiniLM-L6-v2` embedding model (about 90 MB). To index your own files, set `RAG_DATA_DIR` (see [Configuration](#configuration)). Supported formats: `.txt`, `.md`, `.json`, `.jsonl`, `.yaml`, `.yml`, `.pdf`.

### Connect it to an MCP client

Any MCP client that supports stdio servers can run it. Examples for two popular clients follow; for others, use the same command, arguments and environment variables.

#### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), using **absolute paths**:

```json
{
  "mcpServers": {
    "rag-knowledge-base": {
      "command": "/ABSOLUTE/PATH/TO/rag-mcp-server/.venv/bin/python",
      "args": ["-m", "rag_mcp"],
      "env": {
        "RAG_DATA_DIR": "/ABSOLUTE/PATH/TO/rag-mcp-server/sample_data",
        "RAG_INDEX_DIR": "/ABSOLUTE/PATH/TO/rag-mcp-server/index/chroma"
      }
    }
  }
}
```

Restart the app, then try: *"What is on Deck 2 of the Astraeus-9?"* The assistant will call `search_documents` and answer from the returned passages.

#### Claude Code

```bash
claude mcp add rag-knowledge-base \
  -e RAG_INDEX_DIR=$PWD/index/chroma -e RAG_DATA_DIR=$PWD/sample_data \
  -- $PWD/.venv/bin/python -m rag_mcp
```

### Try it in the MCP Inspector (no AI client needed)

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a browser page for calling the server's tools by hand. It needs Node.js (for `npx`).

1. From the project folder, with the virtual environment active and the index built:

   ```bash
   cd rag-mcp-server
   source .venv/bin/activate
   npx @modelcontextprotocol/inspector -e RAG_DATA_DIR=$PWD/sample_data -e RAG_INDEX_DIR=$PWD/index/chroma python -m rag_mcp
   ```

2. The terminal prints a **session token** and a link that already contains it:

   ```
   Session token: <long hex string>
   Open inspector with token pre-filled:
   http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=<long hex string>
   ```

   Open that full link. The token changes on every start and only works for that run on your machine.

3. If you opened plain `http://127.0.0.1:6274` instead, you will see *"Connection Error - Did you add the proxy session token in Configuration?"*. Fix it by opening **Configuration** in the left sidebar, pasting the token into **Proxy Session Token**, and clicking **Connect**.

4. Open the **Tools** tab, click **List Tools**, pick `search_documents`, fill in the arguments and click **Run Tool**.

Settings if you fill the form in by hand instead of using the command above:

| Field | Value |
|---|---|
| Transport | STDIO |
| Command | `python` |
| Arguments | `-m rag_mcp` |
| Environment variables | `RAG_DATA_DIR` = absolute path to `sample_data`, `RAG_INDEX_DIR` = absolute path to `index/chroma` |

See [docs/EXAMPLES.md](docs/EXAMPLES.md) for ready-made queries to paste in, and what each should return.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Inspector says *"Did you add the proxy session token in Configuration?"* | Open the token link printed in the terminal, or paste the token into Configuration, Proxy Session Token |
| `ImportError: cannot import name 'Client' from 'mcp'` | An older `mcp` from another environment (for example conda) is being used. Activate `.venv` and run `python -m pytest` instead of `pytest` |
| Searches return nothing or the index is missing | Run `python -m rag_mcp.ingest` first |
| Server does not show up in Claude Desktop | Use absolute paths in the config, restart Claude Desktop fully, and read `~/Library/Logs/Claude/mcp-server-rag-knowledge-base.log` |
| Lots of Hugging Face `HTTP Request` lines in the log | Harmless; they come from the embedding model check on stderr |
| `npx: command not found` | Install Node.js from nodejs.org |

## Configuration

All settings are environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `RAG_DATA_DIR` | `./sample_data` | Folder of documents to index |
| `RAG_INDEX_DIR` | `./index/chroma` | Where the ChromaDB index is stored |
| `RAG_COLLECTION` | `rag_collection` | Collection name |
| `RAG_EMBEDDER` | `sentence-transformers` | `sentence-transformers`, or `hash` for an offline demo/test embedder |
| `RAG_EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model name |
| `RAG_CHUNK_WORDS` / `RAG_OVERLAP_WORDS` | `200` / `40` | Chunk window and overlap, in words |

## Design notes

- **stdout is reserved for the protocol.** An MCP stdio server that prints anything else breaks the connection, so all logging goes to stderr, and the ingestion CLI is a separate entry point.
- **`rebuild_index` takes no arguments.** It can only re-read the directory the server was configured with, so a prompt-injected model cannot point it at arbitrary files on disk. Ingestion also skips symlinks that resolve outside the data directory and files over 20 MB.
- **Tool annotations are honest.** Search and list tools are marked read-only and idempotent; `rebuild_index` is marked destructive, so clients can ask for confirmation.
- **`top_k` is clamped to 1 to 20**, and tools return structured data, not prose.
- **Models load lazily**, so the server starts instantly and only pays the embedding-model cost on the first search.
- **Offline test embedder.** `HashEmbedder` makes the whole test suite, including a real stdio client-to-server run, work without downloading a model.

## Tests

```bash
pytest
```

25 tests cover chunking and file loading, the vector store, every tool, resource and prompt through a real in-process MCP client, and an end-to-end run that launches the server as a subprocess and talks to it over stdio, the same way Claude Desktop does.

## Project layout

```
src/rag_mcp/
  config.py      settings from environment variables
  embedding.py   sentence-transformers and offline hash embedders
  store.py       ChromaDB wrapper (search, get chunk, list sources)
  ingest.py      loading, chunking and indexing (also a CLI)
  server.py      MCP tools, resources and prompts
tests/           unit, protocol and stdio end-to-end tests
docs/EXAMPLES.md  ready-made queries and what to expect
sample_data/     fictional Astraeus-9 corpus for demos
```

## Roadmap

- Knowledge-graph tools (entities and relationships in Neo4j) alongside vector search, for GraphRAG-style questions
- Hybrid retrieval (BM25 plus vectors) and reranking
- Streamable HTTP transport for remote use

## Licence and data

The bundled sample data is fictional and created for educational use.

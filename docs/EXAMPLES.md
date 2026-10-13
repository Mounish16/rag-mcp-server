# Examples

Ready-made things to try against the bundled Astraeus-9 sample data. Build the index first (`python -m rag_mcp.ingest`).

Lower `distance` means a closer match. Roughly: below 1.0 is a good match, above about 1.2 is weak or unrelated.

## In the MCP Inspector

Start it as described in the [README](../README.md#try-it-in-the-mcp-inspector-no-claude-needed), open the token link, click **Connect**, then use the tabs below.

### Tools tab: `search_documents`

| Arguments | What to expect |
|---|---|
| `{"query": "What is on Deck 2?", "top_k": 2}` | `manuals/blueprint_notes.txt` first: Deck 2 is the laboratories (Xenobiology, Spectrometry, Geo-Analytics) |
| `{"query": "What is on Deck 3?", "top_k": 3}` | Deck layout passage mentioning Cryo Storage |
| `{"query": "Where is cryo storage located?", "top_k": 3}` | Deck layout passage (Deck 3 lists Cryo Storage) and related passages |
| `{"query": "Who runs the navigation dome?", "top_k": 2}` | Command bridge / navigation passages (from the PDF notes) |
| `{"query": "How is the ship powered?", "top_k": 3}` | Whatever power-related passages exist (the sample data mentions a fusion micro-cell); distances may be mid-range |
| `{"query": "Deck 2 Laboratories", "source": "manuals/blueprint_notes.txt", "top_k": 5}` | Only chunks from that one file (the `source` filter) |
| `{"query": "banana smoothie recipe", "top_k": 2}` | Unrelated question: high distances (above about 1.2), showing the server does not invent an answer |

### Tools tab: other tools

| Tool | Arguments | What to expect |
|---|---|---|
| `list_sources` | none | Every indexed file with its chunk count (10 files for the sample data) |
| `index_stats` | none | Collection name and chunk count (17 for the sample data) |
| `get_document_chunk` | `{"source": "manuals/blueprint_notes.txt", "chunk": 0}` | That exact chunk, with `has_previous` / `has_next`. Fetch chunk 1 to keep reading |
| `rebuild_index` | none | Re-indexes the configured data directory. Marked destructive, so run it only when you mean to |

### Resources tab

- `rag://sources` returns the same file list as `list_sources`, as JSON.
- `rag://stats` returns the same information as `index_stats`.

### Prompts tab

- `grounded_answer` with `question` = `What is on Deck 2?` returns the instruction text that tells a model to search, answer only from the results and cite sources.
- `summarize_source` with `source` = `manuals/blueprint_notes.txt` returns a prompt asking the model to summarise that file.

## In Claude Desktop or Claude Code

After adding the server (see the README), ask in plain language:

- "What is on Deck 2 of the Astraeus-9?"
- "Using the knowledge base, list every deck and what is on it."
- "Which files are in the knowledge base?"
- "Summarise the blueprint notes."
- "Does the knowledge base say anything about a pizza oven?" (it should say it found nothing relevant)

Claude calls `search_documents`, reads the returned passages and cites the sources in its answer.

## From a script (no Claude, no browser)

```python
import asyncio, os, sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters

env = dict(os.environ, RAG_DATA_DIR=os.path.abspath("sample_data"), RAG_INDEX_DIR=os.path.abspath("index/chroma"))
params = StdioServerParameters(command=sys.executable, args=["-m", "rag_mcp"], env=env)

async def main():
    async with Client(params) as c:
        for q in ["What is on Deck 2?", "Who commands the ship?"]:
            r = await c.call_tool("search_documents", {"query": q, "top_k": 2})
            print("\nQ:", q)
            for h in r.structured_content["result"]:
                print(" -", h["source"], "chunk", h["chunk"], "dist", round(h["distance"], 3))
                print("  ", h["text"][:160].replace("\n", " "))

asyncio.run(main())
```

Run it from the project folder with the virtual environment active.

## Using your own documents

Point `RAG_DATA_DIR` at any folder of `.txt`, `.md`, `.json`, `.jsonl`, `.yaml`, `.yml` or `.pdf` files and rebuild:

```bash
RAG_DATA_DIR=/path/to/your/docs python -m rag_mcp.ingest
```

Then use the same `RAG_DATA_DIR` and `RAG_INDEX_DIR` values in the Inspector command or the Claude Desktop config.

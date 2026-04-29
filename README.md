[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: Elastic-2.0](https://img.shields.io/badge/License-Elastic%202.0-blue.svg)](https://www.elastic.co/licensing/elastic-license)
[![Version](https://img.shields.io/badge/version-0.92.2-blue.svg)](https://github.com/Flux-Frontiers/diary_kg/releases)
[![CI](https://github.com/Flux-Frontiers/diary_kg/actions/workflows/ci.yml/badge.svg)](https://github.com/Flux-Frontiers/diary_kg/actions/workflows/ci.yml)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![DOI](https://zenodo.org/badge/1183242132.svg)](https://zenodo.org/badge/latestdoi/1183242132)

**DiaryKG** — A deterministic knowledge graph for diaries and journals with semantic indexing and source-grounded snippet packing.

*Author: Eric G. Suchanek, PhD — Flux-Frontiers, Liberty TWP, OH*

---

## Overview

DiaryKG ingests plain-text diary or journal files and produces a hybrid SQLite + LanceDB knowledge graph that supports natural-language querying, source-grounded snippet packs for LLM context, temporal analysis, and topic/context classification.

It was built around the **Samuel Pepys diary** (1660–1669, 7,282 entries) but is general-purpose — any structured plain-text diary or journal file is supported.

The system is organized as two cooperating Python packages:

- **`diary_transformer`** — spaCy NLP enrichment, topic classification, sentence-group chunking, diversity sampling. Turns a raw diary text file into one Markdown chunk-file per entry, with full provenance metadata.
- **`diary_kg`** — orchestrates the chunking pipeline, builds the DocKG-backed SQLite graph + LanceDB vector index over the chunked corpus, and exposes the query / pack / analyze / snapshot APIs and an MCP server.

### Architecture

```
Plain-text diary
       │
       ▼
DiaryTransformer          spaCy NLP enrichment, topic classification,
  (diary_transformer)     sentence-group chunking, diversity sampling
       │
       ▼
Corpus (.md files)        one file per chunk, full provenance metadata
  .diarykg/corpus/
       │
       ├──▶ DocKG build   SQLite graph + LanceDB vector index
       │     (doc-kg)     BAAI/bge-small-en-v1.5 (384-d, normalized)
       │
       └──▶ DiaryKG APIs  query(), pack(), analyze(), snapshot_save()
```

### Storage layout

```
.diarykg/
  config.json         build parameters
  corpus/             one .md chunk file per diary entry
  graph.sqlite        SQLite knowledge graph (DocKG)
  lancedb/            LanceDB vector index (384-d HNSW)
  snapshots/          point-in-time metrics snapshots
```

---

## Quick Start

```bash
# Install
pip install diary-kg

# Build from a plain-text diary file (creates .diarykg/ in the current dir)
diarykg build --source path/to/diary.txt

# Query the corpus
diarykg query "office work and the navy board"

# Pack snippets for an LLM context window
diarykg pack "Pepys at the theatre" --output context.md

# Start the MCP server (stdio transport for Claude Code / Cline / etc.)
diarykg-mcp
```

---

## Installation

### From PyPI (recommended)

```bash
# Core runtime (CLI + MCP server + graph engine)
pip install diary-kg

# With Streamlit / Plotly visualizer extras
pip install "diary-kg[viz]"

# With 3D visualization extras (PyVista, PyQt5, etc. — heavy dependencies)
pip install "diary-kg[viz3d]"

# With KG integration deps (pycode-kg, doc-kg)
pip install "diary-kg[kgdeps]"

# Everything
pip install "diary-kg[all]"
```

### Poetry project

```bash
poetry add diary-kg
poetry add "diary-kg[viz]"
poetry add "diary-kg[kgdeps]"
```

### Local development

```bash
git clone https://github.com/Flux-Frontiers/diary_kg.git
cd diary_kg
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
poetry run pytest
```

---

## CLI Reference

The `diarykg` console script is the primary entry point. The MCP server ships as a separate `diarykg-mcp` script.

| Command | Purpose |
|---|---|
| `diarykg build` | Full pipeline: ingest diary → chunk → index into SQLite + LanceDB |
| `diarykg reindex` | Rebuild the LanceDB + SQLite index from the existing corpus (skips ingest) |
| `diarykg query <QUERY>` | Hybrid semantic + graph search; returns ranked hits |
| `diarykg pack <QUERY>` | Source-grounded Markdown snippet pack for LLM context |
| `diarykg analyze` | Generate a Markdown analysis report for the corpus |
| `diarykg status` | KG health check and build metadata, without loading the full DB |
| `diarykg snapshot save` | Capture point-in-time corpus metrics |
| `diarykg snapshot list / show / diff / prune` | Inspect and prune snapshots |
| `diarykg install-hooks` | Install the DiaryKG pre-commit git hook |
| `diarykg-mcp` | Run the MCP server (stdio / SSE transport) |

Every command accepts a `ROOT` positional argument (default: current directory) pointing at the project that contains `.diarykg/`. Run `diarykg <command> --help` for the full option list.

### Build

```bash
# First build — --source is required
diarykg build --source pepys/pepys_enriched_full.txt

# Incremental update (preserve existing corpus + DBs)
diarykg build --source pepys/pepys_enriched_full.txt --update

# Configure chunking
diarykg build --source diary.txt --chunking semantic --chunk-size 800 --max-chunks 5

# Capture a snapshot immediately after the build
diarykg build --source diary.txt --snapshot
```

Chunking strategies: `sentence_group` (default), `semantic`, `hybrid`. Custom topic catalogs can be supplied with `--topics-file path/to/topics.yaml`.

### Query and pack

```bash
# Top-k semantic hits as a rich-formatted table
diarykg query "Navy affairs" -k 12

# Same query as JSON for downstream tooling
diarykg query "Navy affairs" --json

# Markdown snippet pack ready to paste into an LLM
diarykg pack "Pepys wife Elizabeth" --output context.md
```

### Snapshots

Version is an option (`-v` / `--version`), not a positional argument; bare positionals are treated as `ROOT`.

```bash
# Capture a snapshot at the current corpus state
diarykg snapshot save -v 0.92.2

# With a label
diarykg snapshot save -v 0.92.2 -l "after backfilling 1667 entries"

# List, inspect, compare
diarykg snapshot list
diarykg snapshot show <key>
diarykg snapshot diff <key_a> <key_b>

# Prune snapshots that carry no new metric information
diarykg snapshot prune --dry-run
```

Snapshots are keyed by git tree hash and capture chunk/entry/node/edge counts, temporal span, topic/context distributions, and deltas vs. the previous and baseline snapshots.

### Reindex

Use after changing the embedding model or fixing an index bug, when the corpus `.md` chunk files are already up-to-date.

```bash
diarykg reindex
```

---

## MCP Server

DiaryKG ships an MCP server that exposes three tools to AI agents.

| Tool | Returns | Description |
|---|---|---|
| `query_diary(q, k)` | JSON | Semantic search over the diary corpus; ranked hit list with `node_id`, `score`, `summary`, `source_file`, `timestamp`, `category`, `context`. |
| `pack_diary(q, k)` | Markdown | Top-k diary snippets formatted as Markdown sections, ready to paste into an LLM context window. |
| `diary_stats()` | JSON | Combined corpus metadata (`info()`) and KG stats (`stats()`): chunk/entry counts, temporal span, topic/context distributions, node/edge counts. |

### Run the server

```bash
# Stdio transport (default — for Claude Code / Cline / Claude Desktop / Kilo Code)
diarykg-mcp --repo /path/to/diary_project

# SSE transport
diarykg-mcp --repo /path/to/diary_project --transport sse
```

### Wire it up in an MCP client

Most MCP clients use a JSON config file. Example `.mcp.json` for Claude Code or Kilo Code:

```json
{
  "mcpServers": {
    "diarykg": {
      "command": "diarykg-mcp",
      "args": ["--repo", "/absolute/path/to/diary_project"]
    }
  }
}
```

For per-agent setup steps, run `/setup-diarykg-mcp` in Claude Code (the slash command at [.claude/commands/setup-diarykg-mcp.md](.claude/commands/setup-diarykg-mcp.md) walks through the Claude Code, Cline, Claude Desktop, GitHub Copilot, and Kilo Code variants).

---

## Python API

```python
from diary_kg import DiaryKG

# First build
kg = DiaryKG("/path/to/project", source_file="pepys_diary.txt")
kg.build()

# Subsequent runs only need the project root
kg = DiaryKG("/path/to/project")

# Hybrid semantic + graph search
hits = kg.query("what did Pepys think of the theatre?", k=12)

# Source-grounded snippet pack (list of dicts with content, metadata)
snippets = kg.pack("Navy corruption", k=8)

# Corpus metadata + KG stats
info = kg.info()        # chunk_count, entry_count, temporal_span, topic/context distributions
stats = kg.stats()      # node_count, edge_count

# Markdown analysis report
report = kg.analyze()

# Snapshots
kg.snapshot_save(version="0.92.2", label="release")
kg.snapshot_list()
kg.snapshot_show(key)
kg.snapshot_diff(key_a, key_b)
```

The package re-exports the primary types:

```python
from diary_kg import DiaryKG, DEFAULT_MODEL, CrossHit, CrossSnippet, KGEntry, KGKind
```

---

## Embedding Model

| Use | Model | Dims | Notes |
|---|---|---|---|
| Knowledge graph build | `BAAI/bge-small-en-v1.5` | 384 | Fast, general-text, L2-normalized |
| Multipass pipeline | `BAAI/bge-small-en-v1.5` | 384 | Same model stack-wide; loaded via `kg_utils.embedder.load_sentence_transformer()` |

Model loading is handled by `kg_utils.embedder.load_sentence_transformer()`, which enforces `local_files_only=True` when a cached copy exists — preventing spurious HuggingFace HEAD requests in offline or air-gapped environments.

---

## Project Structure

```
diary_kg/
├── src/
│   ├── diary_kg/                 DiaryKG package
│   │   ├── kg.py                 DiaryKG class (build, query, pack, analyze, snapshots)
│   │   ├── cli.py                Click CLI — `diarykg` console script
│   │   ├── mcp_server.py         MCP server — `diarykg-mcp` console script
│   │   ├── primitives.py         CrossHit, CrossSnippet, KGEntry, KGKind
│   │   ├── snapshots.py          DiarySnapshotManager
│   │   └── module/               Pluggable KGModule interface
│   └── diary_transformer/        Chunking + NLP pipeline
│       ├── transformer.py        DiaryTransformer orchestrator
│       ├── chunker.py            sentence_group / semantic / hybrid chunkers
│       ├── classifier.py         Topic + context classification
│       ├── parser.py             Diary file parser
│       ├── topic_classifier.py   Hybrid keyword / K-means classifier
│       └── topics.yaml           Default topic catalog
├── pepys/                        Sample Pepys diary corpus
├── docs/                         Technical articles and disclosures
├── benchmarks/                   Embedding model benchmarks
├── analysis/                     Versioned analysis reports
├── tests/                        Pytest suite
└── scripts/                      Wiki generator, embedder benchmarks
```

---

## Dependencies

- `doc-kg ≥ 0.12.0` — hybrid semantic + structural document knowledge graph
- `kgmodule-utils ≥ 0.2.3` — shared embedding, model cache, and snapshot utilities
- `spacy ≥ 3.8` with `en_core_web_sm` model
- `sentence-transformers ≥ 5.4`
- `lancedb ≥ 0.29`
- `transformers ≥ 4.57`
- `mcp ≥ 1.0` — Model Context Protocol SDK
- `rich ≥ 14.3` — terminal output and progress bars

Optional extras (`viz`, `viz3d`, `kgdeps`, `dev`) are documented in [pyproject.toml](pyproject.toml).

---

## Development

```bash
# Install with dev tools
pip install -e ".[dev]"

# Run the test suite
pytest                          # uses pytest.ini (testpaths = tests/)
pytest -m "not slow"            # skip slow tests
pytest --cov=diary_kg           # with coverage

# Lint and format
ruff check src tests
ruff format src tests
mypy src/

# Pre-commit (runs ruff, mypy, pytest, detect-secrets, pylint)
pre-commit run --all-files
```

The repo ships an optional pre-commit git hook that rebuilds PyCodeKG and DocKG indices from staged content, captures metrics snapshots keyed by git tree hash, and stages `.pycodekg/snapshots/` and `.dockg/snapshots/` atomically before the standard pre-commit framework checks run. Install it with:

```bash
diarykg install-hooks --repo .
# Skip per-commit with: DIARYKG_SKIP_SNAPSHOT=1 git commit ...
```

---

## License

Elastic License 2.0 — see [LICENSE](LICENSE) and the [Elastic License page](https://www.elastic.co/licensing/elastic-license).

## Citation

If you use DiaryKG in academic work, please cite via the metadata in [CITATION.cff](CITATION.cff).

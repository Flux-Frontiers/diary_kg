# Release Notes — v0.92.2

> Released: 2026-04-28
> Author: Eric G. Suchanek, PhD — Flux-Frontiers, Liberty TWP, OH

---

## What is DiaryKG?

DiaryKG is a deterministic semantic knowledge graph for diary and journal corpora.
It ingests plain-text diary files, enriches each entry with NLP-derived topics,
contexts, and temporal metadata, chunks the corpus with configurable strategies,
and indexes the result into a hybrid SQLite + LanceDB store for natural-language
querying.

The system was built around the **Samuel Pepys diary** (1660–1669, 7,282 entries)
but is general-purpose — any structured plain-text diary or journal file is
supported.

---

## Architecture

```
Plain-text diary
       │
       ▼
DiaryTransformer          — spaCy NLP enrichment, topic classification,
  (diary_transformer)       sentence-group chunking, diversity sampling
       │
       ▼
Corpus (.md files)        — one file per chunk, full provenance metadata
  .diarykg/corpus/
       │
       ├──▶ DocKG build   — SQLite graph + LanceDB vector index
       │     (doc-kg)       BAAI/bge-small-en-v1.5 (384-d, normalized)
       │
       └──▶ DiaryKG APIs  — query(), pack(), analyze(), snapshot_save()
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

## Core Features

### Natural-language querying
- `DiaryKG.query(text)` — hybrid semantic + graph search; returns ranked hits
  with score, timestamp, topic, context, and source provenance
- `DiaryKG.pack(text)` — LLM-ready Markdown snippet pack; top-k semantically
  relevant passages in a single context block

### MCP server integration
DiaryKG ships an MCP server (`diarykg mcp`) exposing three tools to AI agents:
- `query_diary` — semantic search across the corpus
- `pack_diary` — source-grounded snippet context for any query
- `diary_stats` — live corpus statistics

### CLI (`diarykg`)
| Command | Purpose |
|---|---|
| `diarykg build` | Full pipeline: ingest → chunk → index |
| `diarykg reindex` | Rebuild index only (skip ingest) |
| `diarykg query <QUERY>` | Natural-language search |
| `diarykg pack <QUERY>` | Snippet pack for LLM context |
| `diarykg analyze` | Corpus analysis report |
| `diarykg status` | KG health and build metadata |
| `diarykg snapshot save` | Capture metrics snapshot |
| `diarykg snapshot list/show/diff` | Snapshot inspection |

### Temporal knowledge graph
Every chunk node carries full temporal metadata — ISO date, year, month,
day-of-week — enabling chronological filtering and temporal span analysis.
`DiaryKG.info()` returns the corpus's `temporal_span` (start → end).

### Topic & context classification
Hybrid topic classification: supervised keyword matching (primary) with
unsupervised K-means fallback. Out-of-the-box topic catalog covers work,
domestic, social, naval, political, cultural, religious, health, and financial
domains. Custom YAML topic catalogs are supported via `--topics-file`.

### Point-in-time snapshots
`DiarySnapshotManager` captures chunk counts, node/edge counts, topic
distributions, temporal span, and chunking parameters at any commit.
`snapshot diff` compares any two snapshots side-by-side with deltas.

---

## Embedding Model

| Use | Model | Dims | Notes |
|---|---|---|---|
| Knowledge graph build | `BAAI/bge-small-en-v1.5` | 384 | Fast, general-text, L2-normalized |
| Multipass pipeline | `BAAI/bge-small-en-v1.5` | 384 | Same model stack-wide; loaded via `load_sentence_transformer()` |

Model loading is handled by `kg_utils.embedder.load_sentence_transformer()`,
which enforces `local_files_only=True` when a cached copy exists — preventing
spurious HuggingFace HEAD requests in offline or air-gapped environments.

---

## Reliability Fixes in This Release

- **SIGBUS (Bus Error 10) on Apple Silicon eliminated** — root cause was
  `dockg.build(wipe=False)` generating a 1024-clause OR-delete predicate that
  recursed 666 levels in LanceDB's Rust predicate evaluator, overflowing the
  tokio worker-thread stack guard page. Fix: `wipe=True` on every index build.
- **Shared embedder** — `DiaryKG.build()` now reuses the `SentenceTransformer`
  instance already loaded by `DiaryTransformer` (via `wrap_embedder()`),
  avoiding a second MPS allocation while the first model is still live.
- **Streaming cache serialisation** — `save_cache()` writes embeddings
  row-by-row, eliminating a ~750 MB memory spike on large corpora.
- **Thread safety** — `OMP_NUM_THREADS=1` and `TOKENIZERS_PARALLELISM=false`
  are set before spawning the multiprocess embedding pool.

---

## Dependencies

- `doc-kg ≥ 0.12.3` — hybrid semantic + structural document knowledge graph
- `kgmodule-utils ≥ 0.2.2` — shared embedding, model cache, and snapshot utilities
- `spacy ≥ 3.7` with `en_core_web_sm` model
- `sentence-transformers ≥ 5.2`
- `lancedb ≥ 0.29`
- `torch ≥ 2.5.1` (MPS on Apple Silicon, CUDA on Linux, CPU fallback)
- `rich ≥ 14.0` — terminal output and progress bars

---

## Quick Start

```bash
# Install
pip install diary-kg

# Build from a Pepys-format diary file
diarykg build --source pepys/pepys_enriched_full.txt

# Query
diarykg query "office work and the navy board"

# Pack context for an LLM
diarykg pack "Pepys at the theatre" --output context.md

# Start the MCP server
diarykg mcp
```

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

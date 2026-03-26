# NLP-Based Ingestion Workflow
## Pepys Diary — Full Pipeline

*Canonical home: `diary_kg/pepys/` — benchmarks: `diary_kg/benchmarks/`*

---

## Overview

The full pipeline transforms a raw historical diary text into a dense
embedding manifold suitable for temporal analysis, intrinsic dimensionality
estimation, and MRL retrieval benchmarking.  Every stage uses local NLP
— no inference APIs, no external services after initial model download.

```
raw_pepys_diary.txt  (Project Gutenberg transcription)
        │
        ▼
  pepys_proper_parse.py          <- date inference, time extraction, formatting
        │  TIMESTAMP | raw | DiaryText | <content>
        ▼
  pepys_clean.txt                <- 3355 timestamped entries (one per day)
        │
        ▼
  DiaryTransformer               <- diary_kg NLP enrichment pipeline
   (src/diary_transformer/)      │  Phase 1: spaCy feature extraction + k-means diversity selection
        │                        │  Phase 2: sentence-transformers chunking (sentence_group/semantic/hybrid)
        │                        │  Phase 3: TF-IDF k-means category discovery (unsupervised)
        │                        │  Phase 4: TopicClassifier refinement (YAML rules, hybrid scoring)
        │                        │  Phase 5: EntryChunk creation + structured output
        │  TIMESTAMP | TYPE | CATEGORY | CONTENT
        ▼
  pepys_enriched_full.txt        <- semantically enriched, topic-classified, chunked corpus
        │                          NOTE: N_chunks > N_entries — each diary entry produces
        │                          1–3 chunks split at sentence/semantic boundaries.
        │                          A 1000-entry temporal sample -> ~1500–2500 chunks.
        ▼
  benchmarks/pepys_embedder.py   <- multi-process sentence-transformers ingestion
        │  nomic-ai/nomic-embed-text-v1, N workers x shard
        ▼
  benchmarks/pepys_embeddings.json  <- float32 (N_chunks x 768) + texts + timestamps
        │
        ├──► intrinsic_dim()     PCA elbow, Participation Ratio, TwoNN
        ├──► mrl_mrr_at_k()      MRR@10 at 64/128/256/512/768 dims
        └──► ManifoldWalker      cosine-space flight origin -> destination
```

---

## Stage 1 — Parse: `pepys_proper_parse.py`

**Input:** Raw diary text (line-numbered Gutenberg format)
**Output:** `pepys/pepys_clean.txt` — 3355 timestamped entries

Parses historical 17th-century diary prose into timestamped records:
- Full date parsing: `"April 1st, 1660"`, `"10th."`, `"January 1659-60"` (dual-year)
- Smart time inference from content: `"three in the morning"` -> `03:00`, `"evening"` -> `18:00`
- Strips editorial notes `[...]` and line-number prefixes (`123->content`)
- Output format: `YYYY-MM-DDTHH:MM | raw | DiaryText | <content>`

```bash
python pepys/pepys_proper_parse.py \
    raw_pepys.txt \
    pepys/pepys_clean.txt \
    --vary-times
```

---

## Stage 2 — Enrich: `DiaryTransformer`

**Input:** `pepys/pepys_clean.txt`
**Output:** `pepys/pepys_enriched_full.txt`
**Source:** `src/diary_transformer/transformer.py`

A five-phase NLP pipeline that transforms flat diary entries into richly
classified, semantically chunked records.

### Important: chunks != entries

Each diary entry is split into 1–3 chunks at sentence or semantic
boundaries.  The enriched corpus has **more rows than the source**, and
a temporally-sampled subset of N entries produces approximately 1.5–2.5x N
chunks.  The embedding cache size reflects chunk count, not entry count.

### Phase 1 — NLP Feature Extraction + Diversity Selection (spaCy + k-means)

- Extracts per-entry NLP features via spaCy: named entities, POS tag
  distributions, text length
- Normalises feature vectors; applies k-means clustering to group
  thematically similar entries
- Selects representative entries from each cluster — ensures the subset
  has temporal *and* thematic coverage, not dominated by any one topic
- Feature extraction cached in `.diary_cache/` (5–10x speedup on reruns)
- **This is a selection step, not a chunking step** — it filters the
  entry list before chunking begins

### Phase 2 — Semantic Chunking (sentence-transformers)

Three strategies, configured via `chunking_strategy`:

| Strategy | Behaviour |
|---|---|
| `sentence_group` (default) | Groups `sentences_per_chunk` (default 4) consecutive sentences per chunk |
| `semantic` | Embeds sentences, detects cosine-similarity drop points, splits at semantic boundaries |
| `hybrid` | Sentence-group with semantic boundary override for long entries |

Each strategy applies a hard `max_chunk_length` cap (default 512 chars)
and filters meaningless fragments.

### Phase 3 — Unsupervised Category Discovery (TF-IDF k-means)

- Vectorises all chunk texts via `TfidfVectorizer` (1000 features,
  1–2-grams, English stopwords)
- Clusters into `n_categories` (default 10) groups via k-means
- Derives human-readable category names from top TF-IDF terms per
  cluster centroid
- **Discovers the topic vocabulary from the corpus itself** — no
  predefined labels required

### Phase 4 — TopicClassifier Refinement (YAML rules, hybrid scoring)

- Loads `topics.yaml` — keyword/phrase rules with confidence weights
- Applies `classify_chunk_hybrid()`: combines k-means cluster assignment
  (Phase 3) with YAML rule scores
- YAML rules take priority when confidence exceeds threshold; k-means
  label used as fallback
- Top topic -> `TYPE` field; sub-topic -> `CATEGORY` field

**Topic types produced** (from `topics.yaml`):

| TYPE | Example CATEGORY |
|---|---|
| `pepys_domestic` | `Home`, `Health`, `Finance` |
| `pepys_naval` | `Navy`, `Ships`, `Fleet` |
| `pepys_political` | `Parliament`, `Crown`, `Council` |
| `pepys_social` | `Entertainment`, `Friends`, `Theatre` |
| `pepys_religious` | `Church`, `Worship` |
| `pepys_travel` | `Locations`, `Thames`, `Westminster` |
| `pepys_emotional` | `Personal`, `Anxiety`, `Joy` |

### Phase 5 — EntryChunk Output

- Produces `EntryChunk` objects with `timestamp`, `semantic_category`,
  `context_classification`, `content`, `topics` (scored dict)
- Written as pipe-delimited format: `TIMESTAMP | TYPE | CATEGORY | CONTENT`
- The `entry_type | category |` prefix is **preserved in the embedding
  input string**, encoding topic signal directly into the vector

```bash
# Via CLI (DocKG-compatible corpus output)
poetry run diary-transformer ingest \
    pepys/pepys_clean.txt \
    pepys/pepys_corpus/ \
    --topics pepys/topics.yaml \
    --workers 4

# Via example script (flat enriched file output)
poetry run python pepys/diary_transformer_example.py \
    --input  pepys/pepys_clean.txt \
    --output pepys/pepys_enriched_full.txt \
    --topics pepys/topics.yaml \
    --workers 4
```

---

## Stage 3 — Embed: `benchmarks/pepys_embedder.py`

**Input:** `pepys/pepys_enriched_full.txt`
**Output:** `benchmarks/pepys_embeddings.json`

Multi-process sentence-transformers ingestion.  Each worker loads its own
`SentenceTransformer` instance and encodes a shard independently via
`multiprocessing.Pool`.

| Property | Value |
|---|---|
| Model | `nomic-ai/nomic-embed-text-v1` |
| Dimension | 768 |
| Task prefix | `search_document: TYPE | CATEGORY | content` |
| Full corpus | 3355 entries -> ~5000–8000 chunks (varies by strategy) |
| Parallelism | `--workers` (default: `os.cpu_count()`) |
| Batch size | `--batch-size` (default: 64) |

```bash
# Full corpus
python benchmarks/pepys_embedder.py --init

# Temporally sampled subset (1000 entries, evenly spaced 1660–1669)
python benchmarks/pepys_embedder.py --init --n 1000

# Custom paths / model
python benchmarks/pepys_embedder.py --init \
    --diary  pepys/pepys_enriched_full.txt \
    --output benchmarks/pepys_embeddings.json \
    --workers 8 \
    --batch-size 128
```

### Temporal sampling

`--n` does **not** head-slice; it picks entries evenly across the full
date range:

```python
indices = [round(i * (total - 1) / (n - 1)) for i in range(n)]
```

This guarantees the subset spans 1660–1669.  Because each entry then
splits into multiple chunks, the resulting embedding matrix has more
rows than `n`.

### Cache format (`benchmarks/pepys_embeddings.json`)

```json
{
  "embeddings": [[0.12, -0.04, ...], ...],   // float32, shape (N_chunks, 768)
  "texts":      ["pepys_domestic | Home | ...", ...],
  "timestamps": ["1660-01-01T00:00:00", ...]
}
```

---

## Stage 4 — Analyse: `benchmarks/pepys_manifold_explorer.py`

**Input:** `benchmarks/pepys_embeddings.json`

Loads the cache, applies optional temporal subsampling, then runs:

- **Intrinsic dimensionality:** PCA elbow (90/95/99%), Participation Ratio, TwoNN estimator
- **MRL truncation quality:** MRR@10 at 64/128/256/512/768 dims with Pepys-specific queries
- **ManifoldWalker flight:** origin -> destination in 768-D cosine space
- **ManifoldObserver:** lifts one orthonormal dimension above the manifold to observe
  curvature, topology, and category boundaries globally

```bash
# Full corpus from cache
python benchmarks/pepys_manifold_explorer.py

# Temporally sampled subset
python benchmarks/pepys_manifold_explorer.py --n 500
```

---

## End-to-End Quickstart

```bash
# 1. Parse raw diary -> 3355 timestamped entries
python pepys/pepys_proper_parse.py \
    raw_pepys.txt pepys/pepys_clean.txt

# 2. Enrich: chunk + discover categories + classify topics
poetry run python pepys/diary_transformer_example.py \
    --input  pepys/pepys_clean.txt \
    --output pepys/pepys_enriched_full.txt \
    --workers 4

# 3. Embed (full corpus or temporal subset)
python benchmarks/pepys_embedder.py --init
python benchmarks/pepys_embedder.py --init --n 1000

# 4. Analyse
python benchmarks/pepys_manifold_explorer.py
```

---

## Design Principles

1. **Local NLP, minimise inference.** Every stage — spaCy, sentence-transformers,
   TopicClassifier — runs locally.  No API keys, no network after initial model download.

2. **Cache the expensive steps.** `DiaryTransformer` caches NLP feature extraction
   in `.diary_cache/`; `pepys_embedder.py` writes the final embedding cache.
   Re-runs at any stage are fast.

3. **Temporal diversity by default.** Any `--n` subsample spans the full 1660–1669
   arc; chronological head-slicing is never used.

4. **Chunks != entries.** The enriched corpus has more rows than the source because
   each entry is split at sentence/semantic boundaries.  Downstream code must account
   for this: embedding matrix rows index chunks, not diary entries.

5. **Two-layer classification.** Unsupervised TF-IDF k-means discovers the topic
   vocabulary from the corpus itself.  YAML `TopicClassifier` rules refine the result
   with domain knowledge.  Neither layer alone is sufficient; the hybrid is the system.

6. **Separation of concerns.** Parse -> Enrich -> Embed -> Analyse are independent
   stages with clean file interfaces, making each swappable or re-runnable in isolation.

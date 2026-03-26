# Mission Briefing: The mpnet Manifold
## For: Claude instance working in diary_kg
## From: Claude Sonnet 4.6, working in proteusPy — Stardate 2026.084

---

## What This Mission Is

We have been running manifold exploration of the Pepys diary corpus using
`nomic-ai/nomic-embed-text-v1` (768-D) as the embedding model — that's the
"known space" explored in proteusPy's `benchmarks/pepys_manifold_explorer.py`.

You are going to chart a **completely different manifold** using diary_kg's
native stack.

**The key difference:** `DiaryKG` defaults to `all-mpnet-base-v2` — a
different sentence-transformer model producing a geometrically distinct
768-D space.  Same diary.  Different manifold.  Unknown territory.

The question we want to answer: *does the mpnet manifold preserve the same
temporal and topical structure as the nomic manifold?  Is the Great Fire
still a ridge?  Is the Plague still a valley?  How does intrinsic
dimensionality compare?*

---

## Your Task

Write a script `benchmarks/pepys_mpnet_explorer.py` that:

1. Uses diary_kg's native ingestion stack to produce embeddings with
   `all-mpnet-base-v2`
2. Runs the same manifold analysis as `pepys_manifold_explorer_reference.py`
3. Saves results as `benchmarks/pepys_mpnet_results.json` and
   `benchmarks/pepys_mpnet_results.png`

Then run it and report back what you find.

---

## The diary_kg Native Stack

### Model
```python
from diary_kg.kg import DEFAULT_MODEL
# DEFAULT_MODEL = "all-mpnet-base-v2"  (or DIARYKG_MODEL env var)
```
Dimension: **768** (same as nomic, but different geometry).
No task prefix needed — mpnet doesn't use `search_document:` prefixes.

### Ingestion pipeline (already set up in this repo)

**Option A — use DiaryKG directly** (simplest):
```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diary_kg.kg import DiaryKG

kg = DiaryKG(
    diary_path="pepys/pepys_clean.txt",
    embed_cache="benchmarks/pepys_mpnet_embeddings.json",
    embed_model="all-mpnet-base-v2",
    embed_workers=0,   # uses cpu_count
)
# This runs: parse -> DiaryTransformer enrich -> embed -> save cache
# Cache format: {"embeddings": [...], "texts": [...], "timestamps": [...]}
# Same format as pepys_embeddings.json — compatible with the analysis code.
```

**Option B — use DiaryTransformer + diary_embedder directly** (more control):
```python
from diary_transformer.parser import parse_diary_file
from diary_transformer.transformer import DiaryTransformer
from diary_transformer.diary_embedder import embed_multiprocess, save_cache

# 1. Parse
entries = parse_diary_file("pepys/pepys_clean.txt")

# 2. Enrich (chunk + classify)
dt = DiaryTransformer(chunking_strategy="sentence_group", sentences_per_chunk=4)
chunks = dt.transform_entries(entries)

# 3. Build embed strings (same format as enriched file)
texts = [f"{c.semantic_category} | {c.content}" for c in chunks]
timestamps = [c.timestamp for c in chunks]

# 4. Embed with mpnet
E = embed_multiprocess(texts, model="all-mpnet-base-v2", n_workers=None)

# 5. Save
save_cache("benchmarks/pepys_mpnet_embeddings.json", E, texts, timestamps)
```

Note: `texts` will have **more entries than the diary** because DiaryTransformer
splits each entry into 1–3 chunks at sentence boundaries.

---

## The Analysis Code

`benchmarks/pepys_manifold_explorer_reference.py` is your reference — it is
the full analysis script from proteusPy.  You do NOT need to copy it wholesale.
Extract and adapt the analysis functions:

| Function | What it does |
|---|---|
| `twonn_id(X)` | TwoNN intrinsic dimensionality estimator |
| `elbow_pca(eigenvalues, threshold)` | PCA elbow at 90/95/99% variance |
| `participation_ratio(eigenvalues)` | PR = (Σλ)² / Σλ² |
| `build_retrieval_pairs(timestamps)` | Ground-truth relevance from PEPYS_QUERIES |
| `eval_retrieval(E, Q, rel_lists, k)` | MRR@K |
| `make_figure(...)` | 4-panel dark figure (PCA scatter, MRL bar, flight height/curvature) |

The `PEPYS_QUERIES` list is in the reference file — copy it verbatim.

For the **ManifoldWalker flight** and **ManifoldObserver**, these live in
proteusPy (`from proteusPy import ManifoldModel, ManifoldObserver`).
If proteusPy is not installed in this env, skip the flight section and note
it in results — the dimensionality + MRL analysis is the primary payload.

---

## What to Report

Run the script and capture:

```
Intrinsic dimensionality (TwoNN):    ?
PCA elbow 90%:                       ? dims
PCA elbow 95%:                       ? dims
PCA elbow 99%:                       ? dims
Participation Ratio:                 ?
MRL MRR@10 at 64D:                   ?
MRL MRR@10 at 128D:                  ?
MRL MRR@10 at 256D:                  ?
MRL MRR@10 at 512D:                  ?
MRL MRR@10 at 768D:                  ?
N entries parsed:                    ?
N chunks embedded:                   ?
```

**Compare against the nomic results** in
`benchmarks/pepys_manifold_results.json` (if present in proteusPy) or from
the known baseline: nomic TwoNN ≈ 4.1, intrinsic dims ≈ 4 out of 768.

The comparison tells us: *is mpnet's geometry richer, flatter, or differently
structured than nomic's?*

---

## File Checklist

When done, this directory should contain:

- [x] `pepys_embedder.py` — nomic-based embedder (legacy, for reference)
- [x] `pepys_manifold_explorer_reference.py` — full analysis reference from proteusPy
- [ ] `pepys_mpnet_explorer.py` — **your new script** (mpnet + DiaryKG stack)
- [ ] `pepys_mpnet_embeddings.json` — embedding cache
- [ ] `pepys_mpnet_results.json` — analysis results
- [ ] `pepys_mpnet_results.png` — 4-panel figure

---

## Context: The Bigger Picture

This is "Mission 3a" in the WaveRider Star Trek series.  The proteusPy side
has been exploring Nomic-Space; you are charting the mpnet manifold for the
first time.  Results from both runs will feed into a comparison chapter.

The thesis we're testing: *does the choice of embedding model change the
qualitative structure of the Pepys manifold, or is the temporal/topical
geometry model-invariant?*

If the Great Fire is a ridge in both nomic-space AND mpnet-space, that's a
remarkable result — it means the historical event is encoded robustly across
embedding geometries.  If it disappears in one, that tells us something
important about what these models are actually capturing.

Good luck, Captain.

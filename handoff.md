# Handoff: doc-kg v0.15.8 query-path changes — impact on diary_kg

> From: doc_kg release session, 2026-06-10
> Context: doc-kg v0.15.8 recalibrated the hybrid (dense + BM25) seeding pipeline after
> benchmark-driven fixes. diary_kg copies the v0.15.7-era fusion pattern in
> `_fused_chunk_seeds()` ([src/diary_kg/kg.py:521](src/diary_kg/kg.py#L521)), so the lessons
> apply here — adapted below, with measurements taken against the real Pepys corpus.

## What changed in doc-kg 0.15.8 (summary)

1. **Dual-distance lexical seeds.** A single synthetic rank value for BM25-only seeds is
   wrong in both directions: ranked too strong, lexical results crowd out good dense hits;
   too weak, the exact-phrase hit itself gets buried. doc-kg now ranks a lexical seed
   *itself* just behind the best dense hit while its graph-expansion *neighbourhood*
   inherits a conservative distance. Measured: exact-phrase recall@15 0.367 → 0.667 with
   gold-set cost ≤ 1 pp.
2. **Scope-prefilter wildcard fix.** `_lance_where()` now uses `starts_with()` instead of
   `LIKE` (underscores in path prefixes were wildcards). diary_kg never passes scope
   filters, so this is informational only.
3. **A standard recall benchmark** (`doc_kg/benchmarks/recall_bench.py`) with auto-generated
   exact-phrase queries — no human labeling needed for the benefit-side metric.

## Already done in this session (committed nothing)

- `pyproject.toml`: doc-kg floor raised `>=0.15.6` → `>=0.15.8` (you asked for this).
- `poetry.lock` + venv refreshed; `doc_kg 0.15.8` now installed and verified
  (`search_lexical`, `rebuild_fts`, calibrated constants all present).
- Note: the venv previously had doc-kg **0.15.5**, which has no `search_lexical` at all —
  `_fused_chunk_seeds()` would have raised `AttributeError` at query time in that env.
  The 0.15.8 install resolves this.

## Findings — action recommended

### 1. The Pepys corpus has no FTS index: the lexical channel is dead in production

`.diarykg/graph.sqlite` (18,309 chunks) has **no `nodes_fts` table** — it was built before
doc-kg's FTS landed. `search_lexical()` returns `[]` and every query silently degrades to
dense-only. The entire hybrid feature (commit `9eb4641`) is inactive on the built corpus.

**Fix (one-time, seconds, no re-embedding):**

```bash
.venv/bin/dockg reindex-fts --repo .diarykg/corpus --sqlite .diarykg/graph.sqlite
```

or programmatically: `DiaryKG(...)._load_dockg().store.rebuild_fts()`. New `build()` /
`rebuild_index()` runs get it automatically (doc-kg ≥ 0.15.7 builds FTS in `build_graph()`).
Consider a `diarykg reindex-fts` CLI passthrough so users of existing diaries aren't stranded.

### 2. Once FTS is live, the current fusion scoring has measurable distortions

Probed against the real corpus (FTS built on a temp copy; nothing mutated), replicating
`_fused_chunk_seeds()` exactly (k=8, channels at k×15, score = `max(dense, 0.88 − 0.01·lex_rank)`):

| Query | Lexical hits | Effect on fused top-8 |
|---|---|---|
| `parmazan cheese` (phrase) | 1 | clean win — buried-cheese entry at 0.880, rank 1, zero collateral |
| `his Majesty did with his own hand` (phrase) | 120 (OR fallback) | **5 of dense top-8 evicted** |
| `What did Pepys say about the great fire?` (thematic) | 120 (OR fallback) | **3 of dense top-8 evicted**; top hit (0.880) is a *naval losses* entry, not the Fire |
| `worries about money and household accounts` (thematic) | 120 (OR fallback) | **7 of dense top-8 evicted** |

Two mechanisms, both fixable without touching doc-kg:

- **Membership flooding.** The lexical channel is fetched at `limit=k*15` (120). When the
  exact-phrase match fails, the OR-of-terms fallback returns 120 weak hits on common diary
  words, and RRF's sum rewards any node appearing in *both* channels' long tails — evicting
  most of the dense top-8. doc-kg uses k×3 oversampling for exactly this reason.
  **Recommendation:** drop the lexical limit to `k * 3` (or even `k`).
- **Score inflation.** `_LEXICAL_SEED_BASE_SCORE = 0.88` is the score-space mirror of
  doc-kg's *regressive* 0.12 distance (1 − 0.12), assigned even to OR-fallback hits. A
  rank-0 OR hit outranks every dense hit (real dense scores top out ~0.6–0.75 on this
  corpus) — that's how a naval entry tops the "great fire" query at 0.880.
  **Recommendation (mirror of doc-kg's `self_dist`):** anchor lexical-only scores just
  behind the best dense score instead of an absolute constant:

  ```python
  best_dense = max((1.0 - d for d in dense_dist.values()), default=_LEXICAL_SEED_BASE_SCORE)
  lex_score = best_dense - _LEXICAL_SEED_STEP * (lex_rank[nid] + 1)
  ```

  diary_kg has **no graph expansion** in its query path, so the neighbourhood half of
  doc-kg's dual-distance fix is not needed — the seed-self placement is the whole lesson here.
- Optional, stronger: treat phrase-match and OR-fallback hits differently (the phrase case
  earns top placement; the fallback case shouldn't). doc-kg's `search_lexical()` doesn't
  expose which path matched — either probe with a phrase-only FTS query first from diary_kg,
  or we add a `match_kind` return upstream in doc-kg (happy to, ask).

### 3. Score semantics leak into MCP / federated KGRAG

`query()`/`pack()` scores flow unchanged through `mcp_server.py` and the KGModule adapter
(`module/base.py`). A flat 0.88 for lexical hits will look artificially strong next to other
KGs' genuine cosine scores in `kgrag` federated ranking. The best-dense anchoring in #2
fixes this for free.

### 4. Benchmark before/after (cheap, infrastructure exists)

doc-kg's `benchmarks/recall_bench.py` phrase mode auto-generates exact-phrase queries
(unique-in-book token spans, FTS5-tokenizer-aligned — use `[A-Za-z0-9]+`, *not* a
word-with-apostrophes regex, or phrase queries silently degrade to OR). Porting it to the
diary corpus gives a labeled-data-free regression harness for any seeding change. Suggested
acceptance: phrase recall up vs dense-only; thematic top-8 dense-eviction count near zero.

## Non-issues (checked, no action)

- **Scope pushdown / `_lance_where` fix** — diary_kg never passes `where=` or scope params.
- **`relevance` dict changes in `DocKG.query()`** — diary_kg builds its own result dicts
  from SQLite; it never reads doc-kg's `relevance`.
- **API compatibility 0.15.5 → 0.15.8** — `index.search()` and `store` APIs are
  backward-compatible; the full diary_kg test suite should pass unchanged (mocked fusion
  tests at `tests/test_diary_kg.py:286` don't encode the 0.88 constant's interaction with
  real BM25, which is why the distortions above weren't caught).

## Suggested order of work

1. Backfill FTS on `.diarykg/graph.sqlite` (#1) — activates the feature you already shipped.
2. Apply the two-line scoring change + lexical limit reduction (#2).
3. Re-run the probe queries above (script: ask, or reconstruct from the table) / port the
   phrase benchmark (#4).
4. Release; the pyproject floor + lock changes from this session ride along.

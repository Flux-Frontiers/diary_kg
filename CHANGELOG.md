# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `benchmarks/pepys_mpnet_explorer.py`: manifold exploration script using
  diary_kg's native `all-mpnet-base-v2` embeddings — intrinsic dimensionality
  (PCA elbow, Participation Ratio, TwoNN), MRR@k at 64–768 dims, and
  ManifoldWalker cosine-space navigation; compares mpnet geometry against the
  nomic-embed-text-v1 reference manifold
- `benchmarks/pepys_manifold_explorer_reference.py`: reference manifold
  explorer using `nomic-ai/nomic-embed-text-v1` (768-d), providing a baseline
  for cross-model manifold comparison
- `benchmarks/pepys_embedder.py`: multi-process corpus embedder moved to
  benchmarks, used by both reference and mpnet explorer scripts
- `benchmarks/pepys_mpnet_results.json` / `pepys_mpnet_results.png`: mpnet
  manifold analysis outputs (intrinsic dimensionality, MRR@k, manifold walks)
- `benchmarks/MISSION_BRIEFING.md`: mission brief describing the mpnet vs nomic
  manifold comparison task and diary_kg native stack usage
- `pepys/pepys_diverse_1000.txt`: 1000-entry temporally diverse Pepys sample
  used as embedding and manifold benchmark corpus
- `pepys/pepys_diverse_chunked.txt`: sentence-chunked version of the diverse
  sample, used as direct input to the mpnet embedder
- `pepys/pepys_enriched_full.txt`: full semantically enriched, topic-classified
  corpus output from `DiaryTransformer.ingest_to_corpus` (all 3355 entries,
  chunked to ~5000+ rows)
- `docs/personal_agent_pipeline_article.md` /
  `docs/personal_agent_pipeline_article_internal.md`: comprehensive article on
  the personal agent pipeline architecture covering the full NLP stack
- `diary_embedder.py`: standalone multi-process corpus embedding pipeline using
  `nomic-ai/nomic-embed-text-v1` (768-d) for purely local embedding; temporal
  sampling across the full date range, sharded via `multiprocessing.Pool` where
  each worker loads its own `SentenceTransformer` instance; outputs
  `pepys_embeddings.json` (N × 768 float32) for downstream manifold analysis
- `pepys/nlp_ingestion_workflow.md`: end-to-end NLP ingestion workflow
  documentation updated to reflect new directory structure (`pepys/` vs
  `benchmarks/`), corrected pipeline ASCII diagram, and added note that
  N_chunks > N_entries due to sentence-boundary splitting
- `pepys/COMPLETE_TECHNICAL_ARTICLE.md`: updated with Stage 3 multi-process
  corpus embedding section covering temporal sampling, nomic-embed-text-v1,
  sharded Pool execution, and JSON cache output
- `analysis/diary_kg_analysis_20260324.md`: CodeKG architectural analysis
  snapshot (2026-03-24)
- `.vscode/settings.json`: VSCode pytest integration config

### Fixed
- Ruff lint pass (236 auto-fixed + 17 manual): import ordering, deprecated
  `typing.Dict/List/Optional` → builtin generics + `X | None`, f-string without
  placeholder, ambiguous variable name `l`, unused variables, `UP042` `KGKind`
  now inherits from `StrEnum` instead of `(str, Enum)`
- `src/diary_kg/module/base.py`: added `TYPE_CHECKING` guard importing `Embedder`
  and `SemanticIndex` from `doc_kg.index`; lazy inline imports in `embedder` and
  `index` properties resolve `F821` undefined-name errors
- `src/diary_kg/kg.py`: added `TYPE_CHECKING` import for `DiarySnapshotManager`
  (fixes `F821` on return-type annotation); removed dead `node_count` / `edge_count`
  variables that were assigned but never used
- `tests/test_diary_transformer_cli.py` / `pepys/tests/`: restored `result =`
  capture in `test_dockg_not_found_exits_nonzero` — removed by over-eager
  `F841` fix; other unused `result` assignments correctly dropped
- `tests/test_diary_transformer_cli.py`: removed `mix_stderr=False` from
  `CliRunner()` constructor — argument dropped in Click 8.2

### Changed
- `DiaryTransformer`: replaced all `print()` calls with Rich `Console` output —
  colored status messages, bold counts, and `rich.progress` bars with spinner +
  bar + elapsed time for the segmentation and classification loops
- `docs/COMPLETE_TECHNICAL_ARTICLE.md` /
  `docs/COMPLETE_TECHNICAL_ARTICLE_internal.md`: moved from `pepys/` to `docs/`
  to co-locate all long-form documentation under a single directory
- `pyproject.toml`: added `proteuspy = "^0.99.35"` dependency for shared
  manifold-geometry utilities (TurtleND, ManifoldWalker, TwoNN, MRR) used in
  the benchmark scripts
- `pyproject.toml`: added `pythonpath = ["src"]` to `[tool.pytest.ini_options]`
  so pytest resolves `diary_kg` and `diary_transformer` without installation

- `EntryChunk.topics` field (`Dict[str, float]`): stores topic name → classifier confidence
  score from `classify_chunk_hybrid()`, previously discarded via `_`
- `DiaryKG._inject_topic_edges()`: post-DocKG-build step that walks corpus `.md` files,
  parses `topics:` frontmatter, and upserts classifier-derived `topic` nodes plus
  `HAS_TOPIC` edges (with confidence) into the DocKG graph — idempotent via `INSERT OR REPLACE`
- `DiaryKGAdapter.embedder` and `DiaryKGAdapter.index` lazy-initialised properties,
  mirroring the CodeKG adapter pattern for consistent MCP server integration
- Semantic topic seeding in `ingest_to_corpus`: chunk body now prefixed with
  `[Topics: name, ...]` so DocKG's embedding captures classifier topic context,
  enabling topic-aware vector similarity without explicit graph traversal
- `diarykg install-hooks` CLI command: installs a git pre-commit hook that
  auto-captures metrics snapshots (keyed by tree hash), stages `.diarykg/snapshots/`,
  then delegates to the pre-commit framework for quality checks; supports `--force`
  and `DIARYKG_SKIP_SNAPSHOT=1` escape hatch
- `diary/topics.yaml`: comprehensive topic taxonomy (29 categories) covering general
  topics and Pepys-specific 17th-century categories (naval, court, domestic, social,
  religious, financial, health, locations, weather)
- Full Pepys diary corpus (`diary/pepys_clean.txt`, 3 355 lines) replacing the
  previous small sample file

### Changed
- `DiaryTransformer.transform_entries`: captures full topic confidence dict from
  `classify_chunk_hybrid()` (was discarded with `_`) and stores it on `EntryChunk.topics`
- `DiaryTransformer.ingest_to_corpus`: writes `topics: name:score,...` YAML frontmatter
  field (top 5 by confidence) and prepends `[Topics: ...]` semantic seed to chunk body
- `DiaryKG.build()`: added Step 3 — calls `_inject_topic_edges()` after `dockg.build()`
  to attach classifier topics as graph edges
- `DiarySnapshotManager.load_snapshot()`: accepts `'latest'` as a key alias (resolves
  to the most-recent snapshot by timestamp); backfills `vs_previous` / `vs_baseline`
  deltas for older snapshots that predate persisted delta fields
- CI trigger changed from push/PR on main to `workflow_dispatch` only
- Dependencies: pinned `sentence-transformers ^5.2.0` and added `transformers ^4.57.6`

### Removed
- Stale binary cache (`diary/.diary_cache/diversity_features_31ffa0573c9b.pkl`) and
  small-corpus artefacts (`pepys_clean_small.txt`, `pepys_clean_small_chunks.pkl`)

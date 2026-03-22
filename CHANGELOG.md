# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

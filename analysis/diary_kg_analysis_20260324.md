> **Analysis Report Metadata**
> - **Generated:** 2026-03-24T04:03:36Z
> - **Version:** code-kg 0.9.0
> - **Commit:** e5118b7 (main)
> - **Platform:** Darwin arm64 | Python 3.12.13
> - **Graph:** 8211 nodes · 11576 edges (912 meaningful)
> - **Included directories:** all
> - **Excluded directories:** none
> - **Elapsed time:** 4s

# diary_kg Analysis

**Generated:** 2026-03-24 04:03:36 UTC

---

## Executive Summary

This report provides a comprehensive architectural analysis of the **diary_kg** repository using CodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, key call chains, and code quality signals to guide refactoring and architecture decisions.

| Overall Quality | Grade | Score |
|----------------|-------|-------|
| [F] **Critical** | **F** | 35 / 100 |

---

## Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | 8211 |
| **Total Edges** | 11576 |
| **Modules** | 62 (of 62 total) |
| **Functions** | 199 |
| **Classes** | 128 |
| **Methods** | 523 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 3278 |
| CONTAINS | 850 |
| IMPORTS | 510 |
| ATTR_ACCESS | 2242 |
| INHERITS | 2 |

---

## Fan-In Ranking

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers |
|---|----------|--------|---------|
| 1 | `info()` | pepys/diary_kg/kg.py | **18** |
| 2 | `info()` | src/diary_kg/kg.py | **18** |
| 3 | `stats()` | pepys/diary_kg/kg.py | **16** |
| 4 | `stats()` | src/diary_kg/kg.py | **16** |
| 5 | `_read_config()` | pepys/diary_kg/kg.py | **15** |
| 6 | `_read_config()` | src/diary_kg/kg.py | **15** |
| 7 | `_load()` | src/diary_kg/module/base.py | **13** |
| 8 | `is_built()` | pepys/diary_kg/kg.py | **13** |
| 9 | `is_built()` | src/diary_kg/kg.py | **13** |
| 10 | `classify_chunk()` | src/diary_transformer/classifier.py | **11** |
| 11 | `load_manifest()` | pepys/diary_kg/snapshots.py | **10** |
| 12 | `load_manifest()` | src/diary_kg/snapshots.py | **10** |
| 13 | `_kg()` | pepys/diary_kg/cli.py | **9** |
| 14 | `_kg()` | src/diary_kg/cli.py | **9** |
| 15 | `classify()` | pepys/diary_transformer/topic_classifier.py | **9** |


**Insight:** Functions with high fan-in are either core APIs or bottlenecks. Review these for:
- Thread safety and performance
- Clear documentation and contracts
- Potential for breaking changes

---

## High Fan-Out Functions (Orchestrators)

Functions that call many others may indicate complex orchestration logic or poor separation of concerns.

No extreme high fan-out functions detected. Well-balanced architecture.

---

## Module Architecture

Top modules by dependency coupling and cohesion (showing up to 10 with activity).
Cohesion = incoming / (incoming + outgoing + 1); higher = more internally focused.

| Module | Functions | Classes | Incoming | Outgoing | Cohesion |
|--------|-----------|---------|----------|----------|----------|
| `pepys/tests/test_diary_kg_snapshots.py` | 3 | 9 | 0 | 1 | 0.50 |
| `tests/test_diary_kg_snapshots.py` | 3 | 9 | 0 | 1 | 0.50 |
| `pepys/tests/test_diary_kg_cli.py` | 2 | 9 | 0 | 1 | 0.50 |
| `tests/test_diary_kg_cli.py` | 2 | 9 | 0 | 1 | 0.50 |
| `pepys/tests/test_diary_kg.py` | 0 | 8 | 0 | 1 | 0.50 |
| `tests/test_diary_kg.py` | 0 | 8 | 0 | 1 | 0.50 |
| `pepys/tests/test_diary_transformer_classifier.py` | 0 | 4 | 0 | 1 | 0.50 |
| `tests/test_diary_transformer_classifier.py` | 0 | 4 | 0 | 1 | 0.50 |
| `pepys/tests/test_diary_kg_adapter.py` | 2 | 5 | 0 | 2 | 0.67 |
| `tests/test_diary_kg_adapter.py` | 2 | 5 | 0 | 2 | 0.67 |

---

## Key Call Chains

Deepest call chains in the codebase.

**Chain 1** (depth: 4)

```
analyze → stats → _load_dockg → is_built
```

**Chain 2** (depth: 4)

```
analyze → stats → _load_dockg → is_built
```

---

## Public API Surface

Identified public APIs (module-level functions with high usage).

| Function | Module | Fan-In | Type |
|----------|--------|--------|------|
| `DiaryKG()` | src/diary_kg/kg.py | 56 | class |
| `DiaryKGAdapter()` | src/diary_kg/module/base.py | 36 | class |
| `DiaryEntry()` | src/diary_transformer/models.py | 24 | class |
| `EntryChunk()` | src/diary_transformer/models.py | 14 | class |
| `pack()` | pepys/diary_kg/cli.py | 12 | function |
| `pack()` | src/diary_kg/cli.py | 12 | function |
| `classify_chunk()` | src/diary_transformer/classifier.py | 11 | function |
| `DiaryTransformer()` | pepys/diary_transformer/transformer.py | 9 | class |
| `DiaryTransformer()` | src/diary_transformer/transformer.py | 9 | class |
| `build()` | pepys/diary_kg/cli.py | 4 | function |
---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without
docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where
keyword search is as effective as vector embeddings. The semantic model earns its
value only when a docstring is present.

| Kind | Documented | Total | Coverage |
|------|-----------|-------|----------|
| `function` | 157 | 199 | [WARN] 78.9% |
| `method` | 88 | 523 | [LOW] 16.8% |
| `class` | 31 | 128 | [LOW] 24.2% |
| `module` | 60 | 62 | [OK] 96.8% |
| **total** | **336** | **912** | **[LOW] 36.8%** |

> **Recommendation:** 576 nodes lack docstrings. Prioritize documenting high-fan-in functions and public API surface first — these have the highest impact on query accuracy.

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `codekg centrality --top 25`

| Rank | Score | Members | Module |
|------|-------|---------|--------|
| 1 | 0.098181 | 24 | `src/diary_kg/snapshots.py` |
| 2 | 0.086281 | 23 | `src/diary_kg/kg.py` |
| 3 | 0.066747 | 24 | `pepys/diary_kg/snapshots.py` |
| 4 | 0.046915 | 23 | `pepys/diary_kg/kg.py` |
| 5 | 0.042349 | 9 | `src/diary_transformer/state.py` |
| 6 | 0.037089 | 12 | `src/diary_kg/module/base.py` |
| 7 | 0.035042 | 42 | `pepys/tests/test_diary_kg_cli.py` |
| 8 | 0.035042 | 42 | `tests/test_diary_kg_cli.py` |
| 9 | 0.031219 | 9 | `pepys/diary_transformer/state.py` |
| 10 | 0.029605 | 6 | `src/diary_transformer/classifier.py` |
| 11 | 0.029363 | 48 | `pepys/tests/test_diary_kg_snapshots.py` |
| 12 | 0.029363 | 48 | `tests/test_diary_kg_snapshots.py` |
| 13 | 0.027331 | 3 | `src/diary_transformer/models.py` |
| 14 | 0.021096 | 31 | `pepys/tests/test_diary_transformer_classifier.py` |
| 15 | 0.021096 | 31 | `tests/test_diary_transformer_classifier.py` |



---

## Code Quality Issues

- [LOW] Low docstring coverage (36.8%) — semantic query quality will be poor; embedding undocumented nodes yields only structured identifiers, not NL-searchable text. Prioritize docstrings on high-fan-in functions first.
- [WARN] 6 orphaned functions found (`test_empty_string`, `test_missing_frontmatter_returns_empty`, `test_missing_frontmatter_returns_empty`, `test_empty_string`, `TestParseDiaryFile`, `test_empty_file_returns_empty`) -- consider archiving or documenting

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected
- Multiple inheritance used in 1 class(es) without diamond patterns

---

## Recommendations

### Immediate Actions
1. **Improve docstring coverage** — 576 nodes lack docstrings; prioritize high-fan-in functions and public APIs first for maximum semantic retrieval gain
2. **Remove or archive orphaned functions** — `test_empty_string`, `test_missing_frontmatter_returns_empty`, `test_missing_frontmatter_returns_empty`, `test_empty_string`, `TestParseDiaryFile` (and 1 more) have zero callers and add maintenance burden

### Medium-term Refactoring
1. **Harden high fan-in functions** — `info`, `info`, `stats` are widely depended upon; review for thread safety, clear contracts, and stable interfaces
2. **Reduce module coupling** — consider splitting tightly coupled modules or introducing interface boundaries
3. **Add tests for key call chains** — the identified call chains represent well-traveled execution paths that benefit most from regression coverage

### Long-term Architecture
1. **Version and stabilize the public API** — document breaking-change policies for `DiaryKG`, `DiaryKGAdapter`, `DiaryEntry`
2. **Enforce layer boundaries** — add linting or CI checks to prevent unexpected cross-module dependencies as the codebase grows
3. **Monitor hot paths** — instrument the high fan-in functions identified here to catch performance regressions early

---

## Inheritance Hierarchy

**2** INHERITS edges across **1** classes. Max depth: **0**.

| Class | Module | Depth | Parents | Children |
|-------|--------|-------|---------|----------|
| `KGKind` | src/diary_kg/primitives.py | 0 | 2 | 0 |

### Multiple Inheritance (1 classes)

- `KGKind` (src/diary_kg/primitives.py) inherits from `Enum`, `str`


---

## Snapshot History

Recent snapshots in reverse chronological order. Δ columns show change vs. the immediately preceding snapshot.

| # | Timestamp | Branch | Version | Nodes | Edges | Coverage | Δ Nodes | Δ Edges | Δ Coverage |
|---|-----------|--------|---------|-------|-------|----------|---------|---------|------------|
| 1 | 2026-03-16 21:34:32 | main | v0.1.0 | 8211 | 11576 | 36.8% | — | — | — |


---

## Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `TestParseDiaryFile()` | tests/test_diary_transformer_parser.py | 52 |
| `test_empty_file_returns_empty()` | tests/test_diary_transformer_parser.py | 4 |
| `test_empty_string()` | tests/test_diary_transformer_parser.py | 1 |
| `test_missing_frontmatter_returns_empty()` | tests/test_diary_kg.py | 1 |
| `test_missing_frontmatter_returns_empty()` | pepys/tests/test_diary_kg.py | 1 |
| `test_empty_string()` | pepys/tests/test_diary_transformer_parser.py | 1 |
---

## CodeRank -- Global Structural Importance

Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). Scores are normalized to sum to 1.0. This ranking seeds Phase 2 fan-in discovery and Phase 15 concern queries.

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.000609 | method | `DiaryKGAdapter._load` | src/diary_kg/module/base.py |
| 2 | 0.000508 | method | `DiaryKG._snapshot_mgr` | pepys/diary_kg/kg.py |
| 3 | 0.000508 | method | `DiaryKG._snapshot_mgr` | src/diary_kg/kg.py |
| 4 | 0.000502 | method | `DiaryKG._read_config` | pepys/diary_kg/kg.py |
| 5 | 0.000502 | method | `DiaryKG._read_config` | src/diary_kg/kg.py |
| 6 | 0.000473 | class | `DiarySnapshotDelta` | pepys/diary_kg/snapshots.py |
| 7 | 0.000473 | class | `DiarySnapshotDelta` | src/diary_kg/snapshots.py |
| 8 | 0.000443 | class | `DiarySnapshotManifest` | pepys/diary_kg/snapshots.py |
| 9 | 0.000443 | class | `DiarySnapshotManifest` | src/diary_kg/snapshots.py |
| 10 | 0.000424 | function | `_kg` | pepys/diary_kg/cli.py |
| 11 | 0.000420 | function | `_kg` | src/diary_kg/cli.py |
| 12 | 0.000388 | function | `extract_section` | scripts/generate_wiki.py |
| 13 | 0.000378 | method | `DiarySnapshotManager.load_manifest` | pepys/diary_kg/snapshots.py |
| 14 | 0.000378 | method | `DiarySnapshotManager.load_manifest` | src/diary_kg/snapshots.py |
| 15 | 0.000376 | method | `DiaryKG._load_dockg` | pepys/diary_kg/kg.py |
| 16 | 0.000376 | method | `DiaryKG._load_dockg` | src/diary_kg/kg.py |
| 17 | 0.000374 | function | `is_leap_year` | pepys/pepys_proper_parse.py |
| 18 | 0.000367 | function | `_get_kg` | src/diary_kg/mcp_server.py |
| 19 | 0.000364 | method | `TopicClassifier.classify` | pepys/topic_classifier.py |
| 20 | 0.000364 | function | `cli` | pepys/diary_kg/cli.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.8363 | method | `DiaryKGAdapter._load` | src/diary_kg/module/base.py |
| 2 | 0.7594 | method | `TopicClassifier.load_config` | pepys/topic_classifier.py |
| 3 | 0.7531 | method | `TopicClassifier.load_config` | pepys/diary_transformer/topic_classifier.py |
| 4 | 0.75 | method | `DiaryKGAdapter.__init__` | src/diary_kg/module/base.py |
| 5 | 0.7492 | method | `TopicClassifier.load_config` | src/diary_transformer/topic_classifier.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7222 | method | `StateManager.save` | pepys/diary_transformer/state.py |
| 2 | 0.7199 | function | `display_temporal_distribution` | pepys/analyze_pepys_entities.py |
| 3 | 0.7184 | method | `StateManager.save` | src/diary_transformer/state.py |
| 4 | 0.69 | class | `StateManager` | pepys/diary_transformer/state.py |
| 5 | 0.6842 | class | `StateManager` | src/diary_transformer/state.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | method | `DiaryKGAdapter.query` | src/diary_kg/module/base.py |
| 2 | 0.7456 | function | `query` | src/diary_kg/cli.py |
| 3 | 0.7455 | function | `semantic_score_from_distance` | src/diary_kg/module/types.py |
| 4 | 0.7441 | function | `_chunk_semantic` | src/diary_transformer/chunker.py |
| 5 | 0.7406 | function | `query` | pepys/diary_kg/cli.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7526 | function | `_top_metrics` | scripts/benchmark_embedders.py |
| 2 | 0.6855 | class | `QueryCase` | scripts/benchmark_embedders.py |
| 3 | 0.6623 | class | `DiaryTransformer` | src/diary_transformer/transformer.py |
| 4 | 0.6605 | class | `DiaryTransformer` | pepys/diary_transformer/transformer.py |



---

*Report generated by CodeKG Thorough Analysis Tool — analysis completed in 4.5s*

> **Analysis Report Metadata**
> - **Generated:** 2026-03-27T23:03:32Z
> - **Version:** code-kg 0.10.0
> - **Commit:** 5e33672 (main)
> - **Platform:** macOS 26.4 | arm64 (arm) | Turing | Python 3.12.13
> - **Graph:** 8484 nodes · 9705 edges (852 meaningful)
> - **Included directories:** all
> - **Excluded directories:** none
> - **Elapsed time:** 4s

# diary_kg Analysis

**Generated:** 2026-03-27 23:03:32 UTC

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
| **Total Nodes** | 8484 |
| **Total Edges** | 9705 |
| **Modules** | 53 (of 53 total) |
| **Functions** | 202 |
| **Classes** | 119 |
| **Methods** | 478 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 3241 |
| CONTAINS | 799 |
| IMPORTS | 399 |
| ATTR_ACCESS | 2272 |
| INHERITS | 1 |

---

## Fan-In Ranking

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers |
|---|----------|--------|---------|
| 1 | `info()` | src/diary_kg/kg.py | **18** |
| 2 | `is_meaningless_fragment()` | src/diary_transformer/parser.py | **16** |
| 3 | `_read_config()` | src/diary_kg/kg.py | **14** |
| 4 | `_load()` | src/diary_kg/module/base.py | **13** |
| 5 | `stats()` | src/diary_kg/kg.py | **13** |
| 6 | `parse_args()` | benchmarks/pepys_embedder.py | **13** |
| 7 | `parse_args()` | src/diary_transformer/diary_embedder.py | **13** |
| 8 | `load_manifest()` | src/diary_kg/snapshots.py | **11** |
| 9 | `classify_chunk()` | src/diary_transformer/classifier.py | **11** |
| 10 | `is_built()` | src/diary_kg/kg.py | **10** |
| 11 | `DiarySnapshotDelta()` | src/diary_kg/snapshots.py | **9** |
| 12 | `_kg()` | src/diary_kg/cli.py | **9** |
| 13 | `load_snapshot()` | src/diary_kg/snapshots.py | **8** |
| 14 | `_parse_frontmatter()` | src/diary_kg/kg.py | **8** |
| 15 | `get_previous()` | src/diary_kg/snapshots.py | **7** |


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

**Chain 1** (depth: 3)

```
query → _load → DiaryKG
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
| `DiaryKG()` | src/diary_kg/kg.py | 55 | class |
| `DiaryKGAdapter()` | src/diary_kg/module/base.py | 36 | class |
| `DiaryEntry()` | src/diary_transformer/models.py | 22 | class |
| `is_meaningless_fragment()` | src/diary_transformer/parser.py | 16 | function |
| `EntryChunk()` | src/diary_transformer/models.py | 13 | class |
| `parse_args()` | benchmarks/pepys_embedder.py | 13 | function |
| `parse_args()` | src/diary_transformer/diary_embedder.py | 13 | function |
| `classify_chunk()` | src/diary_transformer/classifier.py | 11 | function |
| `pack()` | src/diary_kg/cli.py | 10 | function |
| `DiarySnapshotDelta()` | src/diary_kg/snapshots.py | 9 | class |
---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without
docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where
keyword search is as effective as vector embeddings. The semantic model earns its
value only when a docstring is present.

| Kind | Documented | Total | Coverage |
|------|-----------|-------|----------|
| `function` | 156 | 202 | [WARN] 77.2% |
| `method` | 59 | 478 | [LOW] 12.3% |
| `class` | 21 | 119 | [LOW] 17.6% |
| `module` | 51 | 53 | [OK] 96.2% |
| **total** | **287** | **852** | **[LOW] 33.7%** |

> **Recommendation:** 565 nodes lack docstrings. Prioritize documenting high-fan-in functions and public API surface first — these have the highest impact on query accuracy.

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `codekg centrality --top 25`

| Rank | Score | Members | Module |
|------|-------|---------|--------|
| 1 | 0.139630 | 24 | `src/diary_kg/snapshots.py` |
| 2 | 0.107052 | 24 | `src/diary_kg/kg.py` |
| 3 | 0.061756 | 9 | `src/diary_transformer/state.py` |
| 4 | 0.039949 | 12 | `src/diary_kg/module/base.py` |
| 5 | 0.038071 | 42 | `pepys/tests/test_diary_kg_cli.py` |
| 6 | 0.038071 | 42 | `tests/test_diary_kg_cli.py` |
| 7 | 0.033830 | 48 | `pepys/tests/test_diary_kg_snapshots.py` |
| 8 | 0.033830 | 48 | `tests/test_diary_kg_snapshots.py` |
| 9 | 0.032667 | 6 | `src/diary_transformer/classifier.py` |
| 10 | 0.031973 | 3 | `src/diary_transformer/models.py` |
| 11 | 0.023219 | 17 | `src/diary_kg/cli.py` |
| 12 | 0.022539 | 38 | `pepys/tests/test_diary_kg.py` |
| 13 | 0.022539 | 38 | `tests/test_diary_kg.py` |
| 14 | 0.022124 | 31 | `pepys/tests/test_diary_transformer_classifier.py` |
| 15 | 0.022124 | 31 | `tests/test_diary_transformer_classifier.py` |



---

## Code Quality Issues

- [LOW] Low docstring coverage (33.7%) — semantic query quality will be poor; embedding undocumented nodes yields only structured identifiers, not NL-searchable text. Prioritize docstrings on high-fan-in functions first.
- [WARN] 6 orphaned functions found (`test_empty_string`, `test_missing_frontmatter_returns_empty`, `test_missing_frontmatter_returns_empty`, `TestParseDiaryFile`, `test_empty_string`, `test_empty_file_returns_empty`) -- consider archiving or documenting

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected

---

## Recommendations

### Immediate Actions
1. **Improve docstring coverage** — 565 nodes lack docstrings; prioritize high-fan-in functions and public APIs first for maximum semantic retrieval gain
2. **Remove or archive orphaned functions** — `test_empty_string`, `test_missing_frontmatter_returns_empty`, `test_missing_frontmatter_returns_empty`, `TestParseDiaryFile`, `test_empty_string` (and 1 more) have zero callers and add maintenance burden

### Medium-term Refactoring
1. **Harden high fan-in functions** — `info`, `is_meaningless_fragment`, `_read_config` are widely depended upon; review for thread safety, clear contracts, and stable interfaces
2. **Reduce module coupling** — consider splitting tightly coupled modules or introducing interface boundaries
3. **Add tests for key call chains** — the identified call chains represent well-traveled execution paths that benefit most from regression coverage

### Long-term Architecture
1. **Version and stabilize the public API** — document breaking-change policies for `DiaryKG`, `DiaryKGAdapter`, `DiaryEntry`
2. **Enforce layer boundaries** — add linting or CI checks to prevent unexpected cross-module dependencies as the codebase grows
3. **Monitor hot paths** — instrument the high fan-in functions identified here to catch performance regressions early

---

## Inheritance Hierarchy

**1** INHERITS edges across **1** classes. Max depth: **0**.

| Class | Module | Depth | Parents | Children |
|-------|--------|-------|---------|----------|
| `KGKind` | src/diary_kg/primitives.py | 0 | 1 | 0 |


---

## Snapshot History

Recent snapshots in reverse chronological order. Δ columns show change vs. the immediately preceding snapshot.

| # | Timestamp | Branch | Version | Nodes | Edges | Coverage | Δ Nodes | Δ Edges | Δ Coverage |
|---|-----------|--------|---------|-------|-------|----------|---------|---------|------------|
| 1 | 2026-03-26 22:22:04 | feat/waverider | 0.10.0 | 8355 | 9607 | 33.7% | -129 | -98 | +0.0% |
| 2 | 2026-03-26 22:21:21 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +0 | +0 | +0.0% |
| 3 | 2026-03-26 22:20:02 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +0 | +0 | +0.0% |
| 4 | 2026-03-26 22:16:26 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +0 | +0 | +0.0% |
| 5 | 2026-03-26 22:15:33 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +0 | +0 | +0.0% |
| 6 | 2026-03-26 22:14:55 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +0 | +0 | +0.0% |
| 7 | 2026-03-26 22:12:27 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +0 | +0 | +0.0% |
| 8 | 2026-03-26 22:11:40 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +0 | +0 | +0.0% |
| 9 | 2026-03-26 22:08:42 | feat/waverider | 0.10.0 | 8484 | 9705 | 33.7% | +273 | -1871 | -3.1% |
| 10 | 2026-03-16 21:34:32 | main | v0.1.0 | 8211 | 11576 | 36.8% | — | — | — |


---

## Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `TestParseDiaryFile()` | tests/test_diary_transformer_parser.py | 49 |
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
| 1 | 0.000583 | method | `DiaryKGAdapter._load` | src/diary_kg/module/base.py |
| 2 | 0.000487 | method | `DiaryKG._snapshot_mgr` | src/diary_kg/kg.py |
| 3 | 0.000485 | method | `DiaryKG._read_config` | src/diary_kg/kg.py |
| 4 | 0.000460 | class | `DiarySnapshotDelta` | src/diary_kg/snapshots.py |
| 5 | 0.000432 | class | `DiarySnapshotManifest` | src/diary_kg/snapshots.py |
| 6 | 0.000403 | function | `_kg` | src/diary_kg/cli.py |
| 7 | 0.000383 | method | `DiarySnapshotManager.load_manifest` | src/diary_kg/snapshots.py |
| 8 | 0.000371 | function | `extract_section` | scripts/generate_wiki.py |
| 9 | 0.000358 | function | `is_leap_year` | pepys/pepys_proper_parse.py |
| 10 | 0.000351 | function | `_get_kg` | src/diary_kg/mcp_server.py |
| 11 | 0.000348 | method | `TopicClassifier.classify` | pepys/topic_classifier.py |
| 12 | 0.000348 | function | `cli` | src/diary_kg/cli.py |
| 13 | 0.000348 | function | `cli` | src/diary_transformer/cli.py |
| 14 | 0.000348 | method | `TopicClassifier.classify` | src/diary_transformer/topic_classifier.py |
| 15 | 0.000344 | method | `DiaryKG._load_dockg` | src/diary_kg/kg.py |
| 16 | 0.000334 | method | `DiarySnapshotManager.load_snapshot` | src/diary_kg/snapshots.py |
| 17 | 0.000307 | method | `DiaryKG.is_built` | src/diary_kg/kg.py |
| 18 | 0.000304 | class | `TopicClassifier` | pepys/topic_classifier.py |
| 19 | 0.000304 | class | `TopicClassifier` | src/diary_transformer/topic_classifier.py |
| 20 | 0.000296 | method | `TemporalFlyer.fly_to` | benchmarks/pepys_temporal_flight.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.8296 | method | `DiaryKGAdapter._load` | src/diary_kg/module/base.py |
| 2 | 0.7585 | method | `TopicClassifier.load_config` | pepys/topic_classifier.py |
| 3 | 0.75 | method | `DiaryKGAdapter.__init__` | src/diary_kg/module/base.py |
| 4 | 0.7483 | method | `TopicClassifier.load_config` | src/diary_transformer/topic_classifier.py |
| 5 | 0.7262 | method | `StateManager.__init__` | src/diary_transformer/state.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7513 | function | `save_cache` | benchmarks/pepys_manifold_explorer_reference.py |
| 2 | 0.7272 | function | `display_temporal_distribution` | pepys/analyze_pepys_entities.py |
| 3 | 0.7251 | method | `StateManager.save` | src/diary_transformer/state.py |
| 4 | 0.7226 | method | `DiaryKG.build` | src/diary_kg/kg.py |
| 5 | 0.69 | class | `StateManager` | src/diary_transformer/state.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7508 | function | `eval_retrieval` | benchmarks/pepys_manifold_explorer_reference.py |
| 2 | 0.7415 | function | `eval_retrieval` | benchmarks/pepys_mpnet_explorer.py |
| 3 | 0.7291 | function | `build_retrieval_pairs` | benchmarks/pepys_manifold_explorer_reference.py |
| 4 | 0.7285 | method | `DiaryKGAdapter.query` | src/diary_kg/module/base.py |
| 5 | 0.7262 | function | `query` | src/diary_kg/cli.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7523 | method | `DiaryKG._inject_topic_edges` | src/diary_kg/kg.py |
| 2 | 0.7381 | method | `TemporalFlyer.fly_step` | benchmarks/pepys_temporal_flight.py |
| 3 | 0.7161 | function | `_top_metrics` | scripts/benchmark_embedders.py |
| 4 | 0.7115 | function | `twonn_id` | benchmarks/pepys_manifold_explorer_reference.py |
| 5 | 0.6997 | function | `twonn_id` | benchmarks/pepys_mpnet_explorer.py |



---

*Report generated by CodeKG Thorough Analysis Tool — analysis completed in 4.9s*

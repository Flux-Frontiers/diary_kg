# Release Notes — v0.93.1

> Released: 2026-06-08

A packaging-correctness release that completes the hybrid-retrieval work shipped
in 0.93.0.

### Changed
- Promoted `doc-kg` to a **core** runtime dependency (previously an optional
  `kgdeps` / `all` extra). Every KG operation — `build`, `reindex`, `query`,
  `pack`, `stats` — requires DocKG via `_load_dockg()`, and DocKG's heavy
  transitive deps (`lancedb`, `sentence-transformers`) are already core, so a
  plain `pip install diary-kg` now yields a fully working package instead of one
  that fails at runtime with `ImportError: doc-kg is not installed`.

### Fixed
- Corrected the `doc-kg` version floor from `>=0.15.0` to `>=0.15.6`. The hybrid
  dense + lexical retrieval added in 0.93.0 calls `GraphStore.search_lexical()`,
  which only exists in doc-kg 0.15.6+; the looser constraint could resolve an
  incompatible doc-kg and break `query()` / `pack()`.

### Included from 0.93.0
- Hybrid dense + lexical (BM25) retrieval for `query()` and `pack()` via
  `DiaryKG._fused_chunk_seeds()` — reciprocal rank fusion of the dense vector
  channel with the FTS5/BM25 lexical channel, so exact-phrase diary queries
  surface the right entry instead of being buried by the embedding model.
  Degrades cleanly to pure dense ranking when `nodes_fts` is absent.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

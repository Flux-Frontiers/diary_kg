# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.97.0] - 2026-08-15

The 3-D visualization stack lands in two phases — geometry first, then a
renderer-agnostic scene — and diary_kg stops shipping its dev tooling in the
wheel. Nothing in the build or query path changes: corpora built under 0.96.0
are still valid, and no rebuild is required.

### Added

- **`viz3d` Phase 1 — the diary loader and both layouts, with no rendering.**
  `loader.py` reads a `.diarykg` graph into the shared `LayoutNode`/`LayoutEdge`
  vocabulary from `kg_utils.viz3d.layout` and recovers the chronology the
  layouts stand on. The date lift is the fiddly part: DiaryKG populates
  `timestamp` only on `kind='chunk'` rows, so an entry — a `document` row with a
  null timestamp — takes its date from the chunks it contains. A graph built
  before that enrichment pass has no column at all, which is handled rather
  than raised. `layout_tree.py` keeps gutenberg_kg's grammar with time in place
  of chapters: trunk → period limb (one per calendar year) → entry cluster →
  chunk leaves, limbs ascending with period order so the tree reads
  bottom-to-top as a life does. `layout_temporal.py` is the analytical
  counterpart: Z scales by date rather than by index, so a silent stretch in the
  diary shows up as a gap. Neither module imports PyVista, so the whole phase is
  testable headlessly.
- **`viz3d` Phase 2 — `scene.py`, a Qt-free scene builder for both modes.** It
  builds actors into a `pv.Plotter` the caller creates and owns: no window, no
  event loop, no Qt import. One composition therefore serves an interactive
  viewer and a headless renderer alike. Tree mode grows the organic skeleton
  from `kg_utils.viz3d.organic` through the chunk positions and sweeps it into
  wood with leaf glyphs for foliage; manifold mode draws points and no wood, and
  can draw `SIMILAR_TO` edges — a 1667 entry echoing 1665 is the long diagonal
  the tree cannot express by construction. Edges of one relation become a single
  line-set actor, so a diary with thousands of entries does not add thousands of
  actors.
- **`tests/test_sdk_contract.py`** asserts the `kgmodule-utils` symbols the
  layouts and scene import, and fails with the fix in the message — naming the
  installed version and the floor that works — instead of leaving an
  `ImportError` to be decoded. It also reports when the SDK resolves to a source
  checkout rather than an installed wheel. This exists because 0.12.0 was
  published without the organic engine the floor implied.
- **CI now verifies the built wheel, not just the source tree.** An "Installed
  CLI" job builds the wheel, installs it into a clean virtualenv with no source
  tree present, and loads every console-script entry point. `lint`, `type-check`
  and `test` all run against `src/` via `pythonpath`, which makes them
  structurally incapable of noticing a broken artifact.

### Changed

- **Dev tooling moved from a `dev` extra to an optional Poetry group**
  (`poetry install --with dev`), so it can no longer be pip-installed and no
  longer ships in the wheel. Verified against the wheel's `METADATA` rather than
  the manifest: `Provides-Extra: viz, viz3d` and no dev tool in `Requires-Dist`.
- **Dependency floors brought current**: `doc-kg>=0.21.2`,
  `kgmodule-utils>=0.13.2` (0.12.1 is the release that actually contains the
  organic tree engine; 0.13.1 is skipped over, since it made
  `SnapshotManager.repo_root` read-only and broke subclasses that assign it),
  `pytest>=9.0.3` for GHSA-6w46-j5rx-g56g, and `ruff` capped at `<0.16` so a
  lock regeneration cannot turn into a linter upgrade.
- The ruff pre-commit hook was pinned at v0.15.13 while the lock resolved
  0.15.22, so the hook and `poetry run ruff` could disagree on formatting.
- Per-file `Last Revision:` headers retired, per the fleet standard adopted
  2026-08-15. `git log -1 --format=%cd -- <file>` is exact and free; the hand-
  maintained field was wrong in 71% of fleet files carrying it.

### Removed

- **The `all` aggregate extra.** It re-listed every dev tool by name, so the
  wheel advertised them as installable regardless of where the dev dependencies
  actually lived. Ask for the feature extras you want (`viz`, `viz3d`).
- The `dev` extra — see the Poetry group above.

### Fixed

- **The viz3d test suite gates on the ability to render, not on `DISPLAY`.**
  Without a display this VTK build does not fail, it aborts the interpreter, and
  a fatal abort takes the whole session down — unrelated tests included.
  `DISPLAY` only correlates with the ability to render: an xvfb server without
  GLX, a stale variable pointing at a dead socket, or a container forwarding X
  with no GL driver all set it and abort anyway. `tests/_render.can_render` now
  performs a minimal off-screen render in a child process and reads the exit
  code, so a crash costs one subprocess instead of the suite. The result is
  cached, so it spawns once per session.
- `test_no_pyvista_imported_by_the_layouts` asserted `"pyvista" not in
  sys.modules`, a global condition the scene suite legitimately violates; it
  passed only by luck of file ordering. It now probes in a subprocess, which is
  what it always meant to check.

## [0.96.0] - 2026-07-31

Two classifier defects, both found while running the sqlite-vec parity control
added in 0.95.0. Neither was cosmetic — both wrote bad data into chunk
frontmatter. Alongside them, the `doc-kg` 0.20.0 floor finally drops LanceDB out
of the install.

**Minor rather than patch:** category names change, so the `category`/`topics`
frontmatter differs on rebuild and retrieval output can shift. Existing corpora
are not byte-comparable across this release; rebuild rather than diff against an
older one.

### Changed

- **`doc-kg` floor lifted to `>=0.20.0`, and the `[sqlite-vec]` extra dropped
  from the requirement.** doc-kg 0.20.0 promotes `sqlite-vec` to a core
  dependency, so the extra is now a no-op — `doc-kg[sqlite-vec]` and `doc-kg`
  resolve to the same install. The requirement is written plainly as
  `doc-kg>=0.20.0`. The 0.94.0 rationale for pinning the extra (doc-kg shipped
  the `sqlite_vec` runtime opt-in, so the pinned backend failed at index-open
  time without it) no longer applies.

### Removed

- **LanceDB is out of the dependency tree.** 0.95.0 noted that no change
  confined to this repo could remove it, because `doc-kg` declared
  `lancedb>=0.29.0` as a *core* dependency. doc-kg 0.20.0 moves it behind a
  `lancedb` extra, which DiaryKG does not request — so relocking drops
  `lancedb` and its subtree (`lance-namespace`,
  `lance-namespace-urllib3-client`, `cachetools`, `decorator`, `deprecation`)
  from `poetry.lock` entirely. This is doc_kg's Phase 4 landing; the retirement
  begun in 0.94.0 is complete.

  Existing virtualenvs keep the stale wheels until they are re-synced — run
  `poetry install --sync` (or rebuild the venv) to actually reclaim the space.

### Fixed

- **Category discovery was nondeterministic, making builds unreproducible.**
  `discover_semantic_categories()` clustered with `KMeans(random_state=None)`,
  which re-initialises randomly on every call. The discovered categories — and
  therefore the `category`/`topics` frontmatter of *every* chunk file — differed
  between builds of an identical corpus.

  Measured: **86 of 818 chunk files (10.5%)** changed content across two
  back-to-back ingests of the same source. Because the frontmatter is part of
  the `.md` body DocKG indexes, this propagated downstream into different chunk
  boundaries, embeddings and BM25 ranks — and so into different query results.

  `random_state` now falls back to a fixed constant; an explicit `seed` still
  wins. Verified: **0 of 818** files differ after the fix.

  Note the contrast with `features.py`'s diversity sampler, which also clusters
  but generates *and reports* a seed when none is supplied, so those runs stay
  reproducible after the fact. Category discovery reported nothing, so an
  affected build could never be reproduced. It fits a model over the whole chunk
  set rather than making a sampling decision, so its randomness served no
  caller.

  Found while running the sqlite-vec parity control, where it first presented as
  a vector-backend regression and was then misattributed to DocKG's chunker —
  see Flux-Frontiers/doc_kg#16, corrected. DocKG was faithfully chunking
  different input.

- **Discovered category names were often garbage, and it reached the data.**
  `_generate_category_name()` fell back to `top_terms[0]` whenever no curated
  mapping matched, so honorifics and narrative filler became category labels. A
  real run produced:

  ```
  spiritual, mr, domestic, social, lord, domestic, day, lord, bed, sir
  ```

  Four useless labels (`mr`, `lord`, `day`, `bed`, `sir`) and two duplicated
  ones. This was **not cosmetic**: `classify_chunk()` routes any chunk that
  misses its keyword rules to `categories[0]`, so a garbage first category was
  written into the `category` frontmatter of a large share of the corpus.

  Naming now prefers the curated mapping, then the first *informative* term —
  skipping known honorifics/address forms and generic temporal or narrative
  filler, and requiring at least 4 characters — and returns `"general"` when
  nothing is usable. The candidate window widened from 5 to 12 terms so a
  cluster dominated by honorifics still has something to fall back on. Only the
  *name* is affected; clustering is untouched.

  Same corpus after the fix: `spiritual, pepys_court, domestic, work, social`.

- **Duplicate category names are now deduplicated.** Several terms share a
  mapping, so distinct clusters resolved to the same label. A duplicate is
  unreachable — `classify_chunk` resolves via
  `next(c for c in categories if label in c)` — so its cluster slot was silently
  wasted. Deduplication preserves discovery order, and when clusters collapse
  the count is reported rather than hidden.

  On the Pepys corpus, 10 clusters yield 5 distinct categories: `_TERM_MAPPINGS`
  resolves many terms onto a handful of labels, so extra clusters cannot receive
  distinct names. Deduplication surfaces that rather than causing it.

## [0.95.0] - 2026-07-31

Removes DiaryKG's remaining LanceDB surface. **No deprecation period** — 0.94.0
already stopped writing a LanceDB store, and this drops the vestigial API that
still named one.

### Removed

- **`KGEntry.lancedb_path`** (`diary_kg.primitives`). Passing it is now a
  `TypeError` rather than a silently-ignored argument. This class is DiaryKG's
  *own* registry record; `kg_rag.primitives.KGEntry` still carries the column
  that spans both backends for un-migrated KG kinds, so construct that directly
  if you need it.

- **The retired-backend kwarg passed to `DocKG`.** 0.94.0 still forwarded it,
  set to the vector file's parent, to keep `SemanticIndex`'s metadata pointing
  inside `.diarykg/`. It is only read for that metadata and for a lazy fallback
  an explicitly pinned backend never reaches, so leaving it at DocKG's default
  is inert — nothing reads it and nothing creates the directory it names.
  `_dockg_vector_kwargs()` is now exactly the pin plus the store path.

- **`.gitignore` rules for `.diarykg/lancedb/`.** Rules for `.dockg/`,
  `.pycodekg/` and `.filetreekg/` are untouched: those are other KGs' stores
  inside this repo, and `.dockg` remains LanceDB-capable until doc_kg's Phase 4.

### Changed

- Prose and test names no longer describe the retired backend as a live option;
  the guard that a pre-0.94.0 store directory does **not** satisfy `is_built()`
  is kept, since it asserts that legacy state is ignored.

### Note on the installed package

This does **not** remove `lancedb` from a `pip install diary-kg`, and no change
confined to this repo can. `doc-kg` declares `lancedb>=0.29.0` as a **core**
dependency, and DiaryKG depends on doc-kg, so the wheel still lands in every
environment. `kgmodule-utils[semantic]` carries it too, though DiaryKG installs
that without extras.

Retiring it from the venv is doc_kg's Phase 4 — the one repo where both backends
are already implemented, and the sole remaining blocker on this axis.

## [0.94.0] - 2026-07-30

Retires LanceDB as DiaryKG's vector store in favour of sqlite-vec — Phase 1 of
the fleet migration tracked in `pycode_kg/MIGRATION-sqlite-vec.md`.

**Breaking:** the vector artifact moves from the `.diarykg/lancedb/` *directory*
to a single `.diarykg/vectors.sqlite` *file*. Existing corpora are not converted
in place; rebuild with `diarykg reindex` (corpus `.md` files are reused, so no
re-ingest is needed). A leftover `lancedb/` directory is now inert and no longer
counts towards `DiaryKG.is_built()` — delete it to reclaim the space.

### Added

- **`vectors.sqlite` is the vector store.** `DiaryKG` pins DocKG's backend to
  `sqlite-vec` at all three construction sites rather than leaving it on the
  `"auto"` default. `auto` resolves per-store from what is on disk, so a stale
  `lancedb/` directory would have silently kept an existing corpus on the
  retired backend — the trap that makes a repo look migrated in code while
  still running LanceDB.

- **`KGEntry.vectors_path`** (`diary_kg.primitives`), mirroring
  `kg_rag.primitives.KGEntry` field-for-field. `diary-transformer build` now
  registers this instead of `lancedb_path`. `lancedb_path` is retained and
  documented as deprecated so pre-0.94.0 registry entries still load.

- **Migration guard tests** (`TestVectorStoreWiring`) asserting the backend is
  pinned rather than inferred, that `vectors_path` is passed explicitly, and
  that the CLI fallback emits `--vectors-path` and never `--lancedb`.

### Changed

- **`DiaryKG._lancedb_dir` → `_vectors_path`**, and the DocKG kwargs are
  centralised in `_dockg_vector_kwargs()` / `_dockg_cli_vector_args()` so the
  three construction sites and two subprocess fallbacks cannot drift apart.

  DocKG's `lancedb_dir` parameter is still passed — it is a pre-migration name
  in `kg_utils` that takes a *directory*, forwarded to `SemanticIndex` for
  metadata and for a lazy LanceDB fallback that an explicit sqlite-vec backend
  never reaches. It receives the vector file's parent (`.diarykg/`), mirroring
  `pycode_kg`'s `SemanticIndex(vectors_path.parent, ...)`. It is not renamed:
  the identifier is real and still load-bearing upstream.

- **`dockg` subprocess fallbacks pass `--vector-backend sqlite-vec
  --vectors-path`** instead of `--lancedb`. `diary-transformer build` pins the
  backend the same way, so its outcome no longer depends on whether a
  `lancedb/` directory happens to exist in the target corpus.

- **CLI labels report the real artifact.** `diarykg build`, `diarykg reindex`
  and `diarykg status` printed a `LanceDB :` path label while writing
  `vectors.sqlite`; they now print `Vectors :`. The `diarykg-mcp` startup banner
  likewise reports `vectors` rather than `lancedb`. (Filed as a cosmetic item in
  the KGRAG TODO.)

- **`doc-kg` floor lifted to `>=0.18.2` and installed with `[sqlite-vec]`.**
  0.18.2 is the release that added `DocKG(vectors_path=...)` and the
  `--vectors-path` CLI option this package now passes. The extra is *not*
  optional here: doc-kg ships the `sqlite_vec` runtime opt-in, so pinning the
  backend without it would fail when the index is opened.

- **`wipe` semantics.** `DiaryKG.build(wipe=True)` and `rebuild_index()` unlink
  the `vectors.sqlite` file instead of `rmtree`-ing a directory.

### Removed

- **Direct `lancedb>=0.29.0` dependency**, and `lancedb` from the package
  keywords.

  Note this does **not** yet remove LanceDB from an install: `doc-kg` still
  hard-requires it (its Phase 4), and `kgmodule-utils[semantic]` still carries
  it, so it continues to arrive transitively. Dropping the direct dependency is
  still correct — it just will not shrink the venv until those land.

- **The `[jupyter]` marker on `pyvista`** (`viz3d` and `all` extras). The extra
  pairs `PyQt5` with `pyvistaqt` — the desktop Qt path — so the notebook stack
  `[jupyter]` pulls in (`trame`, `trame-vuetify`, `jupyter-server`, `nbconvert`,
  `ipywidgets`, `pyzmq`, `tornado`, …) was never reachable. `pyvista` itself is
  unchanged at `>=0.44.0`.

  Note `viz` and `viz3d` remain **declared but unimplemented** — this repo ships
  no visualiser code and no `diarykg-viz*` entry points (cf. the open "visualize
  snapshots in viz3d timeline mode" item in `.github/SNAPSHOTS_CI.md`). The
  extras are left in place as placeholders for that work; only the unusable
  Jupyter half is dropped.

- **The `kgdeps` extra** (`pycode-kg`), and `pycode-kg` from `all`. Nothing in
  `diary_kg` imports it; its only consumer is the git hook generated by
  `diarykg install-hooks`, which shells out to `.venv/bin/pycodekg` and so
  resolves at the venv rather than through this package's dependency graph.

  Declaring it made poetry reconcile its `transformers>=5.5.0,<6` pin against
  this project's on every lock — poetry locks optional groups too, so an extra
  is not free. That is the deadlock `doc_kg` hit when it and `pycode-kg` each
  declared the other; `memory_kg` and `doc_kg` both dropped their sibling extras
  in response, and this follows them. Manual-install instructions replace the
  extra as a comment in `pyproject.toml` and in `README.md`.

  Together these two removals drop **59 transitive packages** from the lock with
  none added.

### Fixed

- **`kgmodule-utils` floor lifted to `>=0.9.0`**; lock regenerated. The floor
  had drifted a release behind the published version, so a fresh install could
  resolve an older shared core than the one this package is tested against.
  Suite green against 0.9.0 (205 passed).

## [0.93.4] - 2026-07-29

### Added

- **Import-level MCP server tests** (`tests/test_mcp_server.py`). `mcp_server.py`
  builds its `FastMCP` instance and registers all three tools at module import,
  so an incompatible `mcp` breaks `diarykg-mcp` at import time — invisibly to
  anyone with a pinned lock file. The tests assert the module imports, that
  `mcp.server.fastmcp` still exists, that the entry point resolves, and that the
  tool count matches the documented surface.

### Changed

- **`mcp` upper-bounded to `<2`.** mcp 2.0 removed the bundled
  `mcp.server.fastmcp` module — FastMCP was split out into the standalone
  `fastmcp` package — so the previously unbounded `mcp>=1.0.0` let a clean
  install from PyPI pull 2.x and break `diarykg-mcp` at import. Lift only
  alongside a port to the standalone package.

- **Dependency floors lifted to the currently published releases** —
  `kgmodule-utils>=0.8.0`, `doc-kg>=0.18.1`, `pycode-kg>=0.20.0`; lock
  regenerated. kgmodule-utils 0.8.0 defaults `vector_backend` to `"auto"`:
  sqlite-vec for fresh or already-migrated stores, LanceDB only when an
  un-migrated store already exists on disk, so existing corpora keep working
  untouched.

### Fixed

### Removed

---

## [0.93.3] - 2026-07-09

### Changed
- Raised the `kgmodule-utils` floor to `>=0.4.6` to pick up the encode-batch
  memory fix, preventing unbounded memory growth during large corpus embedding.
- Packaging hygiene: added the missing `dev` extra, de-duplicated dev
  dependencies, dropped the unused TestPyPI source, and bumped stale pins;
  regenerated `poetry.lock` to match.

### Fixed
- CI: corrected the Poetry install flag from `--only-main` to `--only main` in
  the release workflow.

---

## [0.93.2] - 2026-06-10

### Added
- Backfilled FTS5 lexical index (`nodes_fts`) on the production Pepys corpus.
  The hybrid retrieval feature shipped in 0.93.0 was silently dead on diaries
  built before doc-kg 0.15.7 because `nodes_fts` was never created; running
  `dockg reindex-fts` activates it with no re-embedding.

### Changed
- Raised `doc-kg` floor from `>=0.15.6` to `>=0.15.8` to pick up calibrated
  hybrid-retrieval constants and `rebuild_fts()`.
- Reduced lexical oversampling limit in `_fused_chunk_seeds()` from `k×15` to
  `k×3`. The wider window allowed OR-fallback floods on common diary words to
  evict most of the dense top-k via RRF reward for long-tail membership.
- Anchored lexical-seed scores to `best_dense − step×(rank+1)` instead of the
  hardcoded `_LEXICAL_SEED_BASE_SCORE = 0.88`. The constant outranked every real
  cosine hit (corpus tops out ~0.75) and caused OR-fallback hits to lead results
  for thematic queries. Scores now float with the query, preventing lexical noise
  from evicting strong semantic matches and ensuring scores are comparable across
  KGs in federated KGRAG ranking.

### Fixed
- CI workflow renamed from `publish.yml` → `release.yml`; job id and `name:`
  field updated to match.
- Updated unit test for `_fused_chunk_seeds()` to reflect the new anchored-score
  contract: a buried exact-phrase hit is surfaced into the fused top-k via RRF
  (previously required it to be ranked #1 with score ≥ 0.87).

---

## [0.93.1] - 2026-06-08

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

---

## [0.93.0] - 2026-06-08

### Added
- Hybrid dense + lexical (BM25) retrieval for `query()` and `pack()`. A new
  `DiaryKG._fused_chunk_seeds()` helper blends the dense vector channel with the
  FTS5/BM25 lexical channel via reciprocal rank fusion (`_RRF_K = 60`), so
  exact-phrase diary queries surface the right entry instead of being buried by
  the embedding model. Mirrors doc_kg's DocKG fusion.
- Tests for the fusion helper (`TestFusedChunkSeeds`): lexical rescue of a
  dense-buried exact-phrase hit, and graceful fall-back to pure dense ranking
  when the corpus has no lexical index.

### Changed
- `query()` / `pack()` now read `file_path` from the `nodes` table directly
  rather than relying on the seed hit, since fused seeds are identified by
  node id alone.
- Degrades cleanly to pure dense ranking when `nodes_fts` is absent (diaries
  built before doc-kg 0.15.6).

---

## [0.92.7] - 2026-06-08

### Changed
- Bumped `kgmodule-utils` dependency from `>=0.2.3` to `>=0.4.0`; the new
  release adds shared graph store, semantic index, and pipeline base types
  used by downstream KG modules.
- `poetry.lock` refreshed: `kgmodule-utils` updated to `0.4.2`, `ty 0.0.44`
  added as a transitive dependency of `kgmodule-utils`.
- Replaced `mypy` with `ty` for type checking across the project: `[tool.mypy]`
  removed from `pyproject.toml`, `[tool.ty.environment]` / `[tool.ty.rules]`
  added; `mypy>=1.10.0` dev dependency swapped for `ty>=0.0.44`.
- Pre-commit hook and `ci.yml` type-check job updated to run
  `ty check src/` instead of `mypy src/`.
- `# type: ignore[union-attr]` / `# type: ignore[attr-defined]` comments in
  `module/base.py` and `diary_transformer/features.py` simplified to bare
  `# type: ignore` (mypy-specific codes are not recognised by `ty`).

### Fixed
- Added `.dockg/embeddings.json` to `.gitignore` to prevent the 15 MB
  pre-computed embeddings cache from being tracked by git and tripping the
  pre-commit large-file check (`>2000 KB`).

---

## [0.92.6] - 2026-05-21

### Added
- Brand assets: full logo suite (`assets/logos/logo_{32,64,128,256,512}.png`),
  SVG source (`assets/diarykg_logo.svg`), raster master (`assets/diarykg_logo.png`),
  and badge variants (`assets/badges/badge_{20,40,80,200}.png`).
- `scripts/process_logo.py`: logo post-processing helper (resize, badge generation).
- `pillow >=10.0.0` added to dev dependency group for image processing.
- `README.md`: added `corpus_pepys` exemplar section with Docker workflow and curl example.
- `assets/brands.md`: brand guidelines and logo generation prompt for the DiaryKG family.

### Changed
- `README.md` header logo updated to point to `assets/logos/logo_512.png`.
- CI: push and pull-request triggers added to `ci.yml` (was `workflow_dispatch`-only).
- CI: dev dependencies moved to `[tool.poetry.group.dev.dependencies]` so
  `poetry install` includes them without `--extras dev`; `ci.yml` lint and test
  jobs updated accordingly.

### Fixed
- `TestReindex.test_reindex_success_output_shows_paths`: collapse newlines before
  asserting on path strings so the test passes when CI wraps long tmp-dir paths
  across terminal lines.
- `mypy`: removed `follow_imports` setting that caused mypy to chase into
  third-party packages and fail in CI.

### Removed
- `agent-kg`, `ftree-kg`, `memory-kg` optional dependencies removed from
  `pyproject.toml`; none were imported in source and two were not on PyPI.

---

## [0.92.5] - 2026-05-19

### Fixed
- `kg.py` CLI fallback for `dockg build` used `--db` (removed option) instead
  of `--sqlite`; corrected in both `build()` and `rebuild_index()` paths.
- `kg.py` CLI fallback now passes `--no-similar` to `dockg build` in both
  paths, matching the Python API path (`discover_similar=False`). For
  single-author diary corpora the all-pairs SIMILAR_TO scan produces millions
  of low-signal edges due to author-vocabulary uniformity inflating cosine
  scores; disabling it keeps the index lean and query traversal fast.

---

## [0.92.4] - 2026-04-29

### Added
- `integration` pytest marker registered in `pyproject.toml`; tests that require
  live model downloads (e.g. `test_embedder.py`) should be decorated with
  `@pytest.mark.integration` to be excluded from CI runs automatically.
- `pepys/hindsight_analysis.py`: new hindsight analysis script.

### Changed
- CI test job now runs `pytest -m "not integration"` to skip integration tests
  that require sentence-transformers model downloads, keeping CI fast and
  dependency-free.
- Pre-commit hook template (`diarykg install-hooks`) trimmed to pycodekg + dockg
  only; removed stale codekg, ftreekg, and diarykg snapshot sections. Live hook
  synced to match.
- `transformers` constraint corrected to `>=4.57.6,<5` (was `>=4.40.0,<4.57`,
  which conflicted with `pycode-kg>=0.16.0`).
- `kgmodule-utils` minimum version bumped to `>=0.2.3` (upstream).
- `poetry.lock` refreshed: `doc-kg` 0.12.3, `gitpython` 3.1.49, `transformers`
  4.57.6; `httptools` 0.7.1 and `itsdangerous` 2.2.0 added as transitive deps.
- DocKG and PyCodeKG snapshots updated to reflect current codebase state.

---

## [0.92.3] - 2026-04-29

### Added
- `diarykg snapshot save -v/--version` and `-l/--label` flags: explicit
  documentation in command help text and the module docstring. The help text
  now states that `version` is an option (not a positional) and that bare
  positional arguments are treated as `ROOT`.
- README: expanded Python API surface example covering `DiaryKG.query()`,
  `pack()`, `info()`, `stats()`, `analyze()`, and `snapshot_save/list/show/diff`.

### Changed
- `README.md`: full rewrite to match DiaryKG's actual CLI surface and
  architecture; removed legacy CodeKG fork content (3D visualizer sections,
  `codekg viz/viz3d/viz-timeline/architecture/centrality` examples,
  installer-script docs that don't apply); restructured around the real
  `diarykg build/query/pack/analyze/snapshot/install-hooks` commands and the
  separate `diarykg-mcp` entry point
- `src/diary_kg/cli.py`: install-hooks pre-commit template now invokes
  `pycodekg` (was `codekg`) and stages `.pycodekg/snapshots/`; the
  `pycodekg snapshot save` call now passes the required `VERSION` positional
  read from `pyproject.toml`, fixing a previously silent failure where the
  snapshot was skipped on every commit
- `.github/SNAPSHOTS_CI.md`: programmatic-API example now uses
  `DiaryKG.snapshot_list/show/diff` (was a direct
  `code_kg.snapshots.SnapshotManager` import that no longer exists in this
  project)
- `.claude/commands/release.md`: Step 4c analysis now uses `pycodekg analyze`
  and stages `.pycodekg/`; version-badge URL and `__init__.py` path corrected
  from `src/code_kg/` to `src/diary_kg/`
- `.claude/commands/setup-diarykg-mcp.md`: install/version probes now use
  `diary-kg`/`diary_kg` instead of `code-kg`/`code_kg`; stats snippet imports
  `from diary_kg import DiaryKG`
- `.claude/commands/sync-mcp-docs.md`: source-of-truth path updated to
  `src/diary_kg/mcp_server.py`; skill paths updated to `.claude/skills/diarykg/`
- `.claude/skills/publish/SKILL.md`: rewritten for the `diary-kg` release
  workflow; `DIARYKG_SKIP_SNAPSHOT` replaces `CODEKG_SKIP_SNAPSHOT`;
  post-release guidance covers both `pycodekg snapshot save` and
  `diarykg snapshot save`
- `.claude/skills/kgrag*` and `.claude/skills/new-kg-module/SKILL.md`:
  bulk-renamed `codekg`/`code-kg`/`CodeKG`/`code_kg`/`CODEKG_*` to
  `pycodekg`/`pycode-kg`/`PyCodeKG`/`pycode_kg`/`PYCODEKG_*` so the federated
  KG documentation reflects the tools this project actually uses
- `.pre-commit-config.yaml`: dropped `\.codekg/.*` from the detect-secrets
  exclusion list (project no longer produces that directory)
- `scripts/benchmark_embedders.py`: import switched from `code_kg.CodeKG` to
  `pycode_kg.PyCodeKG`; default SQLite/LanceDB paths moved from `.codekg/` to
  `.pycodekg/`; build hint updated to `pycodekg build --repo . --wipe`
- `scripts/generate_wiki.py`: GitHub repo slug, wiki header/logo title, and
  Python-API section updated from `code_kg`/CodeKG to `diary_kg`/DiaryKG
- `src/diary_kg/{kg,snapshots,module/__init__,module/base,module/types}.py`:
  dropped "mirrors code_kg" / "matches code_kg" docstring references that no
  longer reflect the project's structure
- `pyproject.toml`, `src/diary_kg/__init__.py`: version bumped 0.92.2 → 0.92.3

### Fixed
- `diarykg snapshot save "<VERSION>"` previously failed with
  `Error: DiaryKG is not built. Run build() first.` because Click bound the
  version string to the positional `ROOT` argument, resolving it to a
  non-existent directory. Help text and module docstring now make clear that
  `-v/--version` is the option to use, and bare positionals are treated as
  `ROOT`.

### Removed
- `.claude/skills/codekg/` (`SKILL.md` + `clinerules.md`) and
  `.claude/skills/codekg-thorough-analysis/SKILL.md`: stale upstream-tool
  skills documenting the `codekg` CLI. The project uses `pycodekg`; both
  skills remain available globally in `~/.claude/skills/`.
- `docs/ADAPTER_SPEC.md`: cross-KG adapter specification left over from the
  CodeKG fork; no longer authoritative (KGRAG reference docs in
  `.claude/skills/kgrag/references/` cover the federated query layer).

---

## [0.92.2] - 2026-04-28

### Added
- `diarykg reindex` CLI command: rebuilds the LanceDB + SQLite index from the
  existing corpus without re-running ingest — useful after changing embedding
  models or fixing index bugs; exits non-zero on `FileNotFoundError` or
  unexpected errors
- `DiaryKG.rebuild_index()`: wipes only the index (lancedb + sqlite), then
  re-runs DocKG build with `wipe=True` and `discover_similar=False`; injects
  topic edges and enriches chunk metadata afterward
- `kg_utils.embedder.wrap_embedder()`: wraps a live `SentenceTransformer`
  instance as an `Embedder` so `DiaryKG.build()` can share the model already
  loaded by `DiaryTransformer`, preventing a second MPS allocation during build
- `diary_embedder.save_cache()`: streaming row-by-row JSON serialisation
  avoids a ~750 MB memory spike when materialising large embedding arrays

### Changed
- `src/diary_kg/kg.py`: `DiaryKG.build()` now passes `wipe=True` to every
  `dockg.build()` call; `wipe=False` generated a 1024-clause OR-delete
  predicate that recursed 666 levels in LanceDB's Rust evaluator, overflowing
  the tokio worker-thread stack and causing SIGBUS on macOS
- `src/diary_kg/kg.py`: `DiaryKG.build()` creates a `shared_embedder` via
  `wrap_embedder(dt.sentence_model, self._model)` and passes it to `DocKG`
  to avoid loading a second `SentenceTransformer` on MPS while the first is
  still live; `embed_model` default changed from
  `"nomic-ai/nomic-embed-text-v1"` to `DEFAULT_MODEL` (`"BAAI/bge-small-en-v1.5"`)
- `src/diary_transformer/diary_embedder.py`: `_embed_shard` replaced 10-line
  manual ST load with `load_sentence_transformer(model_id)` from
  `kg_utils.embedder`; removed `_local_model_path()` (function lives in
  `kg_utils.embed.resolve_model_path`); `DEFAULT_OUTPUT` renamed to
  `pepys_bge_embeddings.json`; `OMP_NUM_THREADS` and `TOKENIZERS_PARALLELISM`
  set before spawning worker pool to prevent thread-count explosion + SIGBUS
- `src/diary_transformer/diary_embedder.py`: `DEFAULT_MODEL` now imported from
  `kg_utils.embed`; docstring example updated to `BAAI/bge-small-en-v1.5`
- `src/diary_kg/snapshots.py`: `DiarySnapshotManager` refactored to subclass
  the new `kg_utils.snapshots.SnapshotManager` base class; removed 100+ lines
  of duplicated dataclass/manifest code; `DiarySnapshot*` dataclasses removed
  (now `kg_utils.snapshots.Snapshot`)
- `.github/workflows/publish.yml`: added `poetry publish` step before GitHub
  release creation; fixed release title from "CodeKG" to "DiaryKG"
- `.claude/commands/release.md`: updated CodeKG build command to use new
  `pycodekg build --repo .` CLI
- `.claude/skills/dockg/SKILL.md`: updated to reflect `--update` flag
  replacing `--wipe`; added multipass pipeline docs; corrected model tables
- `pyproject.toml`: version bumped to `0.92.2`; header updated; install
  quick-reference expanded; `kgdeps` extra documented

### Fixed
- SIGBUS (Bus Error 10) on Apple Silicon during `diarykg reindex`: root cause
  was `dockg.build(wipe=False)` generating a 1024-clause OR-delete predicate
  that caused a 666-deep recursion in LanceDB's Rust predicate evaluator,
  overflowing the tokio worker-thread stack guard page; fix is `wipe=True`

### Added
- `CITATION.cff`: GitHub/Zenodo software citation metadata (CFF 1.2.0) — enables
  `Cite this repository` button and `@software` BibTeX export for academic referencing
- `README.md`: Zenodo DOI badge linking to archived releases

### Changed
- `pyproject.toml`: `kg-utils` (git URL) replaced by `kgmodule-utils = "^0.2.0"` (PyPI
  release) — package was renamed on PyPI; `commit.txt` added to `.gitignore`
- `src/diary_kg/kg.py`: `DiaryKG.__init__` now resolves model short aliases via
  `KNOWN_MODELS.get(model, model)` so callers can pass `"bge-small"` instead of the
  full HuggingFace ID; `KNOWN_MODELS` imported alongside `DEFAULT_MODEL` from
  `kg_utils.embed`
- `pyproject.toml`: `pycode-kg` switched from git URL to PyPI release (`>=0.16.0`),
  matching `doc-kg` and the pattern used in kgrag
- `src/diary_transformer/diary_embedder.py`: wired `_embed_shard` to the shared
  `kg_utils.embed` model cache — added `_local_model_path()` helper using
  `resolve_model_path` with `.diarykg/models` as the project-local fallback; `_embed_shard`
  now uses a 3-step load sequence (local cache path → `local_files_only=True` → download)
  matching the doc_kg pattern; `trust_remote_code` derived from model name instead of
  hardcoded `True`
- `pyproject.toml`: version bumped 0.91.1 → 0.92.0; `doc-kg` switched from git URL to
  PyPI release (`>=0.12.0`); `kg-utils` added as an explicit core dependency; added
  install quick-reference comment block
- `src/diary_kg/kg.py`: `DEFAULT_MODEL` now re-exported from `kg_utils.embed` (shared
  constant, removes local `os.environ` lookup); fixed hit-score formula from
  `1 - d²/2` → `1 - d` (correct cosine-distance → similarity mapping); removed unused
  `os` import
- `.pre-commit-config.yaml`: moved `ruff` and `detect-secrets` hooks before local hooks;
  `ruff`/`ruff-format` now run with `always_run: true` and `pass_filenames: false`;
  expanded `detect-secrets` exclusion list to cover `.filetreekg/` and `.pycodekg/`
  snapshot directories (SHA tree hashes flagged as false-positive secrets)
- `.claude/commands/`: renamed `codekg.md` → `pycodekg.md` to align with updated
  PyCodeKG skill name
- `README.md`: version badge corrected from placeholder `0.1.0` to `0.91.1`

### Added
- `benchmarks/pepys_ch5_flight.py`: WaveRider Chapter 5 experiment — destination-relative
  temporal encoding; appends `abs(fyear_i − fyear_dest)` as the temporal axis so the
  destination has coordinate 0 and the KNN graph acts as a gravitational attractor;
  full hop log with running Kendall τ and mission data appendix
- `benchmarks/pepys_temporal_flight_results.png`,
  `benchmarks/pepys_temporal_flight_negated.png`: 8-panel (2×4) temporal flight result
  figures for standard and τ-negated runs
- `benchmarks/pepys_mpnet_embeddings_run_summary.md`: run summary for full-corpus
  mpnet embedding (7,282 entries × 768 dims, 33.6 s on Apple Silicon)
- `docs/PIPELINE_TECHNICAL_DISCLOSURE.md`: technical disclosure document covering the
  full offline semantic pre-computation pipeline — DiaryTransformer enrichment,
  multi-process embedding, KG build, manifold analysis, and temporal flight primitives;
  validated metrics on the full 9-year Pepys corpus
- `analysis/diary_kg_analysis_20260327.md`: CodeKG architectural analysis snapshot
  (8,484 nodes, 9,705 edges, 33.7 % docstring coverage, SIR ranking)
- `pepys/pepys_only_topics.yaml`: topics-only YAML derived from the full Pepys corpus
  classification run
- `pepys/pepys_enriched_full_run_summary.md`: run summary for the full enriched-corpus
  ingest pass
- `diary-embedder` CLI entry point: `diary_transformer.diary_embedder:main` — installs
  as `diary-embedder` command; `benchmarks/pepys_embedder.py` reduced to a thin shim
  that delegates here

### Changed
- `pyproject.toml`: version bumped 0.9.0 → 0.91.0; added `diary-embedder` entry point
- `benchmarks/pepys_embedder.py`: replaced 352-line standalone implementation with a
  27-line shim; all logic lives in `diary_transformer.diary_embedder`
- `benchmarks/pepys_mpnet_explorer.py`: replaced `DiaryTransformer`-based ingestion
  with raw `parse_diary` / `temporally_sample` from `diary_transformer.diary_embedder`
  (consistent format with embedder cache); added `flight_obs` parameter to `make_figure`
  so panels 3 & 4 render observer height and curvature when a flight is available;
  added NaN/Inf guard before L2-normalisation; changed default diary to
  `pepys_enriched_full.txt`; added proteusPy repo-root path injection; changed
  terminology from "chunks" to "sentences"
- `benchmarks/pepys_temporal_flight.py`: added fourth flight mode `temporal_backward`
  (reversed KNN walk for τ-reversal symmetry test); figure expanded from 6-panel (2×3)
  to 8-panel (2×4); added `--negate-time` flag; added τ-reversal symmetry console
  output; fixed `turtleND.py` path to `proteusPy/proteusPy/turtleND.py`; default
  cache changed to `pepys_mpnet_embeddings.json`
- `.diarykg/config.json`: updated source to `pepys/pepys_enriched_full.txt`; chunk
  count updated to 6,647 (full 9-year Pepys corpus)
- `.gitignore`: added `.diarykg/corpus/`, `pepys/*.pkl`, `pepys/.diary_cache`

### Removed
- `benchmarks/pepys_mpnet_results.json`, `benchmarks/pepys_mpnet_results.png`: stale
  results from previous smaller-corpus run; regenerated as temporal flight figures

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

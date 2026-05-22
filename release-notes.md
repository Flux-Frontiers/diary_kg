# Release Notes — v0.92.6

> Released: 2026-05-21

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

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

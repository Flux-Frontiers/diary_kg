# Release Notes — v0.92.7

> Released: 2026-06-08

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

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

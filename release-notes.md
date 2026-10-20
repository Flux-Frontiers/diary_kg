# Release Notes -- v0.100.1

> Released: 2026-10-20

### Fixed

- **PDF ingest on a fresh install.** The lock moves to kgmodule-utils 0.27.1
  and doc-kg 0.28.1. kgmodule-utils 0.27.0's `[pdf]` extra declared
  `pymupdf4llm>=1.28.2`, which now resolves to the empty pymupdf4llm 2.0
  placeholder and installs no PDF code; 0.27.1 declares `pymupdf>=2.0`,
  whose wheel ships the `pymupdf4llm` module. Floors are unchanged.

### Changed

- **Dependencies refreshed to clear 21 Dependabot alerts**: pyjwt 2.15.1,
  urllib3 2.8.0, virtualenv 21.14.11 (dev), all transitive.
- **Fleet packages relocked** to kgmodule-utils 0.27.0 and doc-kg 0.28.0
  before the 0.27.1 fix above.
- **Benchmarks import `TurtleND` from `turtlend`** instead of loading
  `turtleND.py` by path from a sibling proteusPy checkout (#33). diary_kg's
  own dependencies are unchanged.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

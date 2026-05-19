# Release Notes — v0.92.5

> Released: 2026-05-19

Patch release fixing two bugs in the `dockg` CLI fallback path used when
`doc_kg` is not importable directly.

## Fixes

- **`--db` → `--sqlite`** — the `dockg build` CLI removed the `--db` flag;
  the fallback in `build()` and `rebuild_index()` now uses `--sqlite`.
- **`--no-similar` added to CLI fallback** — the Python API path already passed
  `discover_similar=False`; the subprocess fallback now matches. Disabling the
  all-pairs SIMILAR_TO scan is correct for single-author diary corpora where
  vocabulary uniformity inflates cosine scores and produces millions of
  low-signal edges.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

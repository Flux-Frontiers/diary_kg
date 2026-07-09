# Release Notes — v0.93.3

> Released: 2026-07-09

A maintenance release focused on dependency and packaging hygiene. The headline
fix raises the `kgmodule-utils` floor to pick up an encode-batch memory fix, so
embedding large diary corpora no longer risks unbounded memory growth.

## What changed

**Embedding memory fix.** DiaryKG now requires `kgmodule-utils>=0.4.6`, which
corrects memory accumulation in the batched encoder. Builds and re-indexes over
large corpora stay within a bounded memory footprint.

**Packaging cleanup.** The `dev` extra that had gone missing is restored,
duplicate dev dependencies are collapsed, the unused TestPyPI source is removed,
and stale version pins are refreshed. `poetry.lock` was regenerated to match.

**CI fix.** The release workflow's Poetry invocation was using the invalid
`--only-main` flag; it now correctly uses `--only main`.

## Upgrading

No action required — upgrade in place with `pip install --upgrade diary-kg`
(or `poetry update diary-kg`). No data migration or rebuild is needed; existing
knowledge graphs remain compatible.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

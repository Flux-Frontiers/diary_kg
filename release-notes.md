# Release Notes — v0.96.0

> Released: 2026-07-31

DiaryKG's vector store is now SQLite end to end, and LanceDB is gone from the install. On
the way there, the sqlite-vec parity control that verified the migration turned up two
classifier defects that had been quietly writing bad data into chunk frontmatter — both are
fixed here. **Rebuild your corpus after upgrading:** category names change, so frontmatter
and retrieval results shift.

This is the first tagged release since v0.93.4. The 0.94.0 and 0.95.0 changelog entries
describe steps of the same migration that were never cut as their own releases, so everything
below arrives together.

## What changed

**The vector store is `vectors.sqlite`.** DiaryKG pins DocKG's backend to `sqlite-vec` and
writes a single SQLite file inside `.diarykg/` instead of a LanceDB directory. `KGEntry`
carries `vectors_path`; the LanceDB-era `lancedb_path` argument was removed outright, with no
deprecation period, and passing it is now a `TypeError`. Anything that constructed a DiaryKG
`KGEntry` with that keyword needs updating — `kg_rag.primitives.KGEntry` still carries the
column spanning both backends if you need it for an un-migrated KG kind.

**LanceDB actually leaves the environment.** Pinning the backend was never enough on its own:
`doc-kg` declared `lancedb` as a core dependency, so the wheel landed in every install
regardless. The `doc-kg>=0.20.0` floor moves it behind an optional extra that DiaryKG does not
request, which drops `lancedb` and its entire subtree from the lock file. Existing
virtualenvs keep the stale wheels until re-synced, so run `poetry install --sync` to reclaim
the space. The same doc-kg release promotes `sqlite-vec` to a core dependency, which is why
the requirement is now a plain `doc-kg>=0.20.0` rather than `doc-kg[sqlite-vec]`.

**Builds are reproducible again.** Category discovery clustered with
`KMeans(random_state=None)`, so an identical corpus produced different categories on every
build. Measured against the Pepys corpus, 86 of 818 chunk files (10.5%) differed between
back-to-back ingests of the same source — and because that frontmatter is part of the body
DocKG indexes, the divergence propagated into chunk boundaries, embeddings, BM25 ranks and
ultimately query results. The seed now falls back to a fixed constant; 0 of 818 files differ
after the fix. This first presented as a vector-backend regression during the parity control
and was briefly misattributed to DocKG's chunker.

**Category names are no longer garbage.** When no curated mapping matched, the namer fell back
to the single top term, so honorifics and narrative filler became labels — a real run produced
`mr`, `lord`, `day`, `bed` and `sir` among its categories, with duplicates. That mattered
beyond appearances: any chunk missing its keyword rules is routed to the first category, so a
junk label was written into a large share of the corpus. Naming now prefers the curated
mapping, then the first genuinely informative term, and falls back to `general`; duplicates
are deduplicated rather than silently occupying an unreachable cluster slot.

## Upgrading

Rebuild. Category names and chunk frontmatter both change, so an existing corpus is not
byte-comparable with one built by an earlier version — rebuild rather than diff against it.
Delete the old `.diarykg/lancedb/` directory if one is still lying around; nothing reads it,
and a pre-0.94.0 store directory deliberately does not satisfy `is_built()`.

If you construct `diary_kg.primitives.KGEntry` yourself, replace `lancedb_path` with
`vectors_path`. Otherwise there are no API changes and no new configuration to set.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

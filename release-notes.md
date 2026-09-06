# Release Notes — v0.98.0

> Released: 2026-09-06

Two changes, both about resources and identity: `DiaryKG` can finally be closed,
and its snapshots can finally be named. Neither is visible in normal querying,
and both were invisible failures until something downstream tripped over them.

## What changed

**`DiaryKG.close()`, and the context manager to go with it.** `DiaryKG` holds a
lazily constructed `DocKG` and had no way to release it, so every caller leaked
one SQLite connection per instance with nothing it could do about it from its own
side. `gutenberg_kg` builds one `DiaryKG` per diary on every corpus build and hit
exactly that. `close()` delegates to `DocKG.close()`, guards the case where the
`DocKG` was never constructed, and drops the reference before closing so calling
it twice is a no-op — and it does not end the object's life, since a later
`query()`, `pack()` or `stats()` rebuilds on demand.

`build(wipe=True)` and `rebuild_index()` also close before unlinking now, rather
than after. An open connection to a deleted file keeps the old database alive
behind the new one, so a rebuild in a process that had already queried was
quietly holding two.

**Snapshots can be keyed on a release tag.** `capture_diary()` takes `key` and
`subject`. Until now there was no way to say what a snapshot was of: every diary
snapshot took the base's UTC-timestamp default, which is the right answer for a
corpus and the wrong one for a release, with no way to choose. `subject` records
what was measured — `corpus:pepys`, `repo:diary-kg` — separately from `version`,
which names the measuring tool rather than the thing measured.

**Dependency floors move to `doc-kg>=0.24.1` and `kgmodule-utils>=0.19.0`.**
0.19.0 is where snapshots stopped keying on a git tree hash that was read before
`git add` staged them, so the hash named a tree that was never committed. The
doc-kg floor skips 0.24.0 deliberately rather than by accident of timing: that
release shipped the new key scheme with a `save_snapshot` that dropped the key on
the way to disk, so every snapshot it wrote fell back to a tree hash anyway.

## Upgrading

Nothing to migrate, and no rebuild required. Existing snapshots keep their keys
and stay addressable.

Two things are worth adopting rather than required. Callers holding a `DiaryKG`
for the life of a process should now close it — `with DiaryKG(...) as kg:` is the
short form. And anyone snapshotting at a release should pass the tag explicitly,
`capture_diary(..., key="v0.98.0")`, because an omitted key still means "this is
a corpus, timestamp it".

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

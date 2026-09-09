# Release Notes -- v0.99.0

> Released: 2026-09-08

`diarykg snapshot save -v <tag>` accepted a release tag and filed the snapshot
under a UTC timestamp anyway. Every snapshot this package has written was
timestamp-keyed, whatever version you gave it. That is fixed, the snapshot
manager now sits on the kgmodule-utils 0.20.0 extension points instead of
overriding them, and releases reach PyPI without a manual upload.

## What changed

**The release tag reaches the snapshot key.** The plumbing was in place and
nothing connected it. `capture_diary()` has taken a `key` since 0.98.0, but
`DiaryKG.snapshot_save()` never passed one, so `--version` arrived as the
snapshot's version field and never as its key. `snapshot_save()` now takes `key`
and `subject` and forwards both, and the CLI passes the tag as the key only when
you give `-v` explicitly. The flag's default is the literal `0.1.0`, which names
the measuring tool rather than the corpus and must not become a key; click's
parameter source tells the two cases apart. A corpus carries no tag, so omitting
`-v` still produces a timestamp, which is the correct key for it. `snapshot save`
also gains `--subject`, matching the other fleet modules.

The fleet had this repo recorded as fixed. The 0.98.0 change added the parameter
and stopped, and the test suite passed the whole time; driving the CLI end to end
against a real corpus is what surfaced it. Two regression tests now pin both
directions.

**The snapshot manager configures the base class instead of overriding it.**
kgmodule-utils 0.20.0 exposes the two things `DiarySnapshotManager` had
reimplemented: a `package_name` class attribute replaces `__init__`, and
`dict_metric_deltas = ("topic_counts",)` replaces `diff_snapshots`, with
`timestamp` and `issues_delta` arriving in the base result. The override also
reloaded both snapshot files to build the topic delta, where the base computes it
from metrics it already holds. `capture_diary()` and `_compute_delta_from_metrics()`
stay, because they are domain API rather than boilerplate.

`get_previous()` is gone with them. It resolved an unsaved key to the most
recently saved snapshot so that `capture()` could persist `vs_previous` into the
file, and nothing read the result: every consumer in this repo and the other
eight reaches `vs_previous` through `load_snapshot()`, which computes the delta
on read. The persisted value was also a liability, because "most recently saved"
is not "chronologically previous". A snapshot arriving out of order left the
stored delta stale, and `load_snapshot()` backfills only when `vs_previous` is
`None`, so a wrong stored value suppressed the recompute that would have
corrected it.

**Releases publish to PyPI.** This repo still carried the older 47-line workflow,
which built a wheel and created a GitHub Release but stopped there, so every
upload to the index was manual. That is why diary-kg sat at 0.97.0 on PyPI. The
workflow now stashes the built artifacts and hands them to a `publish` job over
trusted publishing, so the index and the GitHub Release carry byte-identical
files.

## Upgrading

No rebuild. The changes are confined to snapshots and packaging, and existing
`.diarykg` databases are untouched.

The kgmodule-utils floor moves to `>=0.20.0`, and this one is a hard requirement:
against 0.19.x the manager reports itself as `kg-utils` and drops
`topic_counts_delta` from every diff. Reinstall with
`poetry install --with dev --all-extras` to pick it up.

Snapshots written before this release keep their timestamp keys. Nothing rewrites
them, and the delta between two of them is computed on read, so they continue to
diff correctly against tag-keyed snapshots taken from here on.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

# Release Notes -- v0.101.1

> Released: 2026-11-25

DiaryKG 0.101.1 fixes a build that could destroy the index it was meant to
replace. It also brings the Art Techno logo and a current lock.

## What changed

**A failed build no longer wipes the index.** `diarykg build` deleted the
corpus, `graph.sqlite` and `vectors.sqlite` first and loaded spaCy second.
When `en_core_web_sm` was missing, the build exited and left no index at
all. That is how a fleet-wide `kgrag rebuild-indices` run lost two diary
KGs. The build now loads its NLP models before it touches the store, so a
missing model stops it with the old index intact.

**An Art Techno logo.** A pen nib whose breather hole is a die, writing a
line of dated nodes over a clock wave, with the tagline A LIFE, ENTRY BY
ENTRY. `scripts/build_logo.py` draws every size, including the pdoc and
wiki logos, which had been missing. `scripts/process_logo.py`, the old
raster pipeline, is removed.

**README images show on PyPI.** They now use absolute URLs.

**The lock is current.** doc-kg 0.30.0 and kgmodule-utils 0.32.0.

## Upgrading

`pip install -U diary-kg`. Existing indexes stay valid. A build still needs
the spaCy model: `python -m spacy download en_core_web_sm`.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

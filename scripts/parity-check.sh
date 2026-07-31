#!/usr/bin/env bash
#
# parity-check.sh — prove the sqlite-vec migration changed no query results.
#
# This is step 6 of pycode_kg/MIGRATION-sqlite-vec.md, the one thing CI cannot
# do: CI proves the code is self-consistent, not that the new backend ranks a
# real corpus the same way the old one did.
#
# It builds the SAME corpus twice — once with pre-migration code on LanceDB,
# once with current code on sqlite-vec — and diffs the query output. The diff
# must be empty.
#
# Two traps this script exists to avoid, both from the plan's learnings:
#
#   #4  The store already on disk is NOT a valid control. It was built by an
#       older embedder, so comparing against it measures model drift, not
#       backend parity. The control is rebuilt from pre-migration code here.
#
#   #8  An incomplete index flatters the migration. agent_kg's parity run
#       "passed" with better results purely because the LanceDB control was
#       missing 24% of its nodes. Node counts are reconciled before the
#       comparison is trusted.
#
# Usage:
#   scripts/parity-check.sh [--full] [--keep]
#
#   --full   use pepys_enriched_full.txt (6.3 MB) instead of the small sample
#   --keep   leave the worktree and outputs in place for inspection
#
set -euo pipefail

# Last commit before the sqlite-vec migration (diary-kg 0.93.4).
PRE_MIGRATION_REF="${PRE_MIGRATION_REF:-7677431}"

SOURCE="pepys/pepys_clean_small.txt"
KEEP=0
for arg in "$@"; do
  case "$arg" in
    --full) SOURCE="pepys/pepys_enriched_full.txt" ;;
    --keep) KEEP=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d -t diarykg-parity-XXXXXX)"
CONTROL_TREE="$WORK/pre-migration"
CONTROL_OUT="$WORK/control.txt"
AFTER_OUT="$WORK/after.txt"

# A fixed, deliberately varied query set: exact phrases (which exercise the
# lexical channel), thematic queries (dense channel), and proper nouns.
QUERIES=(
  "the theatre"
  "plague in the city"
  "dinner with my wife"
  "the King returned"
  "my Lord and the Navy office"
  "money and accounts"
  "music and singing"
  "a great fire"
)

cleanup() {
  if [[ "$KEEP" -eq 1 ]]; then
    echo "artifacts kept in $WORK"
  else
    git -C "$REPO_ROOT" worktree remove --force "$CONTROL_TREE" 2>/dev/null || true
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# --------------------------------------------------------------------------
# Learning #8 — reconcile the index against SQLite before trusting a control.
# --------------------------------------------------------------------------
check_drift() {
  local root="$1" label="$2"
  python3 - "$root" "$label" <<'PY'
import sqlite3, sys
from pathlib import Path

root, label = Path(sys.argv[1]), sys.argv[2]
db = root / ".diarykg" / "graph.sqlite"
if not db.exists():
    sys.exit(f"[{label}] no graph.sqlite — build failed")

nodes = sqlite3.connect(db).execute(
    "SELECT COUNT(*) FROM nodes WHERE kind='chunk'"
).fetchone()[0]

vectors_file = root / ".diarykg" / "vectors.sqlite"
lancedb_dir = root / ".diarykg" / "lancedb"

indexed = None
if vectors_file.exists():
    try:
        con = sqlite3.connect(vectors_file)
        tbl = con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','vtab') "
            "AND name LIKE '%vec%' LIMIT 1"
        ).fetchone()
        if tbl:
            indexed = con.execute(f"SELECT COUNT(*) FROM {tbl[0]}").fetchone()[0]
    except sqlite3.Error as exc:
        print(f"[{label}] could not count sqlite-vec rows: {exc}")
elif lancedb_dir.exists():
    try:
        import lancedb
        db_ = lancedb.connect(str(lancedb_dir))
        names = list(db_.table_names())
        if names:
            indexed = db_.open_table(names[0]).count_rows()
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] could not count LanceDB rows: {exc}")

print(f"[{label}] chunk nodes in SQLite : {nodes}")
print(f"[{label}] rows in vector index  : {indexed if indexed is not None else 'unknown'}")

if indexed is None:
    print(f"[{label}] WARNING: could not verify index size — treat the result with suspicion")
elif indexed < nodes:
    pct = 100.0 * (nodes - indexed) / nodes if nodes else 0.0
    sys.exit(
        f"[{label}] ABORT: index is missing {nodes - indexed} of {nodes} nodes "
        f"({pct:.1f}%). This is the agent_kg failure mode — an incomplete index "
        "makes any comparison meaningless, and typically in the migration's "
        "favour. Rebuild before trusting this run."
    )
else:
    print(f"[{label}] index is complete")
PY
}

capture() {
  local root="$1" out="$2"
  : > "$out"
  for q in "${QUERIES[@]}"; do
    echo "### QUERY: $q" >> "$out"
    (cd "$root" && "$REPO_ROOT/.venv/bin/diarykg" query "$q" -k 8 --json) >> "$out"
    echo >> "$out"
  done
}

capture_pre() {
  # Same queries, pre-migration code, still pinned to LanceDB.
  local root="$1" out="$2"
  : > "$out"
  for q in "${QUERIES[@]}"; do
    echo "### QUERY: $q" >> "$out"
    (cd "$root" && "${PRE_PY[@]}" query "$q" -k 8 --json) >> "$out"
    echo >> "$out"
  done
}

# --------------------------------------------------------------------------
say "1/5  Building the CONTROL from pre-migration code ($PRE_MIGRATION_REF)"
# --------------------------------------------------------------------------
# A worktree, not a stash or a checkout: this leaves your branches and working
# tree completely untouched while a second copy builds on the old code.
git -C "$REPO_ROOT" worktree add --detach "$CONTROL_TREE" "$PRE_MIGRATION_REF"
cp -r "$REPO_ROOT/pepys" "$CONTROL_TREE/pepys" 2>/dev/null || true

# Run the OLD source against the CURRENT venv rather than building a second
# one. The venv is ~5.6 GB (torch dominates), and none of the heavy
# dependencies differ across the migration — only diary_kg's own code does, and
# PYTHONPATH takes precedence over site-packages. Requires `lancedb` to be
# importable; it still arrives via doc-kg <0.20.0, but once doc-kg 0.20.0 is
# published you must add it explicitly:
#     .venv/bin/pip install lancedb
PRE_PY=("env" "PYTHONPATH=$CONTROL_TREE/src" "$REPO_ROOT/.venv/bin/python"
        "-c" "from diary_kg.cli import main; main()")

if ! "$REPO_ROOT/.venv/bin/python" -c "import lancedb" 2>/dev/null; then
  echo "ABORT: lancedb is not importable in $REPO_ROOT/.venv" >&2
  echo "The control must be built on LanceDB. Install it:" >&2
  echo "    $REPO_ROOT/.venv/bin/pip install lancedb" >&2
  exit 1
fi

# CRITICAL: force LanceDB for the control.
#
# Pre-migration diary_kg passes no vector_backend, so DocKG uses "auto" — and
# on a fresh build with both stores deleted, "auto" resolves to *sqlite-vec*,
# not LanceDB. Without this the "control" would be sqlite-vec, the comparison
# would be sqlite-vec against sqlite-vec, and the check would pass no matter
# what the migration broke. This is the plan's "auto hides the migration" trap
# in its most dangerous form: as a tautology dressed up as a green result.
export DOCKG_VECTOR_BACKEND=lancedb

rm -rf "$CONTROL_TREE/.diarykg/lancedb" "$CONTROL_TREE/.diarykg/vectors.sqlite"
(cd "$CONTROL_TREE" && "${PRE_PY[@]}" build --source "$SOURCE")

# Assert the control really is LanceDB. If auto silently won anyway, every
# downstream number is meaningless.
if [[ ! -d "$CONTROL_TREE/.diarykg/lancedb" ]]; then
  echo "ABORT: control build produced no .diarykg/lancedb — it fell back to" >&2
  echo "sqlite-vec, so the comparison would be sqlite-vec vs sqlite-vec and" >&2
  echo "would pass regardless of correctness." >&2
  exit 1
fi
if [[ -f "$CONTROL_TREE/.diarykg/vectors.sqlite" ]]; then
  echo "ABORT: control build wrote vectors.sqlite; it is not a LanceDB control." >&2
  exit 1
fi
echo "control confirmed on LanceDB (.diarykg/lancedb present, no vectors.sqlite)"

# --------------------------------------------------------------------------
say "2/5  Reconciling the control index against SQLite (Learning #8)"
# --------------------------------------------------------------------------
check_drift "$CONTROL_TREE" "control"

# --------------------------------------------------------------------------
say "3/5  Capturing control query output"
# --------------------------------------------------------------------------
capture_pre "$CONTROL_TREE" "$CONTROL_OUT"

# --------------------------------------------------------------------------
say "4/5  Rebuilding with CURRENT code on sqlite-vec"
# --------------------------------------------------------------------------
unset DOCKG_VECTOR_BACKEND
rm -rf "$REPO_ROOT/.diarykg/lancedb" "$REPO_ROOT/.diarykg/vectors.sqlite"
(cd "$REPO_ROOT" && "$REPO_ROOT/.venv/bin/diarykg" build --source "$SOURCE")
if [[ ! -f "$REPO_ROOT/.diarykg/vectors.sqlite" ]]; then
  echo "ABORT: migrated build produced no vectors.sqlite" >&2; exit 1
fi
check_drift "$REPO_ROOT" "migrated"
capture "$REPO_ROOT" "$AFTER_OUT"

# --------------------------------------------------------------------------
say "5/5  Comparing"
# --------------------------------------------------------------------------
# Before blaming the backend, check the two runs indexed the same corpus.
#
# DocKG's semantic chunker is NOT reproducible: two builds with identical code,
# identical backend and identical input can split a borderline file differently
# (measured 2026-07-31 — 1656 vs 1657 chunks, differing on
# entry_0226_chunk_0.md). A chunk that exists in one run and not the other has
# different text, so a different embedding and a different score — which shows
# up in the diff looking exactly like a backend regression.
#
# Without this step that misattribution is very easy to make, and it points at
# the wrong repo entirely.
python3 - "$CONTROL_TREE" "$REPO_ROOT" <<'PY'
import sqlite3, sys
from pathlib import Path

def chunks(root):
    """Map chunk id -> text. Comparing IDS ALONE IS NOT ENOUGH.

    Measured 2026-07-31: two builds produced identical id sets (1657 == 1657,
    symmetric difference 0) while 57 of those chunks — 3.4% — held DIFFERENT
    TEXT. The chunker can move a boundary without changing the split count, so
    the id survives and the content underneath it does not. An id-only check
    reports "corpora identical" and every downstream difference then gets
    blamed on the backend.
    """
    db = Path(root) / ".diarykg" / "graph.sqlite"
    return dict(sqlite3.connect(db).execute(
        "SELECT id, text FROM nodes WHERE kind='chunk'"))

c, m = chunks(sys.argv[1]), chunks(sys.argv[2])
only_c, only_m = sorted(set(c) - set(m)), sorted(set(m) - set(c))
retext = sorted(k for k in c if k in m and c[k] != m[k])

print(f"control chunk nodes  : {len(c)}")
print(f"migrated chunk nodes : {len(m)}")
print(f"same id, other text  : {len(retext)}")

if not (only_c or only_m or retext):
    print("corpora identical in id AND text — the diff below is the backend")
    sys.exit(0)

print()
print("!! CORPORA DIFFER — the two runs did not index the same text.")
for label, ids in (("only in control", only_c), ("only in migrated", only_m),
                   ("same id, DIFFERENT TEXT", retext)):
    if ids:
        print(f"   {label} ({len(ids)}): {', '.join(ids[:5])}"
              + (" …" if len(ids) > 5 else ""))
print()
print("   This is DocKG chunker nondeterminism, NOT a vector-backend defect.")
print("   A chunk whose text differs has a different embedding and a different")
print("   BM25 rank, so its score moves on the 1e-2 scale — indistinguishable")
print("   from a backend regression unless you check the text.")
print()
print("   Treat ONLY differences on chunks identical in id and text as backend")
print("   evidence. On the 2026-07-31 run that subset agreed to 7.45e-07 —")
print("   6.2x float32 epsilon — across 718 pairs, while all 10 outliers fell")
print("   on divergent-text chunks. Perfect separation.")
PY

if diff -u "$CONTROL_OUT" "$AFTER_OUT" > "$WORK/parity.diff"; then
  echo
  echo "PARITY CONFIRMED — identical ranking and scores across ${#QUERIES[@]} queries."
  echo "The plan's step 6 is satisfied for: $SOURCE"
  exit 0
fi

echo
echo "PARITY FAILED — the diff is not empty:"
echo
head -80 "$WORK/parity.diff"
echo
cat <<'EOF'
Do not dismiss this, and do not ship on it. Read the corpus comparison above
first — if the corpora differ, differences on those node ids are chunker
nondeterminism and prove nothing about the backend.

  * Scores differ only in the 6th-7th decimal, ranking identical → float32
    accumulation-order noise between two vector engines. Benign. Measured
    2026-07-31 at max 5.66e-07 (~4.75x float32 epsilon, ~9.4e-07 relative).

  * Scores differ by roughly a FACTOR OF TWO → a genuine distance-metric
    mismatch (squared-L2 vs cosine), the ftree_kg failure. NOT expected here,
    since both backends in this stack already query with cosine, so seeing it
    means that finding was wrong. Do not merge until it is understood.

  * Results look BETTER after migrating → suspect the control, not the code.
    That is exactly how agent_kg's 24%-incomplete index disguised itself.

  * Ranking differs on lexical-phrase queries only → look at the RRF fusion in
    DiaryKG._fused_chunk_seeds, not at the vector backend.
EOF
KEEP=1
exit 1

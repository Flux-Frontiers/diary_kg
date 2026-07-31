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
    (cd "$root" && diarykg query "$q" -k 8 --json) >> "$out"
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

echo "Installing pre-migration diary-kg (needs lancedb)..."
echo "NB: if doc-kg 0.20.0 is already published, lancedb is no longer a core"
echo "    dependency there — run: pip install 'doc-kg[lancedb]' in that venv."
python3 -m venv "$WORK/venv-pre"
"$WORK/venv-pre/bin/pip" install -q -e "$CONTROL_TREE"

rm -rf "$CONTROL_TREE/.diarykg/lancedb" "$CONTROL_TREE/.diarykg/vectors.sqlite"
PATH="$WORK/venv-pre/bin:$PATH" \
  bash -c "cd '$CONTROL_TREE' && diarykg build --source '$SOURCE'"

# --------------------------------------------------------------------------
say "2/5  Reconciling the control index against SQLite (Learning #8)"
# --------------------------------------------------------------------------
PATH="$WORK/venv-pre/bin:$PATH" check_drift "$CONTROL_TREE" "control"

# --------------------------------------------------------------------------
say "3/5  Capturing control query output"
# --------------------------------------------------------------------------
PATH="$WORK/venv-pre/bin:$PATH" capture "$CONTROL_TREE" "$CONTROL_OUT"

# --------------------------------------------------------------------------
say "4/5  Rebuilding with CURRENT code on sqlite-vec"
# --------------------------------------------------------------------------
rm -rf "$REPO_ROOT/.diarykg/lancedb" "$REPO_ROOT/.diarykg/vectors.sqlite"
(cd "$REPO_ROOT" && diarykg build --source "$SOURCE")
check_drift "$REPO_ROOT" "migrated"
capture "$REPO_ROOT" "$AFTER_OUT"

# --------------------------------------------------------------------------
say "5/5  Comparing"
# --------------------------------------------------------------------------
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
Do not dismiss this, and do not ship on it.

  * Scores differ but ranking matches → a distance-metric mismatch. Expected
    for ftree_kg (squared-L2 vs cosine); NOT expected here, since both backends
    in this stack already query with cosine. If you see it, that finding was
    wrong and needs re-checking before anything merges.

  * Results look BETTER after migrating → suspect the control, not the code.
    That is exactly how agent_kg's 24%-incomplete index disguised itself.

  * Ranking differs on lexical-phrase queries only → look at the RRF fusion in
    DiaryKG._fused_chunk_seeds, not at the vector backend.
EOF
KEEP=1
exit 1

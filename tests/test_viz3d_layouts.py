"""
Phase 1 contracts for the diary 3-D layouts.

Everything here runs over a synthetic SQLite graph and pure geometry: no
PyVista import, no display, no ``.diarykg`` on disk. That is deliberate — the
sibling repo ``_waverider`` has a suite that segfaults on a headless machine
because a module-scope call renders during *collection*, so import-time
rendering is a mistake worth designing against rather than discovering.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# The layouts import the organic engine at module scope, and kgmodule-utils
# 0.12.0 shipped without it. Skip at collection so a stale SDK produces one
# clear diagnosis from tests/test_sdk_contract.py rather than an import error
# cascade from every module that touches viz3d.
pytest.importorskip(
    "kg_utils.viz3d.organic",
    reason="kgmodule-utils >=0.12.1 required: 0.12.0 shipped without the organic engine",
)

from diary_kg.layout_temporal import TemporalLayout, parse_timestamp  # noqa: E402
from diary_kg.layout_tree import DiaryTreeLayout  # noqa: E402
from diary_kg.loader import load_diary_graph, load_entry_times, period_groups  # noqa: E402

_SCHEMA = """
CREATE TABLE nodes (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
  title TEXT, file_path TEXT, text TEXT, timestamp TEXT
);
CREATE TABLE edges (
  src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL,
  PRIMARY KEY (src, rel, dst)
);
"""


def _build_db(path: Path, entries: list[tuple[str, str | None]], chunks_per_entry: int = 2) -> None:
    """
    Write a synthetic diary graph.

    :param path: Database file to create.
    :param entries: ``[(entry id, ISO timestamp or None)]``.
    :param chunks_per_entry: Chunks hung off each entry.
    """
    con = sqlite3.connect(str(path))
    con.executescript(_SCHEMA)
    for eid, ts in entries:
        # Mirrors the real thing: the document's own timestamp stays null and
        # the date lives on the chunks, written by the enrichment pass.
        con.execute(
            "INSERT INTO nodes (id, kind, name, title, timestamp) VALUES (?, 'document', ?, ?, NULL)",
            (eid, eid, eid),
        )
        for c in range(chunks_per_entry):
            cid = f"{eid}:chunk{c}"
            con.execute(
                "INSERT INTO nodes (id, kind, name, text, timestamp) VALUES (?, 'chunk', ?, ?, ?)",
                (cid, cid, f"text of {cid}", ts),
            )
            con.execute("INSERT INTO edges (src, rel, dst) VALUES (?, 'CONTAINS', ?)", (eid, cid))
    con.commit()
    con.close()


@pytest.fixture
def dated_db(tmp_path: Path) -> Path:
    """Three years of entries, every one dated."""
    path = tmp_path / "dated.sqlite"
    _build_db(
        path,
        [
            ("e1", "1665-03-02T09:00"),
            ("e2", "1665-11-19T21:30"),
            ("e3", "1666-09-02T04:00"),
            ("e4", "1667-01-01T12:00"),
        ],
    )
    return path


@pytest.fixture
def undated_db(tmp_path: Path) -> Path:
    """Entries with no timestamps at all."""
    path = tmp_path / "undated.sqlite"
    _build_db(path, [(f"e{i}", None) for i in range(1, 13)])
    return path


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_no_pyvista_imported_by_the_layouts() -> None:
    """
    Phase 1 is headless: importing the layouts must not pull PyVista in.

    Checked in a subprocess rather than against this process's ``sys.modules``.
    A global assertion here would be order-dependent and dishonest — the scene
    suite imports pyvista legitimately, so whether this passed would depend on
    which test file ran first, not on what the layouts import.
    """
    probe = (
        "import sys\n"
        "import diary_kg.layout_tree, diary_kg.layout_temporal, diary_kg.loader\n"
        "print('LOADED' if 'pyvista' in sys.modules else 'CLEAN')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "CLEAN", "importing the layouts pulled PyVista in"


def test_load_diary_graph_reads_nodes_and_edges(dated_db: Path) -> None:
    nodes, edges = load_diary_graph(dated_db)
    assert len([n for n in nodes if n.kind == "document"]) == 4
    assert len([n for n in nodes if n.kind == "chunk"]) == 8
    assert all(e.rel == "CONTAINS" for e in edges)


def test_entry_times_lift_dates_from_chunks(dated_db: Path) -> None:
    """The document row carries no timestamp; the date comes up through chunks."""
    times = load_entry_times(dated_db)
    assert times == {
        "e1": "1665-03-02T09:00",
        "e2": "1665-11-19T21:30",
        "e3": "1666-09-02T04:00",
        "e4": "1667-01-01T12:00",
    }


def test_entry_times_empty_when_undated(undated_db: Path) -> None:
    assert load_entry_times(undated_db) == {}


def test_entry_times_survives_a_graph_with_no_timestamp_column(tmp_path: Path) -> None:
    """A pre-enrichment graph has no column at all; that is ordinary, not an error."""
    path = tmp_path / "old.sqlite"
    con = sqlite3.connect(str(path))
    con.executescript(
        "CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT, title TEXT,"
        " file_path TEXT, text TEXT);"
        "CREATE TABLE edges (src TEXT, rel TEXT, dst TEXT);"
    )
    con.commit()
    con.close()
    assert load_entry_times(path) == {}


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------


def test_one_limb_per_calendar_year(dated_db: Path) -> None:
    nodes, _ = load_diary_graph(dated_db)
    docs = [n for n in nodes if n.kind == "document"]
    groups = period_groups(docs, load_entry_times(dated_db))

    assert [label for label, _ in groups] == ["1665", "1666", "1667"]
    assert [len(m) for _, m in groups] == [2, 1, 1]


def test_undated_falls_back_to_equal_runs(undated_db: Path) -> None:
    nodes, _ = load_diary_graph(undated_db)
    docs = [n for n in nodes if n.kind == "document"]
    groups = period_groups(docs, load_entry_times(undated_db))

    assert len(groups) >= 3
    assert all(label.startswith("part ") for label, _ in groups)
    # Every entry lands in exactly one run.
    assert sum(len(m) for _, m in groups) == len(docs)


def test_single_year_prefers_the_fallback(tmp_path: Path) -> None:
    """One limb is a worse picture than several runs, so a lone year falls back."""
    path = tmp_path / "one_year.sqlite"
    _build_db(path, [(f"e{i}", f"1665-0{i}-01T00:00") for i in range(1, 6)])
    nodes, _ = load_diary_graph(path)
    docs = [n for n in nodes if n.kind == "document"]
    groups = period_groups(docs, load_entry_times(path))

    assert [label for label, _ in groups] != ["1665"]
    assert all(label.startswith("part ") for label, _ in groups)


def test_period_groups_handles_no_entries() -> None:
    assert period_groups([], {}) == []


# ---------------------------------------------------------------------------
# Tree layout
# ---------------------------------------------------------------------------


def test_tree_places_every_node(dated_db: Path) -> None:
    nodes, edges = load_diary_graph(dated_db)
    pos = DiaryTreeLayout(load_entry_times(dated_db)).compute(nodes, edges)

    assert set(pos) == {n.id for n in nodes}
    assert all(p.shape == (3,) for p in pos.values())
    assert all(np.isfinite(p).all() for p in pos.values())


def test_tree_limbs_ascend_with_time(dated_db: Path) -> None:
    """Earliest year lowest: a tree should read bottom-to-top as a life does."""
    nodes, edges = load_diary_graph(dated_db)
    times = load_entry_times(dated_db)
    layout = DiaryTreeLayout(times)
    pos = layout.compute(nodes, edges)

    assert [label for label, _ in layout.periods] == ["1665", "1666", "1667"]
    heights = [
        np.mean([pos[d.id][2] for d in members])
        for _, members in period_groups([n for n in nodes if n.kind == "document"], times)
    ]
    assert heights == sorted(heights)


def test_tree_is_stable_for_a_fixed_key(dated_db: Path) -> None:
    nodes, edges = load_diary_graph(dated_db)
    times = load_entry_times(dated_db)
    a = DiaryTreeLayout(times, key="pepys").compute(nodes, edges)
    b = DiaryTreeLayout(times, key="pepys").compute(nodes, edges)

    for nid in a:
        np.testing.assert_allclose(a[nid], b[nid])


def test_tree_key_changes_the_tree(dated_db: Path) -> None:
    nodes, edges = load_diary_graph(dated_db)
    times = load_entry_times(dated_db)
    a = DiaryTreeLayout(times, key="pepys").compute(nodes, edges)
    b = DiaryTreeLayout(times, key="evelyn").compute(nodes, edges)

    assert any(not np.allclose(a[nid], b[nid]) for nid in a)


def test_tree_hangs_chunks_near_their_entry(dated_db: Path) -> None:
    nodes, edges = load_diary_graph(dated_db)
    pos = DiaryTreeLayout(load_entry_times(dated_db)).compute(nodes, edges)

    for e in edges:
        if e.rel == "CONTAINS":
            assert np.linalg.norm(pos[e.dst] - pos[e.src]) < 2.0


# ---------------------------------------------------------------------------
# Temporal layout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["1665-03-02T09:00", "1665-03-02", "1665-03", "1665"],
)
def test_parse_timestamp_accepts_partial_precision(text: str) -> None:
    assert parse_timestamp(text) is not None


@pytest.mark.parametrize("text", ["", "not-a-date"])
def test_parse_timestamp_rejects_junk(text: str) -> None:
    assert parse_timestamp(text) is None


def test_temporal_z_is_monotonic_in_date(dated_db: Path) -> None:
    nodes, edges = load_diary_graph(dated_db)
    times = load_entry_times(dated_db)
    pos = TemporalLayout(times).compute(nodes, edges)

    order = sorted(times, key=lambda k: times[k])
    zs = [pos[k][2] for k in order]
    assert zs == sorted(zs)


def test_temporal_gaps_are_proportional_to_silence(dated_db: Path) -> None:
    """
    A silent stretch must show as a gap. e2 -> e3 is ~10 months and e3 -> e4 is
    ~4, so the first gap has to be the larger one — that is the whole point of
    scaling Z by date rather than by index.
    """
    nodes, edges = load_diary_graph(dated_db)
    pos = TemporalLayout(load_entry_times(dated_db)).compute(nodes, edges)

    assert (pos["e3"][2] - pos["e2"][2]) > (pos["e4"][2] - pos["e3"][2])


def test_temporal_places_every_node_and_uses_projection(dated_db: Path) -> None:
    nodes, edges = load_diary_graph(dated_db)
    pos = TemporalLayout(
        load_entry_times(dated_db),
        projection={"e1": (3.0, -4.0)},
    ).compute(nodes, edges)

    assert set(pos) == {n.id for n in nodes}
    np.testing.assert_allclose(pos["e1"][:2], [3.0, -4.0])


def test_temporal_handles_a_wholly_undated_diary(undated_db: Path) -> None:
    """Order is still a chronology, so Z still rises."""
    nodes, edges = load_diary_graph(undated_db)
    pos = TemporalLayout(load_entry_times(undated_db)).compute(nodes, edges)

    docs = [n.id for n in nodes if n.kind == "document"]
    zs = [pos[d][2] for d in docs]
    assert zs == sorted(zs)
    assert zs[0] < zs[-1]

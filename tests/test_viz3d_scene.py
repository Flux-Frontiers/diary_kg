"""
Phase 2 contracts: the scene composes, off-screen, without Qt.

Every test here renders with ``pv.OFF_SCREEN`` and no Qt import anywhere in the
chain. Two failures from this fleet are designed against explicitly:

- ``_waverider``'s suite segfaults on a headless machine because a module-scope
  call renders during *collection*. Nothing here renders at import time, and the
  probe that proves rendering works lives inside a test body.
- ``gutenberg_kg`` learned to skip its pyvista suites at collection, because CI
  installs an extra set that has no pyvista. Same here, via ``importorskip``.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "kg_utils.viz3d.organic",
    reason="kgmodule-utils >=0.12.1 required: 0.12.0 shipped without the organic engine",
)
pv = pytest.importorskip("pyvista", reason="viz3d-render extra not installed")

# An installed pyvista is not enough. This VTK build has no OSMesa or EGL
# fallback, so constructing a Plotter without a display does not raise — it
# aborts the interpreter, and a fatal abort takes the whole session down,
# unrelated tests included. `importorskip` cannot help: pyvista imports fine.
# Gate on a real display and let `xvfb-run -a pytest` provide one.
pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="rendering needs a display; run under `xvfb-run -a`",
)

from diary_kg.loader import load_diary_graph, load_entry_times  # noqa: E402
from diary_kg.scene import (  # noqa: E402
    DiarySceneFilters,
    build_diary_scene,
)

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


@pytest.fixture(scope="module")
def diary_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small dated diary spanning three years, with topics and a SIMILAR_TO echo."""
    path = tmp_path_factory.mktemp("scene") / "diary.sqlite"
    con = sqlite3.connect(str(path))
    con.executescript(_SCHEMA)
    entries = [
        ("e1", "1665-03-02T09:00"),
        ("e2", "1665-11-19T21:30"),
        ("e3", "1666-09-02T04:00"),
        ("e4", "1667-01-01T12:00"),
    ]
    for eid, ts in entries:
        con.execute(
            "INSERT INTO nodes (id, kind, name, title) VALUES (?, 'document', ?, ?)",
            (eid, eid, eid),
        )
        for c in range(3):
            cid = f"{eid}:c{c}"
            con.execute(
                "INSERT INTO nodes (id, kind, name, text, timestamp) VALUES (?, 'chunk', ?, ?, ?)",
                (cid, cid, f"text {cid}", ts),
            )
            con.execute("INSERT INTO edges (src, rel, dst) VALUES (?, 'CONTAINS', ?)", (eid, cid))
    con.execute("INSERT INTO nodes (id, kind, name) VALUES ('t:fire', 'topic', 'fire')")
    con.execute("INSERT INTO edges (src, rel, dst) VALUES ('e3', 'HAS_TOPIC', 't:fire')")
    # A 1667 entry echoing 1665 — the relation the tree cannot express.
    con.execute("INSERT INTO edges (src, rel, dst) VALUES ('e4', 'SIMILAR_TO', 'e1')")
    con.commit()
    con.close()
    return path


@pytest.fixture
def graph(diary_db: Path):
    """``(nodes, edges, entry_times)`` for the sample diary."""
    nodes, edges = load_diary_graph(diary_db)
    return nodes, edges, load_entry_times(diary_db)


@pytest.fixture
def plotter():
    """An off-screen plotter, closed afterwards so the suite leaks no windows."""
    p = pv.Plotter(off_screen=True)
    yield p
    p.close()


def test_no_qt_anywhere_in_the_chain() -> None:
    """
    scene.py must stay Qt-free — that is the whole reason for the module split.

    A Qt import here would mean the same composition could not serve a headless
    renderer, which is what makes `diarykg quilt` nearly free later.
    """
    for mod in ("PyQt5", "pyvistaqt", "PySide6"):
        assert mod not in sys.modules, f"{mod} was imported by the scene chain"


@pytest.mark.parametrize("mode", ["tree", "manifold"])
def test_scene_builds_in_both_modes(graph, plotter, mode: str) -> None:
    nodes, edges, times = graph
    info = build_diary_scene(nodes, edges, plotter, mode=mode, entry_times=times)

    assert info.mode == mode
    assert set(info.positions) == {n.id for n in nodes}
    assert sum(info.counts.values()) > 0
    assert len(plotter.renderer.actors) > 0


def test_tree_mode_grows_wood_and_foliage(graph, plotter) -> None:
    nodes, edges, times = graph
    info = build_diary_scene(nodes, edges, plotter, mode="tree", entry_times=times)

    assert info.skeleton is not None
    assert info.counts["wood"] == 1
    assert info.counts["foliage"] == 1
    assert [label for label, _ in info.periods] == ["1665", "1666", "1667"]


def test_manifold_mode_draws_points_not_wood(graph, plotter) -> None:
    nodes, edges, times = graph
    info = build_diary_scene(nodes, edges, plotter, mode="manifold", entry_times=times)

    assert info.skeleton is None
    assert info.counts["wood"] == 0
    assert info.counts["chunks"] == 1


def test_similar_edges_are_drawn_when_asked(graph, plotter) -> None:
    """The long diagonal is the manifold's reason to exist, so it must reach the scene."""
    nodes, edges, times = graph
    info = build_diary_scene(
        nodes,
        edges,
        plotter,
        mode="manifold",
        entry_times=times,
        filters=DiarySceneFilters(show_similar=True, show_contains=True),
    )

    assert info.counts["similar"] == 1
    assert info.counts["contains"] == 12


def test_threads_are_off_by_default(graph, plotter) -> None:
    nodes, edges, times = graph
    default = build_diary_scene(nodes, edges, plotter, mode="manifold", entry_times=times)
    assert default.counts["threads"] == 0

    p2 = pv.Plotter(off_screen=True)
    try:
        shown = build_diary_scene(
            nodes,
            edges,
            p2,
            mode="manifold",
            entry_times=times,
            filters=DiarySceneFilters(show_threads=True),
        )
        assert shown.counts["threads"] == 1
    finally:
        p2.close()


def test_rejects_an_unknown_mode(graph, plotter) -> None:
    nodes, edges, times = graph
    with pytest.raises(ValueError, match="mode must be one of"):
        build_diary_scene(nodes, edges, plotter, mode="lollipop", entry_times=times)


def test_progress_is_reported(graph, plotter) -> None:
    nodes, edges, times = graph
    seen: list[str] = []
    build_diary_scene(nodes, edges, plotter, mode="tree", entry_times=times, progress=seen.append)

    assert seen and any("scene ready" in m for m in seen)


def test_renders_a_screenshot_off_screen(graph, plotter) -> None:
    """
    The end-to-end proof, and the one that must never move to module scope.

    ``_waverider`` calls ``screenshot()`` while importing and segfaults on a
    headless machine; because that happens during collection, ``--ignore``
    cannot rescue it. Inside a test body it is merely a test.
    """
    nodes, edges, times = graph
    build_diary_scene(nodes, edges, plotter, mode="tree", entry_times=times)

    image = plotter.screenshot(return_img=True)
    assert image is not None
    assert image.shape[0] > 0 and image.shape[1] > 0

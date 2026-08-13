"""
Compose a diary into a PyVista scene — without Qt.

This module builds actors into a plain :class:`pyvista.Plotter` handed in by the
caller. It never creates a window, never starts an event loop, and imports no Qt.
That split is copied from ``gutenberg_kg.scene`` and is worth preserving for a
concrete reason: the same composition then serves both an interactive viewer and
a headless renderer, so a light-field or screenshot pipeline costs nothing extra
later.

Two modes, matching the two layouts:

``tree``
    The artistic view. Entry stations and chunk leaves from
    :class:`~diary_kg.layout_tree.DiaryTreeLayout`, with an organic skeleton
    grown through the leaves by the shared engine and swept into wood.

``manifold``
    The analytical view. :class:`~diary_kg.layout_temporal.TemporalLayout`
    positions, where Z is date, so a silent year is a visible gap.

Nothing renders at import time. That is deliberate: the sibling repo
``_waverider`` has a suite that segfaults on a headless machine because a
module-scope call renders during collection, and ``--ignore`` cannot help when
collection itself kills the process.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pyvista as pv
from kg_utils.viz3d import LayoutEdge, LayoutNode, Skeleton, leaf_glyphs, tree_mesh

from diary_kg.layout_temporal import TemporalLayout
from diary_kg.layout_tree import DiaryTreeLayout, grow_skeleton

__all__ = ["DiarySceneFilters", "DiarySceneInfo", "build_diary_scene"]

#: Modes accepted by :func:`build_diary_scene`.
MODES: tuple[str, ...] = ("tree", "manifold")

_ENTRY_COLOR = "#c8b18a"
_CHUNK_COLOR = "#7ea172"
_THREAD_COLOR = "#8c9bb5"
_WOOD_COLOR = "#6b5540"


@dataclass
class DiarySceneFilters:
    """
    What to draw. Defaults suit the tree: wood and foliage, no clutter.

    :param show_entries: Draw a glyph per entry document.
    :param show_chunks: Draw the chunk leaves.
    :param show_threads: Draw topic and entity nodes.
    :param show_contains: Draw ``CONTAINS`` edges from entry to chunk.
    :param show_similar: Draw ``SIMILAR_TO`` edges, the long diagonals the tree
        cannot express and the manifold can.
    """

    show_entries: bool = True
    show_chunks: bool = True
    show_threads: bool = False
    show_contains: bool = False
    show_similar: bool = False


@dataclass
class DiarySceneInfo:
    """
    What was built, returned so a caller can label, pick or test against it.

    :param title: Human-readable scene title.
    :param mode: ``"tree"`` or ``"manifold"``.
    :param positions: ``{node id: [x, y, z]}`` as computed by the layout.
    :param counts: Actors added, keyed by what they represent.
    :param periods: ``[(label, entry count)]`` — populated in tree mode only.
    :param skeleton: The grown skeleton, in tree mode with leaves present.
    """

    title: str
    mode: str
    positions: dict[str, np.ndarray] = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    periods: list[tuple[str, int]] = field(default_factory=list)
    skeleton: Skeleton | None = None


def _report(progress: Callable[[str], None] | None, message: str) -> None:
    """
    Emit a progress message if the caller wants them.

    Kept as a plain callable rather than a logger or a Qt signal so a Qt caller
    can pump its event loop and a headless caller can print or ignore.

    :param progress: Caller's sink, or ``None``.
    :param message: Message to emit.
    """
    if progress is not None:
        progress(message)


def _points(positions: dict[str, np.ndarray], ids: list[str]) -> np.ndarray:
    """
    Stack the positions of *ids* into an ``(N, 3)`` array.

    :param positions: Layout output.
    :param ids: Node IDs to gather.
    :return: ``(N, 3)`` float array; empty ``(0, 3)`` when nothing matches.
    """
    pts = [positions[i] for i in ids if i in positions]
    return np.asarray(pts, dtype=float) if pts else np.empty((0, 3), dtype=float)


def _add_line_set(
    plotter: pv.Plotter,
    positions: dict[str, np.ndarray],
    edges: list[LayoutEdge],
    rel: str,
    color: str,
    width: float,
    opacity: float,
) -> int:
    """
    Add every edge of one relation as a single line-set actor.

    One actor rather than one per edge: a diary with thousands of entries would
    otherwise add thousands of actors and stall the renderer.

    :param plotter: Target plotter.
    :param positions: Layout output.
    :param edges: All edges.
    :param rel: Relation to draw.
    :param color: Line colour.
    :param width: Line width.
    :param opacity: Line opacity.
    :return: Number of edges drawn.
    """
    pts: list[np.ndarray] = []
    lines: list[int] = []
    for e in edges:
        if e.rel != rel or e.src not in positions or e.dst not in positions:
            continue
        i = len(pts)
        pts.extend([positions[e.src], positions[e.dst]])
        lines.extend([2, i, i + 1])

    if not pts:
        return 0

    mesh = pv.PolyData(np.asarray(pts, dtype=float), lines=np.asarray(lines, dtype=np.int64))
    plotter.add_mesh(mesh, color=color, line_width=width, opacity=opacity)
    return len(lines) // 3


def build_diary_scene(
    nodes: list[LayoutNode],
    edges: list[LayoutEdge],
    plotter: pv.Plotter,
    *,
    mode: str = "tree",
    entry_times: dict[str, str] | None = None,
    filters: DiarySceneFilters | None = None,
    key: str = "diary",
    title: str = "diary",
    leaf_size: float = 0.28,
    progress: Callable[[str], None] | None = None,
) -> DiarySceneInfo:
    """
    Build a diary scene into *plotter*.

    :param nodes: All nodes in the diary graph.
    :param edges: All edges.
    :param plotter: A plain :class:`pyvista.Plotter`. Caller owns it, including
        whether it is off-screen; nothing here shows a window.
    :param mode: ``"tree"`` or ``"manifold"``.
    :param entry_times: ``{document id: ISO timestamp}`` from
        :func:`diary_kg.loader.load_entry_times`.
    :param filters: What to draw. Defaults to entries and chunks.
    :param key: Stable identifier; seeds the layout so a diary always looks the
        same.
    :param title: Scene title, returned on the info object.
    :param leaf_size: Glyph size for chunk foliage in tree mode.
    :param progress: Optional sink for progress messages.
    :return: What was built.
    :raises ValueError: If *mode* is not one of :data:`MODES`.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")

    filters = filters or DiarySceneFilters()
    info = DiarySceneInfo(title=title, mode=mode)

    _report(progress, f"laying out {len(nodes)} nodes ({mode})")
    if mode == "tree":
        layout = DiaryTreeLayout(entry_times, key=key)
        info.positions = layout.compute(nodes, edges)
        info.periods = layout.periods
    else:
        info.positions = TemporalLayout(entry_times, key=key).compute(nodes, edges)

    documents = [n.id for n in nodes if n.kind == "document"]
    chunks = [n.id for n in nodes if n.kind == "chunk"]
    threads = [n.id for n in nodes if n.kind in ("topic", "entity", "person", "place")]

    # Wood first, so foliage and glyphs read as sitting on it.
    if mode == "tree" and chunks:
        _report(progress, f"growing a skeleton through {len(chunks)} leaves")
        try:
            skeleton = grow_skeleton(info.positions, chunks, key=key)
        except ValueError:
            skeleton = None
        if skeleton is not None:
            info.skeleton = skeleton
            plotter.add_mesh(tree_mesh(skeleton), color=_WOOD_COLOR)
            info.counts["wood"] += 1
            if filters.show_chunks:
                foliage = leaf_glyphs(_points(info.positions, chunks), skeleton, size=leaf_size)
                plotter.add_mesh(foliage, color=_CHUNK_COLOR)
                info.counts["foliage"] += 1

    # In manifold mode chunks are points rather than foliage: the question there
    # is when something was written, not what it hangs from.
    if (mode == "manifold" or info.skeleton is None) and filters.show_chunks and chunks:
        pts = _points(info.positions, chunks)
        if pts.size:
            plotter.add_mesh(
                pv.PolyData(pts), color=_CHUNK_COLOR, point_size=5, render_points_as_spheres=True
            )
            info.counts["chunks"] += 1

    if filters.show_entries and documents:
        pts = _points(info.positions, documents)
        if pts.size:
            plotter.add_mesh(
                pv.PolyData(pts), color=_ENTRY_COLOR, point_size=11, render_points_as_spheres=True
            )
            info.counts["entries"] += 1

    if filters.show_threads and threads:
        pts = _points(info.positions, threads)
        if pts.size:
            plotter.add_mesh(
                pv.PolyData(pts), color=_THREAD_COLOR, point_size=9, render_points_as_spheres=True
            )
            info.counts["threads"] += 1

    if filters.show_contains:
        info.counts["contains"] = _add_line_set(
            plotter, info.positions, edges, "CONTAINS", "#5c5a55", 1.0, 0.25
        )
    if filters.show_similar:
        info.counts["similar"] = _add_line_set(
            plotter, info.positions, edges, "SIMILAR_TO", "#b08fc7", 1.5, 0.45
        )

    _report(progress, f"scene ready: {sum(info.counts.values())} actors")
    return info

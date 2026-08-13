"""
The analytical layout: a diary as a temporal manifold.

The tree in :mod:`diary_kg.layout_tree` is a beautiful object but a poor
instrument. You cannot read a topic's rise and fall off it, and two entries five
years apart that say the same thing sit on different limbs by construction.

This layout answers those questions instead:

- **Z is time**, scaled continuously by date, so a silent year is a visible gap
  rather than a limb that simply is not there.
- **XY is semantic** — a caller-supplied projection when one exists, and a
  golden-angle disc otherwise, which spreads entries evenly without pretending
  to carry meaning.
- **Topics and entities are verticals** at fixed XY, so a topic that dominates
  one year and vanishes the next becomes legible as a column that stops.

The two layouts are complementary: the tree shows a life's shape, the manifold
shows its structure. Nothing here imports PyVista.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from kg_utils.viz3d import (
    Layout3D,
    LayoutEdge,
    LayoutNode,
    golden_spiral_2d,
    seed_from_key,
)

__all__ = ["TemporalLayout", "parse_timestamp"]

_DOCUMENT_KINDS = frozenset({"document"})
_CHUNK_KINDS = frozenset({"chunk"})
#: Kinds drawn as verticals rather than placed at a moment in time.
_THREAD_KINDS = frozenset({"topic", "entity", "person", "place"})


def parse_timestamp(ts: str) -> float | None:
    """
    Convert an ISO-ish timestamp to a sortable ordinal in days.

    DiaryKG frontmatter is not uniformly precise — some entries carry a full
    ``YYYY-MM-DDTHH:MM`` and others only ``YYYY-MM-DD`` — so this accepts a
    prefix and degrades rather than raising.

    :param ts: Timestamp string.
    :return: Days since the Unix epoch as a float, or ``None`` if unparseable.
    """
    if not ts:
        return None
    text = str(ts).strip().replace("Z", "")
    for cut in (len(text), 19, 16, 13, 10, 7, 4):
        try:
            fragment = text[:cut]
            if cut == 7:
                fragment += "-01"
            elif cut == 4:
                fragment += "-01-01"
            dt = datetime.fromisoformat(fragment)
        except ValueError:
            continue
        return dt.timestamp() / 86400.0
    return None


class TemporalLayout(Layout3D):
    """
    Lay a diary out as time against semantic position.

    :param entry_times: ``{document id: ISO timestamp}``, from
        :func:`diary_kg.loader.load_entry_times`.
    :param projection: Optional ``{node id: (x, y)}`` semantic projection. When
        absent, a golden-angle disc is used, which is even but arbitrary.
    :param key: Stable identifier seeding the fallback placement.
    :param height: Z extent of the whole diary.
    :param radius: XY radius of the disc.
    """

    def __init__(
        self,
        entry_times: dict[str, str] | None = None,
        *,
        projection: dict[str, tuple[float, float]] | None = None,
        key: str = "diary",
        height: float = 20.0,
        radius: float = 8.0,
    ) -> None:
        self.entry_times = dict(entry_times or {})
        self.projection = dict(projection or {})
        self.key = key
        self.height = float(height)
        self.radius = float(radius)

    def compute(
        self,
        nodes: list[LayoutNode],
        edges: list[LayoutEdge],
    ) -> dict[str, np.ndarray]:
        """
        Assign a position to every node.

        :param nodes: All nodes in the diary graph.
        :param edges: All edges; ``CONTAINS`` ties chunks to their entry's date.
        :return: ``{node id: [x, y, z]}``.
        """
        rng = np.random.default_rng(seed_from_key(self.key))
        by_id = {n.id: n for n in nodes}

        documents = [n for n in nodes if n.kind in _DOCUMENT_KINDS]
        ordinals = {d.id: parse_timestamp(self.entry_times.get(d.id, "")) for d in documents}
        dated = [v for v in ordinals.values() if v is not None]

        if dated:
            lo, hi = min(dated), max(dated)
            span = (hi - lo) or 1.0

            def z_of(doc_id: str, index: int) -> float:
                v = ordinals.get(doc_id)
                if v is None:
                    # Undated among dated: fall back to its position in order,
                    # which keeps it in sequence without inventing a date.
                    return self.height * (index / max(len(documents) - 1, 1))
                return self.height * ((v - lo) / span)

        else:
            # No dates at all: order is the only chronology available, and for a
            # diary that is still a chronology.
            def z_of(doc_id: str, index: int) -> float:  # noqa: ARG001 - parity
                return self.height * (index / max(len(documents) - 1, 1))

        # XY: semantic if supplied, otherwise an even disc.
        spiral = golden_spiral_2d(max(len(documents), 1), radius=self.radius)

        pos: dict[str, np.ndarray] = {}
        placed: set[str] = set()
        for i, doc in enumerate(documents):
            if doc.id in self.projection:
                x, y = self.projection[doc.id]
            else:
                p = np.asarray(spiral[i], dtype=float)
                x, y = float(p[0]), float(p[1])
            pos[doc.id] = np.array([x, y, z_of(doc.id, i)])
            placed.add(doc.id)

        # Chunks sit at their entry's moment, scattered slightly so a busy entry
        # reads as a cluster rather than a single overplotted point.
        chunk_parent: dict[str, str] = {}
        for e in edges:
            if e.rel == "CONTAINS" and e.src in pos:
                dst = by_id.get(e.dst)
                if dst is not None and dst.kind in _CHUNK_KINDS:
                    chunk_parent[e.dst] = e.src
        for chunk_id, parent in chunk_parent.items():
            jitter = rng.normal(scale=self.radius * 0.02, size=3)
            jitter[2] *= 0.25  # keep a chunk close to its entry's moment
            pos[chunk_id] = pos[parent] + jitter
            placed.add(chunk_id)

        # Threads: topics and entities are verticals, so they take a fixed XY at
        # mid-height and the renderer draws the column.
        threads = [n for n in nodes if n.kind in _THREAD_KINDS and n.id not in placed]
        if threads:
            ring = golden_spiral_2d(len(threads), radius=self.radius * 1.15)
            for n, p in zip(threads, ring):
                p = np.asarray(p, dtype=float)
                pos[n.id] = np.array([float(p[0]), float(p[1]), self.height * 0.5])
                placed.add(n.id)

        leftovers = [n.id for n in nodes if n.id not in placed]
        if leftovers:
            ring = golden_spiral_2d(len(leftovers), radius=self.radius * 1.35)
            for nid, p in zip(leftovers, ring):
                p = np.asarray(p, dtype=float)
                pos[nid] = np.array([float(p[0]), float(p[1]), 0.0])

        return pos

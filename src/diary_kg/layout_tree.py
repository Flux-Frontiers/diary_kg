"""
The artistic layout: a diary as a single tree.

The grammar, inherited from ``gutenberg_kg``'s forest renderer, is::

    trunk -> period limb (one per calendar year) -> entry cluster -> chunk leaves

A diary has no chapters, just thousands of dated entries, so its real hierarchy
is time and the limbs are periods. Each limb is a span of the diarist's life.

This module computes *positions only*. Turning a skeleton into meshes is the
renderer's job and needs PyVista; nothing here imports it, so the whole layout
is testable headlessly. :func:`grow_skeleton` is offered separately for callers
that want the organic branch geometry — it uses the shared engine promoted into
``kgmodule-utils`` 0.12.0, whose colonisation and pipe-model code is NumPy-only.
"""

from __future__ import annotations

import numpy as np
from kg_utils.viz3d import (
    Layout3D,
    LayoutEdge,
    LayoutNode,
    crown_spacing,
    fibonacci_sphere,
    seed_from_key,
)

from diary_kg.loader import period_groups

__all__ = ["DiaryTreeLayout", "grow_skeleton"]

#: Golden angle, radians. Successive limbs step by this so they never stack.
_GOLDEN_ANGLE = np.pi * (3.0 - np.sqrt(5.0))

_DOCUMENT_KINDS = frozenset({"document"})
_CHUNK_KINDS = frozenset({"chunk"})


class DiaryTreeLayout(Layout3D):
    """
    Grow one tree from a diary graph.

    :param entry_times: ``{document id: ISO timestamp}``, from
        :func:`diary_kg.loader.load_entry_times`. May be empty, in which case
        periods fall back to equal runs of input order.
    :param key: Stable identifier seeding every random choice, so the same
        graph always produces the same tree.
    :param trunk_height: Height of the trunk before the first limb.
    :param crown_radius: Outer radius the limb tips reach.
    """

    def __init__(
        self,
        entry_times: dict[str, str] | None = None,
        *,
        key: str = "diary",
        trunk_height: float = 10.0,
        crown_radius: float = 6.0,
    ) -> None:
        self.entry_times = dict(entry_times or {})
        self.key = key
        self.trunk_height = float(trunk_height)
        self.crown_radius = float(crown_radius)
        #: ``[(label, entry count)]`` for the periods of the last :meth:`compute`.
        self.periods: list[tuple[str, int]] = []

    def compute(
        self,
        nodes: list[LayoutNode],
        edges: list[LayoutEdge],
    ) -> dict[str, np.ndarray]:
        """
        Assign a position to every node.

        :param nodes: All nodes in the diary graph.
        :param edges: All edges; ``CONTAINS`` supplies entry-to-chunk structure.
        :return: ``{node id: [x, y, z]}``.
        """
        rng = np.random.default_rng(seed_from_key(self.key))
        by_id = {n.id: n for n in nodes}

        documents = [n for n in nodes if n.kind in _DOCUMENT_KINDS]
        chunks_of: dict[str, list[str]] = {d.id: [] for d in documents}
        for e in edges:
            if e.rel == "CONTAINS" and e.src in chunks_of:
                dst = by_id.get(e.dst)
                if dst is not None and dst.kind in _CHUNK_KINDS:
                    chunks_of[e.src].append(e.dst)

        groups = period_groups(documents, self.entry_times)
        self.periods = [(label, len(members)) for label, members in groups]

        pos: dict[str, np.ndarray] = {}
        placed: set[str] = set()
        stations: list[np.ndarray] = []

        n_periods = max(len(groups), 1)
        for k, (_label, members) in enumerate(groups):
            # Limbs ascend with period order, so a tree reads bottom-to-top as
            # earliest-to-latest. This monotonicity is a tested contract.
            t = (k + 0.5) / n_periods
            z_base = self.trunk_height * (0.25 + 0.70 * t)
            angle = k * _GOLDEN_ANGLE
            outward = np.array([np.cos(angle), np.sin(angle), 0.0])
            reach = self.crown_radius * (0.55 + 0.45 * t)
            rise = self.trunk_height * 0.18

            m = len(members)
            for j, doc in enumerate(members):
                # Entries march outward along the limb, nearest the trunk first.
                s = (j + 1) / (m + 1)
                station = outward * reach * (0.30 + 0.70 * s)
                station = station + np.array([0.0, 0.0, z_base + rise * s])
                # A small deterministic wobble keeps entries off a dead-straight
                # line without breaking reproducibility.
                station = station + rng.normal(scale=reach * 0.03, size=3)
                pos[doc.id] = station
                placed.add(doc.id)
                stations.append(station)

        # Leaf clusters are sized from the crown's own geometry rather than a
        # guessed constant: ``crown_spacing`` gives the typical gap between
        # entries, and a cluster narrower than that gap keeps neighbouring
        # entries legible as separate clusters however dense the diary is.
        if len(stations) >= 2:
            spread = crown_spacing(np.array(stations)) * 0.35
        else:
            spread = self.crown_radius * 0.10
        spread = max(float(spread), 1e-3)

        for doc_id, leaves in chunks_of.items():
            if not leaves or doc_id not in pos:
                continue
            station = pos[doc_id]
            for leaf_id, unit in zip(leaves, fibonacci_sphere(len(leaves))):
                pos[leaf_id] = station + np.asarray(unit, dtype=float) * spread
                placed.add(leaf_id)

        # Everything else — topics, entities, orphan chunks — rings the trunk at
        # its base rather than landing on the origin in a heap.
        leftovers = [n.id for n in nodes if n.id not in placed]
        if leftovers:
            halo = self.crown_radius * 1.25
            for i, nid in enumerate(leftovers):
                a = i * _GOLDEN_ANGLE
                pos[nid] = np.array([np.cos(a) * halo, np.sin(a) * halo, 0.0])

        return pos


def grow_skeleton(
    positions: dict[str, np.ndarray],
    chunk_ids: list[str],
    *,
    key: str = "diary",
    root: np.ndarray | None = None,
):
    """
    Grow organic branch geometry through the placed leaves.

    Thin wrapper over the shared engine so callers do not have to assemble the
    attractor array themselves. Colonisation and the pipe model are NumPy-only;
    only mesh building needs PyVista, and that happens downstream.

    :param positions: Output of :meth:`DiaryTreeLayout.compute`.
    :param chunk_ids: IDs whose positions act as crown attractors.
    :param key: Stable identifier; seeds the RNG so the tree is reproducible.
    :param root: Trunk base. Defaults to the origin.
    :return: A :class:`kg_utils.viz3d.Skeleton` with radii assigned.
    :raises ValueError: If no attractor positions are available.
    """
    from kg_utils.viz3d import grow_tree  # local: keeps import cost off module load

    pts = np.array([positions[c] for c in chunk_ids if c in positions], dtype=float)
    if pts.size == 0:
        raise ValueError("no chunk positions to grow a skeleton through")

    return grow_tree(pts, np.asarray(root if root is not None else [0.0, 0.0, 0.0], dtype=float), key=key)

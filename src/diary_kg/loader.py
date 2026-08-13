"""
Load a ``.diarykg/`` graph into the shared layout vocabulary.

This is the seam between DiaryKG's SQLite and the geometry in
:mod:`diary_kg.layout_tree` and :mod:`diary_kg.layout_temporal`: it reads nodes
and edges into :class:`~kg_utils.viz3d.LayoutNode` / ``LayoutEdge``, and it
recovers the chronology the layouts are built on.

Nothing here imports PyVista, or renders. The layouts are pure geometry over
what this module returns, which is what makes them testable on a synthetic
database with no display.

**Where dates come from.** DiaryKG builds on DocKG's store and then adds
``timestamp`` to the ``nodes`` table in an enrichment pass that only ever writes
it to ``kind='chunk'`` rows — the date lives in each chunk's markdown
frontmatter. A ``document`` row, which is what an *entry* is, keeps a null
timestamp. So an entry's date has to be lifted from the chunks it contains,
which is what :func:`load_entry_times` does.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np
from kg_utils.viz3d import LayoutEdge, LayoutNode

__all__ = [
    "load_diary_graph",
    "load_entry_times",
    "period_groups",
]

#: Columns DocKG guarantees. Anything DiaryKG adds later is read defensively,
#: because a graph built before an enrichment pass simply will not have it.
_BASE_COLUMNS = ("id", "kind", "name", "title", "file_path", "text")


def load_diary_graph(db_path: Path | str) -> tuple[list[LayoutNode], list[LayoutEdge]]:
    """
    Read a DiaryKG graph into layout nodes and edges.

    IDs are used verbatim. Unlike ``gutenberg_kg``, which namespaces every ID
    with a book slug because it merges a whole corpus into one forest, a diary
    is a single graph and there is nothing to collide with.

    :param db_path: Path to the ``.diarykg`` SQLite database.
    :return: ``(nodes, edges)``.
    """
    nodes: list[LayoutNode] = []
    edges: list[LayoutEdge] = []

    with sqlite3.connect(str(db_path)) as con:
        cols = ", ".join(_BASE_COLUMNS)
        for nid, kind, name, title, file_path, text in con.execute(f"SELECT {cols} FROM nodes"):
            nodes.append(
                LayoutNode(
                    id=nid,
                    kind=kind,
                    # A chunk's ``name`` is its entry timestamp, which is the
                    # most useful label it has; a document prefers its title.
                    name=title or name or nid,
                    module_path=file_path,
                    docstring=text[:500] if text else None,
                )
            )
        for src, rel, dst in con.execute("SELECT src, rel, dst FROM edges"):
            edges.append(LayoutEdge(src=src, rel=rel, dst=dst))

    return nodes, edges


def load_entry_times(db_path: Path | str) -> dict[str, str]:
    """
    Earliest chunk timestamp per entry document.

    :param db_path: Path to the ``.diarykg`` SQLite database.
    :return: ``{document id: ISO timestamp}``. Empty when the graph carries no
        timestamps at all — either because the enrichment pass never ran or
        because the column does not exist yet, both of which are ordinary
        rather than exceptional.
    """
    with sqlite3.connect(str(db_path)) as con:
        try:
            rows = con.execute(
                "SELECT e.src, MIN(n.timestamp) FROM edges e "
                "JOIN nodes n ON n.id = e.dst "
                "WHERE e.rel = 'CONTAINS' AND n.kind = 'chunk' AND n.timestamp IS NOT NULL "
                "GROUP BY e.src"
            ).fetchall()
        except sqlite3.OperationalError:
            # No ``timestamp`` column: a graph built before metadata enrichment.
            return {}

    return {src: ts for src, ts in rows if ts}


def period_groups(
    branch_nodes: list[LayoutNode],
    entry_times: dict[str, str],
) -> list[tuple[str, list[LayoutNode]]]:
    """
    Split entry documents into the chronological periods that become limbs.

    Real years are used when every entry carries a date and at least two years
    are present — one limb per calendar year, which is what a reader means by
    "the 1665 branch". A single year would produce a one-limbed tree, which is
    a worse picture than the fallback gives.

    Without usable dates it falls back to equal runs of the input order, which
    for a diary is still chronological, just unlabelled.

    :param branch_nodes: Entry documents, in file order.
    :param entry_times: Mapping from :func:`load_entry_times`.
    :return: ``[(label, members)]``, earliest first.
    """
    if not branch_nodes:
        return []

    dated = [(entry_times.get(n.id), n) for n in branch_nodes]
    if all(ts for ts, _ in dated):
        by_year: dict[str, list[LayoutNode]] = defaultdict(list)
        for ts, node in dated:
            by_year[str(ts)[:4]].append(node)
        if len(by_year) >= 2:
            return sorted(by_year.items())

    n = len(branch_nodes)
    n_limbs = max(3, int(round(np.sqrt(n) / 2.0)))
    n_limbs = min(n_limbs, n)  # never more limbs than entries
    runs: dict[int, list[LayoutNode]] = defaultdict(list)
    for i, node in enumerate(branch_nodes):
        runs[min(i * n_limbs // n, n_limbs - 1)].append(node)
    return [(f"part {k + 1}", v) for k, v in sorted(runs.items())]

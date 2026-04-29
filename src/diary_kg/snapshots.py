"""
snapshots.py — Temporal Snapshots of DiaryKG Metrics

Snapshot model:
- Key is the git tree hash (HEAD^{tree}), stable across rebases
- Snapshots stored in .diarykg/snapshots/{tree_hash}.json
- manifest.json indexes all snapshots with fast lookup
- Deltas computed vs previous (chronological) and vs baseline (oldest)

Usage
-----
>>> from diary_kg.snapshots import DiarySnapshotManager
>>> mgr = DiarySnapshotManager(".diarykg/snapshots")
>>> snap = mgr.capture_diary(version="0.1.0", info=kg.info(), db_stats=kg.stats())
>>> mgr.save_snapshot(snap)
>>> mgr.list_snapshots()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_utils.snapshots import PruneResult as PruneResult  # noqa: F401 — re-export
from kg_utils.snapshots import Snapshot, SnapshotManager

# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class DiarySnapshotManager(SnapshotManager):
    """Manages DiaryKG snapshot storage, retrieval, and comparison."""

    def __init__(self, snapshots_dir: Path | str) -> None:
        super().__init__(snapshots_dir, package_name="diary-kg")

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture_diary(
        self,
        version: str,
        info: dict,
        db_stats: dict,
        branch: str | None = None,
        tree_hash: str = "",
        label: str | None = None,
        source_file: str | None = None,
    ) -> Snapshot:
        """Capture a snapshot from current DiaryKG state.

        This is the diary-specific entry point.  It maps ``info`` / ``db_stats``
        to the base-class ``capture()`` signature so the override does not
        conflict with the supertype.

        :param version: Version string (e.g. ``"0.1.0"``).
        :param info: Output of ``DiaryKG.info()``.
        :param db_stats: Output of ``DiaryKG.stats()`` (node/edge counts).
        :param branch: Git branch; auto-detected if ``None``.
        :param tree_hash: Git tree hash; auto-detected if empty.
        :param label: Optional human-readable label.
        :param source_file: Source diary file label.
        :return: New :class:`~kg_utils.snapshots.Snapshot` instance (not yet saved).
        """
        node_count = db_stats.get("node_count", 0)
        edge_count = db_stats.get("edge_count", 0)
        if not isinstance(node_count, int):
            node_count = 0
        if not isinstance(edge_count, int):
            edge_count = 0

        metrics: dict[str, Any] = {
            "chunk_count": info.get("chunk_count", 0),
            "entry_count": info.get("entry_count", 0),
            "total_nodes": node_count,
            "total_edges": edge_count,
            "topic_counts": info.get("topic_counts") or {},
            "context_counts": info.get("context_counts") or {},
            "temporal_span": info.get("temporal_span") or {},
            "chunking_strategy": info.get("chunking_strategy", ""),
            "chunk_size": info.get("chunk_size", 512),
        }
        if label is not None:
            metrics["label"] = label
        sf = source_file or info.get("source_file")
        if sf is not None:
            metrics["source_file"] = sf

        return super().capture(
            version=version,
            branch=branch,
            graph_stats_dict=metrics,
            tree_hash=tree_hash,
        )

    # ------------------------------------------------------------------
    # Save — guard on chunk_count
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: Snapshot, *, force: bool = False) -> Path | None:
        """Save snapshot; raises ``ValueError`` if ``chunk_count`` is 0.

        :param snapshot: Snapshot to persist.
        :param force: If ``True``, always write a new history entry.
        :return: Path to the saved JSON file, or ``None`` if no-op.
        :raises ValueError: If ``chunk_count`` is 0 (degenerate / unbuilt KG).
        """
        chunk_count = (
            snapshot.metrics.get("chunk_count", 0) if isinstance(snapshot.metrics, dict) else 0
        )
        if chunk_count == 0:
            raise ValueError(
                "Refusing to save degenerate snapshot with 0 chunks. "
                "Run 'diarykg build' before capturing a snapshot."
            )
        return super().save_snapshot(snapshot, force=force)

    # ------------------------------------------------------------------
    # Delta computation — diary-specific fields
    # ------------------------------------------------------------------

    def _compute_delta_from_metrics(
        self, new_m: dict[str, Any], old_m: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "chunks": new_m.get("chunk_count", 0) - old_m.get("chunk_count", 0),
            "entries": new_m.get("entry_count", 0) - old_m.get("entry_count", 0),
            "nodes": new_m.get("total_nodes", 0) - old_m.get("total_nodes", 0),
            "edges": new_m.get("total_edges", 0) - old_m.get("total_edges", 0),
        }

    # ------------------------------------------------------------------
    # Previous snapshot — fall back to most recent when key is unsaved
    # ------------------------------------------------------------------

    def get_previous(self, key: str) -> Snapshot | None:
        """Return the snapshot immediately before this one (by timestamp).

        If *key* is not yet in the manifest (unsaved snapshot), falls back to
        the most recently saved snapshot so deltas are still computed.
        """
        manifest = self.load_manifest()
        current_ts = next((s["timestamp"] for s in manifest.snapshots if s.get("key") == key), None)
        if not current_ts:
            if not manifest.snapshots:
                return None
            latest = max(manifest.snapshots, key=lambda x: x["timestamp"])
            return self.load_snapshot(latest["key"])
        prev_entry = None
        for s in sorted(manifest.snapshots, key=lambda x: x["timestamp"], reverse=True):
            if s["timestamp"] < current_ts:
                prev_entry = s
                break
        return self.load_snapshot(prev_entry["key"]) if prev_entry else None

    # ------------------------------------------------------------------
    # Diff — add topic_counts_delta
    # ------------------------------------------------------------------

    def diff_snapshots(self, key_a: str, key_b: str) -> dict[str, Any]:
        """Compare two snapshots side-by-side, including topic distribution delta.

        :param key_a: Earlier snapshot key.
        :param key_b: Later snapshot key.
        :return: Dict with ``a``, ``b``, ``delta``, ``topic_counts_delta`` keys.
        """
        result = super().diff_snapshots(key_a, key_b)
        if "error" in result:
            return result

        snap_a = self.load_snapshot(key_a)
        snap_b = self.load_snapshot(key_b)
        if snap_a and snap_b:
            topics_a: dict[str, int] = (
                snap_a.metrics.get("topic_counts", {}) if isinstance(snap_a.metrics, dict) else {}
            )
            topics_b: dict[str, int] = (
                snap_b.metrics.get("topic_counts", {}) if isinstance(snap_b.metrics, dict) else {}
            )
            all_topics = set(topics_a) | set(topics_b)
            result["topic_counts_delta"] = {
                t: topics_b.get(t, 0) - topics_a.get(t, 0)
                for t in all_topics
                if topics_b.get(t, 0) != topics_a.get(t, 0)
            }
        return result

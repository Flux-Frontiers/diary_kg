"""
test_diary_kg_snapshots.py

Unit tests for diary_kg.snapshots — DiarySnapshotManager using the
kg_utils.snapshots dict-based Snapshot model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from kg_utils.snapshots import Snapshot

from diary_kg.snapshots import DiarySnapshotManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metrics(
    chunk_count: int = 10,
    entry_count: int = 5,
    node_count: int = 20,
    edge_count: int = 15,
    topic_counts: dict | None = None,
    context_counts: dict | None = None,
) -> dict:
    return {
        "chunk_count": chunk_count,
        "entry_count": entry_count,
        "total_nodes": node_count,
        "total_edges": edge_count,
        "topic_counts": topic_counts or {"work": 4, "domestic": 3},
        "context_counts": context_counts or {"Home": 3, "Office": 2},
        "temporal_span": {"start": "1660-01-01T00:00", "end": "1667-04-15T22:30"},
        "chunking_strategy": "sentence_group",
        "chunk_size": 512,
    }


def _snapshot(
    tree_hash: str = "abc123",
    branch: str = "main",
    timestamp: str | None = None,
    chunk_count: int = 10,
    label: str | None = None,
) -> Snapshot:
    m = _make_metrics(chunk_count=chunk_count)
    if label is not None:
        m["label"] = label
    return Snapshot(
        branch=branch,
        timestamp=timestamp or datetime.now(UTC).isoformat(),
        version="0.1.0",
        metrics=m,
        tree_hash=tree_hash,
    )


def _make_mgr(tmp_path: Path) -> DiarySnapshotManager:
    return DiarySnapshotManager(tmp_path / "snapshots")


# ---------------------------------------------------------------------------
# DiarySnapshotManager — save / load
# ---------------------------------------------------------------------------


class TestSaveLoadSnapshot:
    def test_save_creates_json_file(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        s = _snapshot(tree_hash="aaa111")
        mgr.save_snapshot(s)
        assert (mgr.snapshots_dir / "aaa111.json").exists()

    def test_save_updates_manifest(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        mgr.save_snapshot(_snapshot(tree_hash="aaa111"))
        manifest = mgr.load_manifest()
        keys = [e["key"] for e in manifest.snapshots]
        assert "aaa111" in keys

    def test_save_rejects_zero_chunk_count(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        s = _snapshot(chunk_count=0)
        with pytest.raises(ValueError, match="0 chunks"):
            mgr.save_snapshot(s)

    def test_load_snapshot_returns_snapshot(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        s = _snapshot(tree_hash="bbb222")
        mgr.save_snapshot(s)
        loaded = mgr.load_snapshot("bbb222")
        assert loaded is not None
        assert loaded.key == "bbb222"

    def test_load_snapshot_missing_returns_none(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        assert mgr.load_snapshot("nonexistent") is None

    def test_upsert_same_key(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        s = _snapshot(tree_hash="ccc333", label="first")
        mgr.save_snapshot(s)
        s2 = _snapshot(tree_hash="ccc333", label="updated")
        mgr.save_snapshot(s2)
        manifest = mgr.load_manifest()
        entries = [e for e in manifest.snapshots if e["key"] == "ccc333"]
        assert len(entries) == 1  # upserted, not duplicated

    def test_empty_manifest_when_no_file(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        manifest = mgr.load_manifest()
        assert manifest.snapshots == []


# ---------------------------------------------------------------------------
# DiarySnapshotManager — list / diff / baseline / previous
# ---------------------------------------------------------------------------


class TestListSnapshots:
    def _populate(self, mgr: DiarySnapshotManager) -> list[str]:
        keys = []
        base_ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        for i, (key, chunk_count) in enumerate([("k1", 5), ("k2", 10), ("k3", 15)]):
            ts = (base_ts + timedelta(hours=i)).isoformat()
            s = _snapshot(tree_hash=key, timestamp=ts, chunk_count=chunk_count)
            mgr.save_snapshot(s)
            keys.append(key)
        return keys

    def test_returns_reverse_chronological(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        self._populate(mgr)
        snaps = mgr.list_snapshots()
        timestamps = [s["timestamp"] for s in snaps]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_limit_respected(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        self._populate(mgr)
        snaps = mgr.list_snapshots(limit=2)
        assert len(snaps) == 2

    def test_branch_filter(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        s1 = _snapshot(tree_hash="main1", branch="main")
        s2 = _snapshot(tree_hash="feat1", branch="feature")
        s1.timestamp = datetime(2024, 1, 1, tzinfo=UTC).isoformat()
        s2.timestamp = datetime(2024, 1, 2, tzinfo=UTC).isoformat()
        mgr.save_snapshot(s1, force=True)
        mgr.save_snapshot(s2, force=True)
        main_snaps = mgr.list_snapshots(branch="main")
        assert all(s.get("branch") == "main" for s in main_snaps)
        assert len(main_snaps) == 1

    def test_fills_vs_previous_delta(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        self._populate(mgr)
        snaps = mgr.list_snapshots()
        for snap in snaps[:-1]:
            assert snap.get("deltas", {}).get("vs_previous") is not None

    def test_empty_list_when_no_snapshots(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        assert mgr.list_snapshots() == []


class TestGetBaselineAndPrevious:
    def test_get_baseline_returns_oldest(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        old = _snapshot(tree_hash="old1", timestamp=datetime(2023, 1, 1, tzinfo=UTC).isoformat())
        new = _snapshot(tree_hash="new1", timestamp=datetime(2024, 1, 1, tzinfo=UTC).isoformat())
        mgr.save_snapshot(old, force=True)
        mgr.save_snapshot(new, force=True)
        baseline = mgr.get_baseline()
        assert baseline is not None
        assert baseline.key == "old1"

    def test_get_baseline_empty_returns_none(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        assert mgr.get_baseline() is None

    def test_get_previous_returns_immediately_before(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        s1 = _snapshot(tree_hash="s1", timestamp=datetime(2024, 1, 1, tzinfo=UTC).isoformat())
        s2 = _snapshot(tree_hash="s2", timestamp=datetime(2024, 1, 2, tzinfo=UTC).isoformat())
        s3 = _snapshot(tree_hash="s3", timestamp=datetime(2024, 1, 3, tzinfo=UTC).isoformat())
        for s in [s1, s2, s3]:
            mgr.save_snapshot(s, force=True)
        prev = mgr.get_previous("s3")
        assert prev is not None
        assert prev.key == "s2"

    def test_get_previous_for_oldest_returns_none(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        s = _snapshot(tree_hash="only")
        mgr.save_snapshot(s)
        assert mgr.get_previous("only") is None

    def test_get_previous_unknown_key_returns_none(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        assert mgr.get_previous("doesnotexist") is None


class TestDiffSnapshots:
    def test_diff_returns_a_b_delta(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        a = _snapshot(tree_hash="sa", chunk_count=10)
        b = _snapshot(tree_hash="sb", chunk_count=20)
        mgr.save_snapshot(a)
        mgr.save_snapshot(b)
        result = mgr.diff_snapshots("sa", "sb")
        assert "a" in result
        assert "b" in result
        assert "delta" in result
        assert result["delta"]["chunks"] == 10

    def test_diff_topic_counts_delta(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        a = _snapshot(tree_hash="sa")
        a.metrics["topic_counts"] = {"work": 2, "domestic": 3}
        b = _snapshot(tree_hash="sb")
        b.metrics["topic_counts"] = {"work": 5, "domestic": 3, "social": 1}
        mgr.save_snapshot(a)
        mgr.save_snapshot(b)
        result = mgr.diff_snapshots("sa", "sb")
        assert "topic_counts_delta" in result
        assert result["topic_counts_delta"].get("work") == 3
        assert result["topic_counts_delta"].get("social") == 1
        assert "domestic" not in result["topic_counts_delta"]

    def test_diff_missing_key_returns_error(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        result = mgr.diff_snapshots("missing_a", "missing_b")
        assert "error" in result


# ---------------------------------------------------------------------------
# DiarySnapshotManager — capture
# ---------------------------------------------------------------------------


class TestCapture:
    def test_capture_returns_snapshot(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        info = {
            "chunk_count": 10,
            "entry_count": 5,
            "topic_counts": {"work": 3},
            "context_counts": {"Office": 2},
            "temporal_span": {"start": "1660-01-01", "end": "1667-04-15"},
            "chunking_strategy": "sentence_group",
            "chunk_size": 512,
        }
        db_stats = {"node_count": 20, "edge_count": 15}
        snap = mgr.capture_diary(
            version="0.1.0",
            info=info,
            db_stats=db_stats,
            branch="main",
            tree_hash="testhash",
            label="test capture",
            source_file="pepys.txt",
        )
        assert isinstance(snap, Snapshot)
        assert snap.metrics["chunk_count"] == 10
        assert snap.metrics["total_nodes"] == 20
        assert snap.metrics.get("label") == "test capture"
        assert snap.metrics.get("source_file") == "pepys.txt"
        # The tree hash is provenance, not the key. With no key supplied the
        # base assigns a UTC timestamp, which is the right answer for a corpus.
        assert snap.tree_hash == "testhash"
        assert snap.key != "testhash"
        datetime.fromisoformat(snap.key)

    def test_vs_previous_is_resolved_on_read_not_at_capture(self, tmp_path):
        """The delta is computed by the read path, not frozen into the file.

        This class used to override get_previous() to resolve an unsaved key to
        the most recently *saved* snapshot, so capture() could fill vs_previous
        and persist it. That was removed in 0.99.0. Two reasons: nothing reads
        vs_previous from raw JSON -- every consumer goes through
        load_snapshot() -- and a persisted value can go stale. "Most recently
        saved" is not "chronologically previous", so a snapshot that arrives out
        of order leaves the stored delta wrong, and because load_snapshot only
        backfills when vs_previous is None, a stored value permanently
        suppresses the correction.

        Capture now leaves it None and load_snapshot fills it through
        _compute_delta_from_metrics, which keeps the diary-specific fields.
        """
        mgr = _make_mgr(tmp_path)
        first = _snapshot(
            tree_hash="first", chunk_count=5, timestamp=datetime(2024, 1, 1, tzinfo=UTC).isoformat()
        )
        mgr.save_snapshot(first)

        info = {
            "chunk_count": 10,
            "entry_count": 5,
            "topic_counts": {},
            "context_counts": {},
            "temporal_span": None,
            "chunking_strategy": "",
            "chunk_size": 512,
        }
        db_stats = {"node_count": 20, "edge_count": 0}
        snap = mgr.capture_diary(
            version="0.2.0",
            info=info,
            db_stats=db_stats,
            branch="main",
            tree_hash="second",
            key="v0.2.0",
        )
        # Unsaved key: the base cannot resolve a predecessor yet.
        assert snap.vs_previous is None
        mgr.save_snapshot(snap)

        reloaded = mgr.load_snapshot("v0.2.0")
        assert reloaded is not None
        assert reloaded.vs_previous is not None
        assert reloaded.vs_previous["chunks"] == 5  # 10 - 5
        assert reloaded.vs_previous["entries"] == 0

    def test_a_late_arriving_snapshot_corrects_the_previous_delta(self, tmp_path):
        """The read path recomputes; a persisted delta could not.

        B is captured after A, then C lands between them chronologically. B's
        true predecessor becomes C, and the delta reported for B follows.
        """
        mgr = _make_mgr(tmp_path)

        def save(key, ts, chunks):
            snap = _snapshot(chunk_count=chunks, timestamp=ts)
            snap.snapshot_key = key
            mgr.save_snapshot(snap, force=True)

        save("A", datetime(2024, 1, 1, tzinfo=UTC).isoformat(), 10)
        save("B", datetime(2024, 3, 1, tzinfo=UTC).isoformat(), 30)
        assert mgr.load_snapshot("B").vs_previous["chunks"] == 20  # vs A

        save("C", datetime(2024, 2, 1, tzinfo=UTC).isoformat(), 20)
        assert mgr.load_snapshot("B").vs_previous["chunks"] == 10  # now vs C

    def test_capture_non_int_node_count_treated_as_zero(self, tmp_path):
        mgr = _make_mgr(tmp_path)
        snap = mgr.capture_diary(
            version="0.1.0",
            info={"chunk_count": 5, "entry_count": 2},
            db_stats={"node_count": "n/a", "edge_count": "n/a"},
            branch="main",
            tree_hash="xyz",
        )
        assert snap.metrics["total_nodes"] == 0
        assert snap.metrics["total_edges"] == 0


# ---------------------------------------------------------------------------
# The deleted overrides: each behaviour now comes from a base extension point
#
# 0.99.0 removed __init__ and diff_snapshots from this module. get_previous
# stays; see its docstring. These tests pin what the deleted overrides did.
# ---------------------------------------------------------------------------


class TestBaseExtensionPoints:
    def test_package_name_comes_from_the_class_attribute(self, tmp_path: Path) -> None:
        """Replaces the deleted __init__, whose only job was this string.

        Against kgmodule-utils < 0.20.0 the base has no package_name class
        attribute, so every snapshot's tool field would read "kg-utils".
        """
        assert DiarySnapshotManager.package_name == "diary-kg"
        assert _make_mgr(tmp_path).package_name == "diary-kg"

    def test_save_and_reload_persists_key_subject_and_tool(self, tmp_path: Path) -> None:
        """The round trip this repo had no test for at all.

        key, subject, tool and tool_version are the four fields a hand-written
        save_snapshot copy dropped in the sibling packages. Assert them from
        the file on disk, then again after a reload.
        """
        import json

        mgr = _make_mgr(tmp_path)
        snap = Snapshot(
            branch="main",
            timestamp=datetime.now(UTC).isoformat(),
            version="9.9.9",
            metrics=_make_metrics(),
            tree_hash="e" * 40,
            snapshot_key="v9.9.9",
            subject="corpus:pepys",
            tool="diary-kg",
            tool_version="9.9.9",
        )
        saved = mgr.save_snapshot(snap)
        assert saved is not None and saved.name == "v9.9.9.json"

        on_disk = json.loads(saved.read_text(encoding="utf-8"))
        assert on_disk["key"] == "v9.9.9"
        assert on_disk["subject"] == "corpus:pepys"
        assert on_disk["tree_hash"] == "e" * 40
        assert on_disk["tool"] == "diary-kg"
        assert on_disk["tool_version"] == "9.9.9"

        reloaded = mgr.load_snapshot("v9.9.9")
        assert reloaded is not None
        assert reloaded.key == "v9.9.9"
        assert reloaded.subject == "corpus:pepys"
        assert reloaded.tool == "diary-kg"

    def test_diff_carries_topic_counts_delta(self, tmp_path: Path) -> None:
        """Replaces the deleted diff_snapshots: only changed topics appear.

        The override also re-loaded both snapshots to build this; the base
        reads the metrics it already has.
        """
        mgr = _make_mgr(tmp_path)
        for key, topics in (
            ("d_a", {"work": 4, "same": 2, "gone": 3}),
            ("d_b", {"work": 9, "same": 2, "new": 1}),
        ):
            snap = Snapshot(
                branch="main",
                timestamp=datetime.now(UTC).isoformat(),
                version="0.1.0",
                metrics=_make_metrics(topic_counts=topics),
                snapshot_key=key,
            )
            mgr.save_snapshot(snap, force=True)

        result = mgr.diff_snapshots("d_a", "d_b")
        assert result["topic_counts_delta"] == {"work": 5, "gone": -3, "new": 1}

    def test_diff_carries_timestamp_and_issues_delta(self, tmp_path: Path) -> None:
        """Both now come from the base rather than a module override."""
        mgr = _make_mgr(tmp_path)
        for key, issues in (("d_a", ["kept", "gone"]), ("d_b", ["kept", "new"])):
            snap = Snapshot(
                branch="main",
                timestamp=datetime.now(UTC).isoformat(),
                version="0.1.0",
                metrics=_make_metrics(),
                issues=issues,
                snapshot_key=key,
            )
            mgr.save_snapshot(snap, force=True)

        result = mgr.diff_snapshots("d_a", "d_b")
        assert result["a"]["timestamp"] and result["b"]["timestamp"]
        assert result["issues_delta"] == {"introduced": ["new"], "resolved": ["gone"]}

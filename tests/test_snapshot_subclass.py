"""
test_snapshot_subclass.py — Verify DiarySnapshotManager inherits from kg_utils.snapshots.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from kg_utils.snapshots import Snapshot, SnapshotManager

from diary_kg.snapshots import DiarySnapshotManager


@pytest.fixture
def mgr(tmp_path: Path) -> DiarySnapshotManager:
    return DiarySnapshotManager(tmp_path / "snapshots")


@pytest.fixture
def sample_info() -> dict:
    return {
        "chunk_count": 200,
        "entry_count": 42,
        "topic_counts": {"science": 10, "philosophy": 8},
        "context_counts": {"personal": 20, "work": 22},
        "temporal_span": {"start": "2020-01-01", "end": "2026-01-01"},
        "chunking_strategy": "semantic",
        "chunk_size": 512,
        "source_file": "diary.md",
    }


@pytest.fixture
def sample_db_stats() -> dict:
    return {"node_count": 350, "edge_count": 480}


def test_inherits_from_base() -> None:
    assert issubclass(DiarySnapshotManager, SnapshotManager)


def test_git_helpers_inherited(mgr: DiarySnapshotManager) -> None:
    """_get_current_branch and _get_current_tree_hash come from base."""
    branch = mgr._get_current_branch()
    tree_hash = mgr._get_current_tree_hash()
    assert isinstance(branch, str) and len(branch) > 0
    assert isinstance(tree_hash, str) and len(tree_hash) > 0


def test_capture_returns_snapshot(
    mgr: DiarySnapshotManager, sample_info: dict, sample_db_stats: dict
) -> None:
    with (
        patch.object(DiarySnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(DiarySnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture_diary(version="1.0.0", info=sample_info, db_stats=sample_db_stats)

    assert isinstance(snap, Snapshot)
    assert isinstance(snap.metrics, dict)


def test_metrics_dict_access(
    mgr: DiarySnapshotManager, sample_info: dict, sample_db_stats: dict
) -> None:
    with (
        patch.object(DiarySnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(DiarySnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture_diary(version="1.0.0", info=sample_info, db_stats=sample_db_stats)

    assert snap.metrics["chunk_count"] == 200
    assert snap.metrics["entry_count"] == 42
    assert snap.metrics["total_nodes"] == 350
    assert snap.metrics["total_edges"] == 480
    assert snap.metrics["chunking_strategy"] == "semantic"


def test_save_and_load_preserves_metrics(
    mgr: DiarySnapshotManager, sample_info: dict, sample_db_stats: dict
) -> None:
    with (
        patch.object(DiarySnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(DiarySnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture_diary(version="1.0.0", info=sample_info, db_stats=sample_db_stats)
    mgr.save_snapshot(snap)

    loaded = mgr.load_snapshot("hash001")
    assert loaded is not None
    assert isinstance(loaded.metrics, dict)
    assert loaded.metrics["chunk_count"] == 200
    assert loaded.metrics["topic_counts"]["science"] == 10


def test_delta_backfilled_on_load(
    mgr: DiarySnapshotManager, sample_info: dict, sample_db_stats: dict
) -> None:
    """vs_previous is backfilled from manifest on load, not set at capture time."""
    with (
        patch.object(DiarySnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(DiarySnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap_a = mgr.capture_diary(version="1.0.0", info=sample_info, db_stats=sample_db_stats)
    mgr.save_snapshot(snap_a)

    info_b = dict(sample_info, chunk_count=220, entry_count=45)
    with (
        patch.object(DiarySnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(DiarySnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        snap_b = mgr.capture_diary(version="1.0.1", info=info_b, db_stats=sample_db_stats)
    mgr.save_snapshot(snap_b)

    loaded = mgr.load_snapshot("hash002")
    assert loaded is not None
    assert isinstance(loaded.vs_previous, dict)
    assert loaded.vs_previous["chunks"] == 20
    assert loaded.vs_previous["entries"] == 3


def test_save_rejects_zero_chunks(mgr: DiarySnapshotManager, sample_db_stats: dict) -> None:
    empty_info = {
        "chunk_count": 0,
        "entry_count": 0,
        "topic_counts": {},
        "context_counts": {},
        "temporal_span": {},
        "chunking_strategy": "",
        "chunk_size": 512,
    }
    with (
        patch.object(DiarySnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(DiarySnapshotManager, "_get_current_tree_hash", return_value="hash000"),
    ):
        snap = mgr.capture_diary(version="0.0.0", info=empty_info, db_stats=sample_db_stats)
    with pytest.raises(ValueError, match="0 chunks"):
        mgr.save_snapshot(snap)

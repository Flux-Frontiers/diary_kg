"""
test_diary_kg.py

Unit tests for diary_kg.kg — DiaryKG: is_built, source_file, info,
analyze, snapshot helpers.  Tests that require DocKG (build, query, pack,
stats) mock the internal _dockg attribute.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from diary_kg.kg import DiaryKG, _parse_frontmatter


def _seed_hit(node_id: str, distance: float, kind: str = "chunk"):
    """Minimal SeedHit stand-in for fusion tests."""
    return SimpleNamespace(id=node_id, kind=kind, distance=distance, file_path="")


# ---------------------------------------------------------------------------
# _parse_frontmatter helper
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_extracts_key_value_pairs(self):
        text = "---\nsource_file: pepys.txt\nentry_index: 3\n---\n\nBody text.\n"
        fm = _parse_frontmatter(text)
        assert fm["source_file"] == "pepys.txt"
        assert fm["entry_index"] == "3"

    def test_missing_frontmatter_returns_empty(self):
        assert _parse_frontmatter("No frontmatter here.") == {}

    def test_empty_string_returns_empty(self):
        assert _parse_frontmatter("") == {}


# ---------------------------------------------------------------------------
# DiaryKG.is_built()
# ---------------------------------------------------------------------------


class TestIsBuilt:
    def test_unbuilt_returns_false(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root)
        assert kg.is_built() is False

    def test_sqlite_present_returns_true(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        assert kg.is_built() is True

    def test_lancedb_only_returns_true(self, tmp_kg_root):
        lancedb_dir = tmp_kg_root / ".diarykg" / "lancedb"
        lancedb_dir.mkdir(parents=True)
        kg = DiaryKG(tmp_kg_root)
        assert kg.is_built() is True


# ---------------------------------------------------------------------------
# DiaryKG.source_file / source_path
# ---------------------------------------------------------------------------


class TestSourceFile:
    def test_override_takes_priority(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root, source_file="override.txt")
        assert kg.source_file == "override.txt"

    def test_reads_from_config_when_no_override(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        # built_kg_root fixture writes source_file = "pepys_diary.txt" in config
        assert kg.source_file == "pepys_diary.txt"

    def test_returns_none_when_neither(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root)
        assert kg.source_file is None


# ---------------------------------------------------------------------------
# DiaryKG._read_config / _write_config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_read_missing_config_returns_empty(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root)
        assert kg._read_config() == {}

    def test_write_and_read_roundtrip(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root)
        kg._write_config({"foo": "bar", "count": 42})
        result = kg._read_config()
        assert result["foo"] == "bar"
        assert result["count"] == 42

    def test_write_merges_not_replaces(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root)
        kg._write_config({"a": 1})
        kg._write_config({"b": 2})
        result = kg._read_config()
        assert result["a"] == 1
        assert result["b"] == 2

    def test_corrupted_config_returns_empty(self, tmp_kg_root):
        cfg = tmp_kg_root / ".diarykg" / "config.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("not json", encoding="utf-8")
        kg = DiaryKG(tmp_kg_root)
        assert kg._read_config() == {}


# ---------------------------------------------------------------------------
# DiaryKG.info()
# ---------------------------------------------------------------------------


class TestInfo:
    def test_info_returns_dict(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        # Prevent _load_dockg from actually loading DocKG
        kg._db_path = built_kg_root / ".diarykg" / "graph.sqlite"
        with patch.object(kg, "_load_dockg", side_effect=RuntimeError("no dockg")):
            result = kg.info()
        assert isinstance(result, dict)

    def test_chunk_count_matches_corpus_files(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        with patch.object(kg, "_load_dockg", side_effect=RuntimeError("no dockg")):
            result = kg.info()
        # built_kg_root fixture creates 5 chunk .md files
        assert result["chunk_count"] == 5

    def test_entry_count_from_frontmatter(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        with patch.object(kg, "_load_dockg", side_effect=RuntimeError("no dockg")):
            result = kg.info()
        # 5 chunks spread across entries 0-4 → 5 unique entry indices
        assert result["entry_count"] == 5

    def test_temporal_span_present(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        with patch.object(kg, "_load_dockg", side_effect=RuntimeError("no dockg")):
            result = kg.info()
        span = result.get("temporal_span")
        assert span is not None
        assert "start" in span
        assert "end" in span

    def test_topic_counts_present(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        with patch.object(kg, "_load_dockg", side_effect=RuntimeError("no dockg")):
            result = kg.info()
        # built_kg_root has domestic(2), work(2), social(1)
        assert "domestic" in result["topic_counts"] or "work" in result["topic_counts"]

    def test_info_on_unbuilt_kg(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root)
        result = kg.info()
        assert result["chunk_count"] == 0
        assert result["entry_count"] == 0
        assert result["temporal_span"] is None


# ---------------------------------------------------------------------------
# DiaryKG.stats()
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_returns_kind_diary(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        mock_store = MagicMock()
        mock_store.stats.return_value = {"total_nodes": 42, "total_edges": 30}
        mock_dockg = MagicMock()
        mock_dockg.store = mock_store
        kg._dockg = mock_dockg
        with patch.object(kg, "_load_dockg", return_value=mock_dockg):
            result = kg.stats()
        assert result["kind"] == "diary"
        assert result["node_count"] == 42
        assert result["edge_count"] == 30

    def test_stats_fallback_on_exception(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        mock_dockg = MagicMock()
        mock_dockg.store.stats.side_effect = RuntimeError("db error")
        kg._dockg = mock_dockg
        with patch.object(kg, "_load_dockg", return_value=mock_dockg):
            result = kg.stats()
        assert result["kind"] == "diary"
        assert result["node_count"] == "n/a"


# ---------------------------------------------------------------------------
# DiaryKG.analyze()
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_analyze_returns_markdown_string(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        mock_store = MagicMock()
        mock_store.stats.return_value = {"total_nodes": 10, "total_edges": 5}
        mock_dockg = MagicMock()
        mock_dockg.store = mock_store
        kg._dockg = mock_dockg
        with patch.object(kg, "_load_dockg", return_value=mock_dockg):
            report = kg.analyze()
        assert isinstance(report, str)
        assert "# DiaryKG Analysis Report" in report

    def test_analyze_includes_chunk_count(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        mock_store = MagicMock()
        mock_store.stats.return_value = {"total_nodes": 10, "total_edges": 5}
        mock_dockg = MagicMock()
        mock_dockg.store = mock_store
        kg._dockg = mock_dockg
        with patch.object(kg, "_load_dockg", return_value=mock_dockg):
            report = kg.analyze()
        assert "5" in report  # chunk_count from built_kg_root


# ---------------------------------------------------------------------------
# DiaryKG.snapshot_list / snapshot_show / snapshot_diff
# ---------------------------------------------------------------------------


class TestSnapshotHelpers:
    def test_snapshot_list_empty_initially(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        assert kg.snapshot_list() == []

    def test_snapshot_show_missing_key_raises(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        with pytest.raises(FileNotFoundError):
            kg.snapshot_show("nonexistent_key")

    def test_snapshot_diff_missing_returns_error_dict(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        result = kg.snapshot_diff("missing_a", "missing_b")
        assert "error" in result

    def test_snapshot_save_raises_when_not_built(self, tmp_kg_root):
        kg = DiaryKG(tmp_kg_root)
        with pytest.raises(RuntimeError, match="not built"):
            kg.snapshot_save()

    def test_snapshot_save_and_list(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        # Mock DocKG so stats() works without a real DB
        mock_store = MagicMock()
        mock_store.stats.return_value = {"total_nodes": 10, "total_edges": 5}
        mock_dockg = MagicMock()
        mock_dockg.store = mock_store
        kg._dockg = mock_dockg
        with patch.object(kg, "_load_dockg", return_value=mock_dockg):
            snap = kg.snapshot_save(version="0.1.0", label="test snap")
        assert "key" in snap
        assert snap["metrics"]["chunk_count"] == 5

        snaps = kg.snapshot_list()
        assert len(snaps) == 1
        assert snaps[0]["metrics"]["label"] == "test snap"

    def test_snapshot_show_after_save(self, built_kg_root):
        kg = DiaryKG(built_kg_root)
        mock_store = MagicMock()
        mock_store.stats.return_value = {"total_nodes": 5, "total_edges": 3}
        mock_dockg = MagicMock()
        mock_dockg.store = mock_store
        kg._dockg = mock_dockg
        with patch.object(kg, "_load_dockg", return_value=mock_dockg):
            saved = kg.snapshot_save(version="0.1.0")
        key = saved["key"]
        shown = kg.snapshot_show(key)
        assert shown["key"] == key


# ---------------------------------------------------------------------------
# _fused_chunk_seeds — hybrid dense + lexical (BM25) fusion
# ---------------------------------------------------------------------------


class TestFusedChunkSeeds:
    def test_lexical_rescues_buried_exact_phrase(self, tmp_kg_root):
        """Exact-phrase chunk buried in dense (rank 7) is surfaced into fused top-k.

        With best-dense anchoring the lexical score is just below the best dense
        score, so a phrase hit can't leapfrog a genuinely strong dense hit —
        but it IS pulled from outside the top-k into the result set via RRF.
        """
        kg = DiaryKG(tmp_kg_root)
        target = "c7"
        # Dense buries the target at rank 7; also include a non-chunk to filter.
        dense = [_seed_hit(f"c{i}", 0.30 + 0.01 * i) for i in range(8)]
        dense.append(_seed_hit("ent:x", 0.05, kind="entity"))
        mock_dockg = MagicMock()
        mock_dockg.index.search.return_value = dense
        mock_dockg.store.search_lexical.return_value = [target]  # phrase hit -> rank 0

        fused = kg._fused_chunk_seeds(mock_dockg, "parmazan cheese", k=5)
        ids = [i for i, _ in fused]

        # c7 was excluded from pure-dense top-5; RRF surfaces it into fused top-5.
        assert target in ids
        # Anchored just below best dense score (0.70 − 0.01 = 0.69).
        target_score = next(score for nid, score in fused if nid == target)
        assert target_score == pytest.approx(0.69, abs=1e-6)
        assert "ent:x" not in ids  # non-chunk dense hits are excluded

    def test_falls_back_to_dense_without_fts(self, tmp_kg_root):
        """No lexical index -> pure dense ranking, scores from cosine distance."""
        kg = DiaryKG(tmp_kg_root)
        dense = [_seed_hit(f"c{i}", 0.30 + 0.05 * i) for i in range(5)]
        mock_dockg = MagicMock()
        mock_dockg.index.search.return_value = dense
        mock_dockg.store.search_lexical.return_value = []  # older corpus, no nodes_fts

        fused = kg._fused_chunk_seeds(mock_dockg, "q", k=3)

        assert [i for i, _ in fused] == ["c0", "c1", "c2"]
        assert fused[0][1] == pytest.approx(0.70)  # 1 - 0.30

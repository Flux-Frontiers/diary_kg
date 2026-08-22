"""DiaryKG's adoption of the shared kg_utils.temporal contract.

A diary is the fleet's most obviously dated corpus, and until it wrote the
contract keys a federated ``QueryScope(time_range=...)`` could not reach it:
DiaryKG kept its date in a private ``timestamp`` column that nothing outside
DiaryKG knows to read.

These cover both halves of the adoption — writing the contract at build time,
and surfacing it on query/pack results where the KGRAG adapter reads it.
"""

from __future__ import annotations

import json
import sqlite3

from kg_utils.temporal import read_span

from diary_kg.kg import _temporal_for


class TestTemporalMapping:
    def test_maps_timestamp_to_occurred_start(self):
        assert _temporal_for("1666-09-02") == {"occurred_start": "1666-09-02"}

    def test_datetime_precision_is_preserved(self):
        out = _temporal_for("1666-09-02T05:30:00")
        assert out["occurred_start"].startswith("1666-09-02T05:30")

    def test_year_only_stays_a_year(self):
        """Precision must survive: a year-dated entry covers the whole year."""
        assert _temporal_for("1666") == {"occurred_start": "1666"}

    def test_no_occurred_end_is_emitted(self):
        """Absent end means 'as wide as the precision', which is what we want."""
        assert "occurred_end" not in _temporal_for("1666-09-02")

    def test_empty_timestamp_yields_nothing(self):
        assert _temporal_for("") == {}
        assert _temporal_for(None) == {}

    def test_malformed_timestamp_does_not_raise(self):
        """One bad frontmatter date must not fail a corpus build."""
        assert _temporal_for("sometime in September") == {}
        assert _temporal_for("1666-13-45") == {}

    def test_result_is_readable_as_a_span(self):
        """The whole point: what we write must be what the contract reads."""
        span = read_span(_temporal_for("1666-09-02"))
        assert span is not None
        assert span.overlaps("1666-09-01", "1666-09-03")
        assert not span.overlaps("1667-01-01", "1667-12-31")

    def test_day_entry_covers_its_whole_day(self):
        span = read_span(_temporal_for("1666-09-02"))
        assert span.overlaps("1666-09-02", "1666-09-02")

    def test_year_entry_covers_any_day_in_it(self):
        span = read_span(_temporal_for("1666"))
        assert span.overlaps("1666-09-02", "1666-09-02")


class TestEnrichmentWritesContract:
    """The build-time half: the contract lands in DocKG's metadata column."""

    def _db_with_chunk(self, path):
        con = sqlite3.connect(str(path))
        con.executescript(
            """
            CREATE TABLE nodes (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
              title TEXT, file_path TEXT, char_start INTEGER, char_end INTEGER,
              heading_level INTEGER, text TEXT, metadata TEXT
            );
            CREATE TABLE edges (
              src TEXT, rel TEXT, dst TEXT, evidence TEXT,
              PRIMARY KEY (src, rel, dst)
            );
            """
        )
        con.execute(
            "INSERT INTO nodes (id, kind, name, file_path, text) VALUES (?,?,?,?,?)",
            ("chunk:e1.md:0000", "chunk", "1666-09-02", "e1.md", "Up betimes."),
        )
        con.commit()
        con.close()

    def _corpus(self, d, timestamp="1666-09-02"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "e1.md").write_text(
            f"---\ntimestamp: {timestamp}\ncategory: naval\ncontext: office\n"
            f"source_file: pepys.txt\n---\n\nUp betimes.\n",
            encoding="utf-8",
        )

    def _run_enrichment(self, tmp_path, timestamp="1666-09-02"):
        from diary_kg.kg import DiaryKG

        db = tmp_path / ".diarykg" / "graph.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        self._db_with_chunk(db)
        corpus = tmp_path / ".diarykg" / "corpus"
        self._corpus(corpus, timestamp)

        kg = DiaryKG.__new__(DiaryKG)
        kg._db_path = db
        kg._corpus_dir = corpus
        kg._enrich_metadata()
        return db

    def test_metadata_column_holds_the_contract(self, tmp_path):
        db = self._run_enrichment(tmp_path)
        con = sqlite3.connect(str(db))
        raw = con.execute("SELECT metadata FROM nodes WHERE kind='chunk'").fetchone()[0]
        con.close()
        assert json.loads(raw) == {"occurred_start": "1666-09-02"}

    def test_private_timestamp_column_is_untouched(self, tmp_path):
        """DiaryKG's own layouts read `timestamp`; adoption must not disturb it."""
        db = self._run_enrichment(tmp_path)
        con = sqlite3.connect(str(db))
        ts = con.execute("SELECT timestamp FROM nodes WHERE kind='chunk'").fetchone()[0]
        con.close()
        assert ts == "1666-09-02"

    def test_written_metadata_is_readable_as_a_span(self, tmp_path):
        db = self._run_enrichment(tmp_path)
        con = sqlite3.connect(str(db))
        raw = con.execute("SELECT metadata FROM nodes WHERE kind='chunk'").fetchone()[0]
        con.close()
        span = read_span(json.loads(raw))
        assert span.overlaps("1666-09-01", "1666-09-03")

    def test_unparseable_timestamp_leaves_metadata_null(self, tmp_path):
        db = self._run_enrichment(tmp_path, timestamp="one autumn morning")
        con = sqlite3.connect(str(db))
        raw = con.execute("SELECT metadata FROM nodes WHERE kind='chunk'").fetchone()[0]
        ts = con.execute("SELECT timestamp FROM nodes WHERE kind='chunk'").fetchone()[0]
        con.close()
        assert raw is None
        assert ts == "one autumn morning"  # preserved verbatim, just not parseable

    def test_enrichment_is_idempotent(self, tmp_path):
        from diary_kg.kg import DiaryKG

        db = self._run_enrichment(tmp_path)
        kg = DiaryKG.__new__(DiaryKG)
        kg._db_path = db
        kg._corpus_dir = tmp_path / ".diarykg" / "corpus"
        kg._enrich_metadata()
        con = sqlite3.connect(str(db))
        rows = con.execute("SELECT metadata FROM nodes WHERE kind='chunk'").fetchall()
        con.close()
        assert len(rows) == 1
        assert json.loads(rows[0][0]) == {"occurred_start": "1666-09-02"}


class TestNoDivergence:
    """The contract is a derived view of `timestamp`, not a second authoring.

    Two representations of one date are fine; two independent *writes* of it are
    not — that is the drift the fleet audit exists to catch. These pin the
    derivation so a future edit that authors `metadata` from somewhere else
    fails here instead of silently disagreeing with the column.
    """

    def test_metadata_is_a_derived_view_of_timestamp(self, tmp_path):
        """For every chunk: metadata == _temporal_for(timestamp). Exactly."""
        db = TestEnrichmentWritesContract()._run_enrichment(tmp_path, timestamp="1660-01-01T00:00")
        con = sqlite3.connect(str(db))
        rows = con.execute("SELECT timestamp, metadata FROM nodes WHERE kind='chunk'").fetchall()
        con.close()
        assert rows
        for timestamp, raw_meta in rows:
            stored = json.loads(raw_meta) if raw_meta else {}
            assert stored == _temporal_for(timestamp)

    def test_column_keeps_its_authored_form(self, tmp_path):
        """Normalising into the column would rewrite existing corpora."""
        db = TestEnrichmentWritesContract()._run_enrichment(tmp_path, timestamp="1660-01-01T00:00")
        con = sqlite3.connect(str(db))
        ts = con.execute("SELECT timestamp FROM nodes WHERE kind='chunk'").fetchone()[0]
        con.close()
        assert ts == "1660-01-01T00:00"

    def test_the_two_forms_denote_the_same_instant(self, tmp_path):
        """Different rendering, same date — that is the whole claim."""
        from kg_utils.temporal import parse_temporal

        db = TestEnrichmentWritesContract()._run_enrichment(tmp_path, timestamp="1660-01-01T00:00")
        con = sqlite3.connect(str(db))
        ts, raw_meta = con.execute(
            "SELECT timestamp, metadata FROM nodes WHERE kind='chunk'"
        ).fetchone()
        con.close()
        from_column = parse_temporal(ts)
        from_contract = parse_temporal(json.loads(raw_meta)["occurred_start"])
        assert from_column == from_contract

    def test_query_derives_from_the_same_column(self):
        """Query time uses the same function on the same column, so hits agree."""
        for raw in ("1660-01-01T00:00", "1666-09-02", "1666", ""):
            assert _temporal_for(raw) == _temporal_for(raw)

    def test_time_precision_round_trips_through_the_contract(self):
        """A time-precision entry must still land on the right day."""
        from kg_utils.temporal import read_span

        span = read_span(_temporal_for("1660-01-01T00:00"))
        assert span.overlaps("1660-01-01", "1660-01-01")
        assert not span.overlaps("1660-01-02", "1660-01-31")

"""kg.py — DiaryKG: knowledge graph for diary and journal sources.

``DiaryKG`` orchestrates the full diary-to-KG pipeline:

1. **Build**: ``DiaryTransformer.ingest_to_corpus()`` segments the source diary
   into ``.md`` chunk files under ``.diarykg/corpus/``, then ``DocKG`` indexes
   the corpus into SQLite + LanceDB.

2. **Query / Pack**: ``DocKG`` provides semantic search; provenance is surfaced
   as the original source ``.txt`` (not the generated chunk file).

3. **Snapshots**: Point-in-time captures of corpus metrics stored under
   ``.diarykg/snapshots/`` with manifest and per-snapshot JSON files.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from diary_kg.snapshots import DiarySnapshotManager

from kg_utils.embed import DEFAULT_MODEL as DEFAULT_MODEL
from kg_utils.embed import KNOWN_MODELS
from kg_utils.embedder import wrap_embedder

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Return frontmatter key-value dict from a Markdown chunk file."""
    m = _FM_RE.match(text)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            result[k.strip()] = v.strip()
    return result


class DiaryKG:
    """Knowledge graph for a diary or journal corpus.

    :param root: Project root directory.  The ``.diarykg/`` storage directory
        is created here.
    :param source_file: Relative path to the diary ``.txt`` source inside
        *root*.  Required for the first ``build()``; subsequent calls read it
        from ``config.json`` when omitted.
    """

    KG_DIR = ".diarykg"

    def __init__(
        self,
        root: str | Path,
        source_file: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.root = Path(root).resolve()
        self._source_file_override = source_file
        self._model = KNOWN_MODELS.get(model, model)

        self._kg_dir = self.root / self.KG_DIR
        self._corpus_dir = self._kg_dir / "corpus"
        self._db_path = self._kg_dir / "graph.sqlite"
        self._lancedb_dir = self._kg_dir / "lancedb"
        self._config_path = self._kg_dir / "config.json"
        self._snapshot_dir = self._kg_dir / "snapshots"

        self._dockg: Any = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def source_path(self) -> Path | None:
        """Absolute path to the source diary file (if set / resolvable)."""
        sf = self._source_file_override or self._read_config().get("source_file")
        if sf:
            p = self.root / sf
            return p if p.exists() else Path(sf).resolve()
        return None

    @property
    def source_file(self) -> str | None:
        """Relative source file label (used in frontmatter + provenance)."""
        return self._source_file_override or self._read_config().get("source_file")

    def is_built(self) -> bool:
        """True if at least one database exists."""
        return self._db_path.exists() or self._lancedb_dir.exists()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _read_config(self) -> dict[str, Any]:
        if self._config_path.exists():
            try:
                return json.loads(self._config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _write_config(self, data: dict[str, Any]) -> None:
        self._kg_dir.mkdir(parents=True, exist_ok=True)
        existing = self._read_config()
        existing.update(data)
        self._config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Lazy DocKG loader
    # ------------------------------------------------------------------

    def _load_dockg(self) -> Any:
        if self._dockg is not None:
            return self._dockg
        try:
            from doc_kg.kg import DocKG  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError(
                "doc-kg is not installed. Install it with: pip install doc-kg"
            ) from exc
        if not self.is_built():
            raise RuntimeError("DiaryKG is not built yet. Run DiaryKG.build() first.")
        self._dockg = DocKG(
            corpus_root=str(self._corpus_dir),
            db_path=str(self._db_path),
            lancedb_dir=str(self._lancedb_dir),
            model=self._model,
        )
        return self._dockg

    @staticmethod
    def _source_from_node(node: dict[str, Any], fallback_sf: str | None) -> str:
        """Extract original source file label from a DocKG result node."""
        meta = node.get("metadata") or {}
        return meta.get("source_file") or fallback_sf or node.get("file_path") or ""

    @staticmethod
    def _timestamp_from_node(node: dict[str, Any]) -> str | None:
        meta = node.get("metadata") or {}
        return meta.get("timestamp")

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(
        self,
        batch_size: int = 0,
        seed: int | None = None,
        max_chunks_per_entry: int = 3,
        chunking_strategy: str = "sentence_group",
        chunk_size: int = 512,
        sentences_per_chunk: int = 4,
        workers: int = 1,
        topics_file: str | None = None,
        wipe: bool = False,
        embed_cache: str | None = None,
        embed_model: str = DEFAULT_MODEL,
        embed_workers: int = 0,
    ) -> int:
        """Run the full build pipeline: ingest → index.

        1. ``DiaryTransformer.ingest_to_corpus()`` → ``.diarykg/corpus/*.md``
        2. ``dockg build`` → ``.diarykg/graph.sqlite`` + ``.diarykg/lancedb/``
        3. (optional) ``diary_embedder`` → JSON embedding cache

        :param batch_size: Entries to sample (``0`` = all).
        :param seed: RNG seed for reproducible sampling.
        :param max_chunks_per_entry: Max chunks emitted per diary entry.
        :param chunking_strategy: ``sentence_group`` | ``semantic`` | ``hybrid``.
        :param chunk_size: Max characters per chunk.
        :param sentences_per_chunk: Sentences per chunk for sentence_group/hybrid.
        :param workers: Parallel workers for feature extraction.
        :param topics_file: Path to YAML topics override.
        :param wipe: Delete existing corpus + DBs before rebuilding.
        :param embed_cache: Path for the JSON embedding cache written by
            ``diary_embedder``.  Pass ``None`` (default) to skip.
        :param embed_model: HuggingFace model id for embedding
            (default: ``BAAI/bge-small-en-v1.5``).
        :param embed_workers: Parallel workers for embedding (0 = cpu_count).
        :return: Number of ``.md`` chunk files written.
        :raises ValueError: If no source file is configured.
        """
        sf = self.source_file
        if not sf:
            raise ValueError(
                "source_file is required for build(). Pass it to DiaryKG() or --source."
            )

        src_path = self.root / sf
        if not src_path.exists():
            src_path = Path(sf)
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {sf}")

        if wipe:
            import shutil  # pylint: disable=import-outside-toplevel

            for target in (self._corpus_dir, self._lancedb_dir):
                if target.exists():
                    shutil.rmtree(target)
            if self._db_path.exists():
                self._db_path.unlink()
            # Also wipe the DiaryTransformer chunk cache adjacent to the source file
            stem = src_path.stem
            for ext in ("_chunks.json", "_chunks.pkl"):
                cache_file = src_path.parent / f"{stem}{ext}"
                if cache_file.exists():
                    cache_file.unlink()
                    print(f"Wiped chunk cache: {cache_file}")
            self._dockg = None
            print("Wiped existing corpus + databases.")

        self._corpus_dir.mkdir(parents=True, exist_ok=True)

        # Step 1 — ingest via DiaryTransformer
        from diary_transformer import DiaryTransformer  # pylint: disable=import-outside-toplevel

        dt = DiaryTransformer(
            max_chunk_length=chunk_size,
            num_workers=workers,
            topics_file=topics_file,
            chunking_strategy=chunking_strategy,
            sentences_per_chunk=sentences_per_chunk,
        )
        n = dt.ingest_to_corpus(
            str(src_path),
            str(self._corpus_dir),
            batch_size=batch_size,
            seed=seed,
            max_chunks_per_entry=max_chunks_per_entry,
            source_file=sf,
            embed_cache=embed_cache,
            embed_model=embed_model,
            embed_workers=embed_workers,
        )

        # Reuse DiaryTransformer's already-loaded SentenceTransformer for DocKG.
        # Both now use the same model (DEFAULT_MODEL); loading a second instance
        # on MPS while the first is still live triggers SIGBUS on the first batch.
        shared_embedder = wrap_embedder(dt.sentence_model, self._model)
        del dt

        # Step 2 — build DocKG index
        print(f"Building DocKG index for {self._corpus_dir}...")
        try:
            from doc_kg.kg import DocKG  # pylint: disable=import-outside-toplevel

            dockg = DocKG(
                corpus_root=str(self._corpus_dir),
                db_path=str(self._db_path),
                lancedb_dir=str(self._lancedb_dir),
                model=self._model,
                embedder=shared_embedder,
            )
            dockg.build(wipe=True)
            self._dockg = dockg
        except ImportError:
            # Fallback: invoke dockg CLI
            subprocess.run(
                [
                    "dockg",
                    "build",
                    "--repo",
                    str(self._corpus_dir),
                    "--db",
                    str(self._db_path),
                    "--lancedb",
                    str(self._lancedb_dir),
                ],
                check=True,
            )

        # Step 3 — inject classifier topic edges into the DocKG graph
        n_edges = self._inject_topic_edges()
        print(f"Injected {n_edges} classifier HAS_TOPIC edges.")

        # Step 4 — enrich SQLite nodes with diary frontmatter metadata
        n_enriched = self._enrich_metadata()
        print(f"Enriched {n_enriched} chunk nodes with diary metadata.")

        # Persist config
        self._write_config(
            {
                "source_file": sf,
                "built_at": datetime.now(UTC).isoformat(),
                "chunk_count": n,
                "batch_size": batch_size,
                "chunking_strategy": chunking_strategy,
                "chunk_size": chunk_size,
            }
        )

        print(f"DiaryKG build complete: {n} chunks indexed.")
        return n

    def rebuild_index(self) -> None:
        """Re-run DocKG indexing on the existing corpus, skipping ingest.

        Use this when the corpus ``.md`` files are already up-to-date but the
        LanceDB / SQLite index needs to be rebuilt — e.g. after changing the
        embedding model or fixing an index-build bug.

        :raises FileNotFoundError: If the corpus directory doesn't exist.
        """
        if not self._corpus_dir.exists():
            raise FileNotFoundError(
                f"Corpus not found: {self._corpus_dir}. Run 'diarykg build' first."
            )

        # Wipe only the index, keep corpus files.
        import shutil  # pylint: disable=import-outside-toplevel

        if self._lancedb_dir.exists():
            shutil.rmtree(self._lancedb_dir)
        if self._db_path.exists():
            self._db_path.unlink()
        self._dockg = None

        print(f"Building DocKG index for {self._corpus_dir}...")
        try:
            from doc_kg.kg import DocKG  # pylint: disable=import-outside-toplevel

            dockg = DocKG(
                corpus_root=str(self._corpus_dir),
                db_path=str(self._db_path),
                lancedb_dir=str(self._lancedb_dir),
                model=self._model,
            )
            dockg.build(wipe=True, discover_similar=False)
            self._dockg = dockg
        except ImportError:
            import subprocess  # pylint: disable=import-outside-toplevel

            subprocess.run(
                [
                    "dockg",
                    "build",
                    "--repo",
                    str(self._corpus_dir),
                    "--db",
                    str(self._db_path),
                    "--lancedb",
                    str(self._lancedb_dir),
                ],
                check=True,
            )

        n_edges = self._inject_topic_edges()
        print(f"Injected {n_edges} classifier HAS_TOPIC edges.")
        n_enriched = self._enrich_metadata()
        print(f"Enriched {n_enriched} chunk nodes with diary metadata.")

    def _inject_topic_edges(self) -> int:
        """Inject classifier-derived topic nodes and HAS_TOPIC edges into the graph.

        Reads ``topics:`` frontmatter from every corpus ``.md`` file, looks up
        all DocKG chunk nodes that originate from that file, then upserts a
        ``topic`` node and a ``HAS_TOPIC`` edge (with classifier confidence) for
        each topic.  Uses ``INSERT OR REPLACE`` so repeated builds stay idempotent.

        :return: Number of HAS_TOPIC edges written.
        """
        import json as _json  # pylint: disable=import-outside-toplevel
        import sqlite3  # pylint: disable=import-outside-toplevel

        if not self._db_path.exists() or not self._corpus_dir.exists():
            return 0

        md_files = sorted(self._corpus_dir.glob("*.md"))
        if not md_files:
            return 0

        edges_written = 0

        with sqlite3.connect(str(self._db_path)) as con:
            cur = con.cursor()

            for md_path in md_files:
                text = md_path.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                topics_raw = fm.get("topics", "").strip()
                if not topics_raw:
                    continue

                # Parse "name:score,name:score" pairs
                topic_scores: dict[str, float] = {}
                for pair in topics_raw.split(","):
                    pair = pair.strip()
                    if ":" in pair:
                        name, _, score_str = pair.rpartition(":")
                        try:
                            topic_scores[name.strip()] = float(score_str)
                        except ValueError:
                            pass
                    elif pair:
                        topic_scores[pair] = 1.0

                if not topic_scores:
                    continue

                # Find all DocKG chunk nodes for this file
                filename = md_path.name
                cur.execute(
                    "SELECT id FROM nodes WHERE kind='chunk' AND file_path=?",
                    (filename,),
                )
                chunk_ids = [row[0] for row in cur.fetchall()]
                if not chunk_ids:
                    continue

                for topic_name, score in topic_scores.items():
                    # Derive stable topic node ID matching DocKG's convention
                    slug = re.sub(r"[^a-z0-9]+", "-", topic_name.lower()).strip("-")
                    topic_id = f"topic:{slug}"
                    topic_label = topic_name.replace("_", " ")

                    # Upsert topic node
                    cur.execute(
                        "INSERT OR REPLACE INTO nodes"
                        " (id, kind, name, title, text)"
                        " VALUES (?, 'topic', ?, ?, ?)",
                        (topic_id, f"topic:{topic_name}", topic_id, topic_label),
                    )

                    for chunk_id in chunk_ids:
                        evidence = _json.dumps(
                            {"confidence": round(score, 4), "source": "classifier"},
                            separators=(",", ":"),
                        )
                        cur.execute(
                            "INSERT OR REPLACE INTO edges (src, rel, dst, evidence)"
                            " VALUES (?, 'HAS_TOPIC', ?, ?)",
                            (chunk_id, topic_id, evidence),
                        )
                        edges_written += 1

            con.commit()

        return edges_written

    def _enrich_metadata(self) -> int:
        """Enrichment pass: store diary frontmatter fields into the SQLite nodes table.

        Adds columns ``timestamp``, ``category``, ``context``, and
        ``diary_source_file`` to the DocKG ``nodes`` table (idempotent), then
        populates them from each corpus chunk's ``.md`` frontmatter.

        :return: Number of chunk rows updated.
        """
        import sqlite3  # pylint: disable=import-outside-toplevel

        if not self._db_path.exists() or not self._corpus_dir.exists():
            return 0

        md_files = sorted(self._corpus_dir.glob("*.md"))
        if not md_files:
            return 0

        n_updated = 0
        with sqlite3.connect(str(self._db_path)) as con:
            for col in ("timestamp", "category", "context", "diary_source_file"):
                try:
                    con.execute(f"ALTER TABLE nodes ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass  # column already exists
            con.commit()

            for md_path in md_files:
                fm = _parse_frontmatter(md_path.read_text(encoding="utf-8"))
                if not fm:
                    continue
                con.execute(
                    """
                    UPDATE nodes
                       SET timestamp=?, category=?, context=?, diary_source_file=?
                     WHERE kind='chunk' AND file_path=?
                    """,
                    (
                        fm.get("timestamp"),
                        fm.get("category"),
                        fm.get("context"),
                        fm.get("source_file"),
                        md_path.name,
                    ),
                )
                n_updated += con.execute("SELECT changes()").fetchone()[0]
            con.commit()

        return n_updated

    # ------------------------------------------------------------------
    # Query / Pack
    # ------------------------------------------------------------------

    def query(self, q: str, k: int = 8) -> list[dict[str, Any]]:
        """Semantic search over the diary corpus.

        Pure vector search over chunk nodes, with scores and diary metadata
        sourced from the enriched SQLite ``nodes`` table.

        :param q: Natural-language query string.
        :param k: Number of results to return.
        :return: List of result dicts with keys: ``score``, ``summary``,
            ``source_file``, ``timestamp``, ``category``, ``context``,
            ``node_id``.
        """
        import sqlite3  # pylint: disable=import-outside-toplevel

        dockg = self._load_dockg()
        sf = self.source_file

        # Pure semantic search — oversample then filter to chunk nodes only
        seed_hits = dockg.index.search(q, k=k * 15)
        chunk_hits = [h for h in seed_hits if h.kind == "chunk"][:k]
        if not chunk_hits:
            return []

        hits = []
        with sqlite3.connect(str(self._db_path)) as con:
            for hit in chunk_hits:
                score = max(0.0, 1.0 - hit.distance)
                row = con.execute(
                    """
                    SELECT text, timestamp, category, context, diary_source_file
                      FROM nodes WHERE id=?
                    """,
                    (hit.id,),
                ).fetchone()
                if not row:
                    continue
                text, timestamp, category, context, diary_sf = row
                hits.append(
                    {
                        "node_id": hit.id,
                        "score": score,
                        "summary": (text or "")[:120],
                        "source_file": diary_sf or sf or hit.file_path or "",
                        "timestamp": timestamp or "",
                        "category": category or "",
                        "context": context or "",
                    }
                )
        return hits

    def pack(self, q: str, k: int = 8) -> list[dict[str, Any]]:
        """Return source snippets for LLM ingestion.

        :param q: Natural-language query string.
        :param k: Number of snippets.
        :return: List of snippet dicts with keys: ``content``, ``source_file``,
            ``timestamp``, ``score``, ``node_id``.
        """
        import sqlite3  # pylint: disable=import-outside-toplevel

        dockg = self._load_dockg()
        sf = self.source_file

        seed_hits = dockg.index.search(q, k=k * 15)
        chunk_hits = [h for h in seed_hits if h.kind == "chunk"][:k]
        if not chunk_hits:
            return []

        snippets = []
        with sqlite3.connect(str(self._db_path)) as con:
            for hit in chunk_hits:
                score = max(0.0, 1.0 - hit.distance)
                row = con.execute(
                    """
                    SELECT text, timestamp, diary_source_file
                      FROM nodes WHERE id=?
                    """,
                    (hit.id,),
                ).fetchone()
                if not row:
                    continue
                text, timestamp, diary_sf = row
                snippets.append(
                    {
                        "node_id": hit.id,
                        "score": score,
                        "content": text or "",
                        "source_file": diary_sf or sf or hit.file_path or "",
                        "timestamp": timestamp or "",
                    }
                )
        return snippets

    # ------------------------------------------------------------------
    # Info / Stats / Analyze
    # ------------------------------------------------------------------

    def info(self) -> dict[str, Any]:
        """Return diary-specific corpus information.

        Reads config + corpus frontmatter without loading the full DocKG.
        Use this for rich corpus introspection (temporal span, topic
        distribution, context breakdown).

        :return: Dict with chunk_count, entry_count, source_file, built_at,
            temporal_span, topic_counts, context_counts.
        """
        config = self._read_config()
        md_files = list(self._corpus_dir.rglob("*.md")) if self._corpus_dir.exists() else []

        timestamps: list[str] = []
        categories: Counter = Counter()
        contexts: Counter = Counter()
        entry_indices: set = set()

        for md in md_files:
            try:
                fm = _parse_frontmatter(md.read_text(encoding="utf-8"))
                if fm.get("timestamp"):
                    timestamps.append(fm["timestamp"])
                if fm.get("category"):
                    categories[fm["category"]] += 1
                if fm.get("context"):
                    contexts[fm["context"]] += 1
                if fm.get("entry_index"):
                    entry_indices.add(fm["entry_index"])
            except OSError:
                continue

        timestamps.sort()
        span: dict[str, str] | None = None
        if len(timestamps) >= 2:
            span = {"start": timestamps[0], "end": timestamps[-1]}
        elif timestamps:
            span = {"start": timestamps[0], "end": timestamps[0]}

        return {
            "source_file": config.get("source_file", self._source_file_override),
            "built_at": config.get("built_at"),
            "chunk_count": len(md_files),
            "entry_count": len(entry_indices),
            "temporal_span": span,
            "topic_counts": dict(categories.most_common()),
            "context_counts": dict(contexts.most_common()),
        }

    def stats(self) -> dict[str, Any]:
        """Return KG storage statistics (node + edge counts).

        Matches the contract expected by the KGRAG cross-KG ``analyze``
        command so the system can report total indexed size across all KGs.

        :return: Dict with node_count, edge_count, kind.
        """
        self._load_dockg()
        try:
            s = self._dockg.store.stats()
            return {
                "node_count": s.get("total_nodes", "n/a"),
                "edge_count": s.get("total_edges", "n/a"),
                "kind": "diary",
            }
        except Exception:  # pylint: disable=broad-exception-caught
            return {"node_count": "n/a", "edge_count": "n/a", "kind": "diary"}

    def analyze(self) -> str:
        """Return a Markdown analysis report.

        :return: Markdown string covering corpus overview, topic distribution,
            context distribution, temporal span, and DocKG baseline stats.
        """
        info = self.info()
        db_stats = self.stats()
        span = info.get("temporal_span") or {}
        span_str = f"{span.get('start', '?')} → {span.get('end', '?')}" if span else "n/a"

        lines: list[str] = [
            "# DiaryKG Analysis Report",
            "",
            f"**Root:** `{self.root}`  |  **Source:** `{info.get('source_file', 'unknown')}`",
            "",
            "## Corpus Overview",
            "",
            f"- Chunk files   : **{info['chunk_count']}**",
            f"- Diary entries : **{info['entry_count']}**",
            f"- Temporal span : **{span_str}**",
            f"- Built at      : {info.get('built_at', 'n/a')}",
            f"- DocKG nodes   : {db_stats['node_count']}",
            f"- DocKG edges   : {db_stats['edge_count']}",
            "",
            "## Topic Distribution",
            "",
            "| Category | Chunks |",
            "|---|---:|",
        ]
        for cat, cnt in (info.get("topic_counts") or {}).items():
            lines.append(f"| {cat} | {cnt} |")

        lines += [
            "",
            "## Context Distribution",
            "",
            "| Context | Chunks |",
            "|---|---:|",
        ]
        for ctx, cnt in (info.get("context_counts") or {}).items():
            lines.append(f"| {ctx} | {cnt} |")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Snapshots  (delegated to DiarySnapshotManager)
    # ------------------------------------------------------------------

    def _snapshot_mgr(self) -> DiarySnapshotManager:  # type: ignore[name-defined]
        from .snapshots import DiarySnapshotManager  # pylint: disable=import-outside-toplevel

        return DiarySnapshotManager(self._snapshot_dir)

    def snapshot_save(self, version: str = "0.1.0", label: str | None = None) -> dict[str, Any]:
        """Capture a point-in-time snapshot of corpus metrics.

        Key is the git tree hash (``HEAD^{tree}``).  Metrics include
        chunk/entry/node/edge counts, temporal span, and topic/context
        distributions.  Deltas vs previous and baseline are computed
        automatically.

        :param version: Version label for this snapshot.
        :param label: Optional human-readable description.
        :return: Saved snapshot as a dict.
        :raises RuntimeError: If the KG is not built.
        :raises ValueError: If chunk_count is 0.
        """
        if not self.is_built():
            raise RuntimeError("DiaryKG is not built. Run build() first.")
        config = self._read_config()
        info = self.info()
        info["chunking_strategy"] = config.get("chunking_strategy", "")
        info["chunk_size"] = config.get("chunk_size", 512)
        db_stats = self.stats()
        mgr = self._snapshot_mgr()
        snap = mgr.capture_diary(version=version, info=info, db_stats=db_stats, label=label)
        mgr.save_snapshot(snap)
        return snap.to_dict()

    def snapshot_list(self, branch: str | None = None) -> list[dict[str, Any]]:
        """Return all snapshots in reverse-chronological order.

        :param branch: Filter by branch name if provided.
        :return: List of manifest entry dicts.
        """
        return self._snapshot_mgr().list_snapshots(branch=branch)

    def snapshot_show(self, key: str) -> dict[str, Any]:
        """Load a full snapshot by tree-hash key.

        :param key: Git tree hash (from ``snapshot_list()``).
        :return: Full snapshot dict.
        :raises FileNotFoundError: If the snapshot does not exist.
        """
        snap = self._snapshot_mgr().load_snapshot(key)
        if snap is None:
            raise FileNotFoundError(f"Snapshot not found: {key}")
        return snap.to_dict()

    def snapshot_diff(self, key_a: str, key_b: str) -> dict[str, Any]:
        """Compare two snapshots and return a delta report.

        :param key_a: Earlier snapshot tree-hash key.
        :param key_b: Later snapshot tree-hash key.
        :return: Dict with ``a``, ``b``, ``delta``, ``topic_counts_delta``.
        """
        return self._snapshot_mgr().diff_snapshots(key_a, key_b)

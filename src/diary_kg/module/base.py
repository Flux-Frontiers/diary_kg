"""
diary_kg/module/base.py

DiaryKGAdapter — KGRAG adapter for diary_kg.kg.DiaryKG.

Follows the same structural pattern as code_kg.module.base.KGModule:

  - lazy-initialised backing instance (``_load()`` / ``_kg``)
  - five-method adapter interface (is_available, query, pack, stats, analyze)
  - must-not-raise contract on all I/O methods
  - cheap ``is_available()`` (import check + built flag only)

The adapter reads ``KGEntry.metadata["source_file"]`` to locate the
pipe-delimited diary source used when building the corpus.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from diary_kg.primitives import CrossHit, CrossSnippet, KGEntry, KGKind

if TYPE_CHECKING:
    from diary_kg.kg import DiaryKG as _DiaryKG


class DiaryKGAdapter:
    """KGRAG adapter wrapping a :class:`~diary_kg.kg.DiaryKG` instance.

    Implements the five-method adapter contract required by the KGRAG
    orchestrator:

    - :meth:`is_available` — cheap availability check
    - :meth:`query`        — semantic search → :class:`~diary_kg.primitives.CrossHit` list
    - :meth:`pack`         — semantic search → :class:`~diary_kg.primitives.CrossSnippet` list
    - :meth:`stats`        — graph statistics dict
    - :meth:`analyze`      — full Markdown analysis report

    Also exposes :meth:`info` (diary-specific corpus metadata).

    Typical use::

        entry = KGEntry(
            name="pepys",
            kind=KGKind.DIARY,
            repo_path=Path("/corpus/pepys"),
            metadata={"source_file": "pepys.txt"},
            is_built=True,
        )
        adapter = DiaryKGAdapter(entry)
        if adapter.is_available():
            hits = adapter.query("daily routine at the office", k=8)

    :param entry: Registry entry describing this diary KG instance.
    """

    def __init__(self, entry: KGEntry) -> None:
        """Store the registry entry.  Does not load DiaryKG or open any DB.

        Initialization is deliberately cheap and side-effect-free.  All I/O
        is deferred to :meth:`_load`, called lazily at the top of every I/O
        method.

        :param entry: :class:`~diary_kg.primitives.KGEntry` for this instance.
        """
        self.entry = entry
        self._kg: _DiaryKG | None = None  # populated lazily by _load()

    # ------------------------------------------------------------------
    # Lazy initialisation — mirrors KGModule._store / ._index pattern
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Lazily instantiate :class:`~diary_kg.kg.DiaryKG`.

        Returns immediately if already loaded (``self._kg is not None``).
        Called at the top of every I/O method.

        :raises ImportError: If ``diary-kg`` is not installed.
        """
        if self._kg is not None:
            return

        try:
            from diary_kg.kg import DiaryKG  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "diary-kg is not installed. "
                "Run: pip install 'diary-kg @ git+https://github.com/Flux-Frontiers/diary_kg.git'"
            ) from exc

        source_file: str | None = self.entry.metadata.get("source_file")
        self._kg = DiaryKG(
            root=self.entry.repo_path,
            source_file=source_file,
        )

    # ------------------------------------------------------------------
    # Adapter interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return ``True`` if diary-kg is importable and the KG is built.

        Cheap: import check + ``entry.is_built`` flag only.
        Does not load or open the DiaryKG database.

        :return: ``True`` if this adapter can serve queries.
        """
        try:
            import diary_kg  # noqa: F401, PLC0415
            return bool(self.entry.is_built)
        except ImportError:
            return False

    def query(self, q: str, k: int = 8) -> list[CrossHit]:
        """Semantic query over the diary corpus.

        Delegates to :meth:`~diary_kg.kg.DiaryKG.query` and converts each
        result dict to a :class:`~diary_kg.primitives.CrossHit`.

        DiaryKG result dicts contain:
        ``node_id``, ``score``, ``summary``, ``source_file``,
        ``timestamp``, ``category``, ``context``.

        :param q: Natural-language query string.
        :param k: Maximum number of results to return.
        :return: Up to ``k`` :class:`~diary_kg.primitives.CrossHit` objects
                 ranked by descending score.  Returns ``[]`` on any error.
        """
        self._load()
        try:
            raw: list[dict[str, Any]] = self._kg.query(q, k=k)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            return []
        return [self._to_hit(r) for r in raw]

    def pack(self, q: str, k: int = 8, context: int = 5) -> list[CrossSnippet]:  # noqa: ARG002
        """Retrieve diary snippets for inclusion in an LLM context window.

        Delegates to :meth:`~diary_kg.kg.DiaryKG.pack` and converts each
        result dict to a :class:`~diary_kg.primitives.CrossSnippet`.

        ``context`` is accepted for interface compatibility but is ignored
        for diary KGs — entries are timestamped prose with no line numbers.

        :param q: Natural-language query string.
        :param k: Maximum number of snippets to return.
        :param context: Ignored (no line-number concept in diary KGs).
        :return: Up to ``k`` :class:`~diary_kg.primitives.CrossSnippet` objects
                 ranked by descending score.  Returns ``[]`` on any error.
        """
        self._load()
        try:
            raw: list[dict[str, Any]] = self._kg.pack(q, k=k)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            return []
        return [self._to_snippet(r) for r in raw]

    def stats(self) -> dict[str, Any]:
        """Return graph statistics for this diary KG.

        Delegates to :meth:`~diary_kg.kg.DiaryKG.stats`.

        :return: Dict containing at minimum ``"kind"``, ``"node_count"``,
                 and ``"edge_count"``.  Returns ``{"kind": "diary", "error": ...}``
                 on failure.
        """
        self._load()
        try:
            return self._kg.stats()  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            return {"kind": "diary", "error": str(exc)}

    def analyze(self) -> str:
        """Run a full analysis and return a Markdown report.

        Delegates to :meth:`~diary_kg.kg.DiaryKG.analyze`.

        :return: Markdown report beginning with ``# DiaryKG Analysis Report``.
                 Returns a Markdown error string on failure.
        """
        self._load()
        try:
            return self._kg.analyze()  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            return f"# DiaryKG Analysis\n\nAnalysis failed: {exc}\n"

    # ------------------------------------------------------------------
    # DiaryKG-specific extras
    # ------------------------------------------------------------------

    def info(self) -> dict[str, Any]:
        """Return corpus metadata: chunk count, entry count, source file.

        Delegates to :meth:`~diary_kg.kg.DiaryKG.info`.

        :return: Corpus metadata dict.  Returns ``{"error": ...}`` on failure.
        """
        self._load()
        try:
            return self._kg.info()  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Conversion helpers — mirror KGModule._nodespec_to_node pattern
    # ------------------------------------------------------------------

    def _to_hit(self, raw: dict[str, Any]) -> CrossHit:
        """Convert a DiaryKG query result dict to a :class:`~diary_kg.primitives.CrossHit`.

        :param raw: Result dict from :meth:`~diary_kg.kg.DiaryKG.query`.
        :return: :class:`~diary_kg.primitives.CrossHit` instance.
        """
        return CrossHit(
            kg_name=self.entry.name,
            kg_kind=KGKind.DIARY,
            node_id=raw.get("node_id", ""),
            name=raw.get("timestamp", ""),
            kind=raw.get("category", "chunk"),
            score=float(raw.get("score", 0.0)),
            summary=raw.get("summary", ""),
            source_path=raw.get("source_file", ""),
        )

    def _to_snippet(self, raw: dict[str, Any]) -> CrossSnippet:
        """Convert a DiaryKG pack result dict to a :class:`~diary_kg.primitives.CrossSnippet`.

        ``lineno`` and ``end_lineno`` are always ``None`` — diary entries
        are timestamped prose blocks, not source files with line numbers.

        :param raw: Result dict from :meth:`~diary_kg.kg.DiaryKG.pack`.
        :return: :class:`~diary_kg.primitives.CrossSnippet` instance.
        """
        return CrossSnippet(
            kg_name=self.entry.name,
            kg_kind=KGKind.DIARY,
            node_id=raw.get("node_id", ""),
            source_path=raw.get("source_file", ""),
            content=raw.get("content", ""),
            score=float(raw.get("score", 0.0)),
            lineno=None,
            end_lineno=None,
        )

"""
diary_kg/primitives.py

Shared data types for the DiaryKG adapter interface.

CrossHit and CrossSnippet are the result types consumed by the KGRAG
orchestrator.  KGEntry describes a registered DiaryKG instance.
KGKind discriminates the type of knowledge graph backend.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class KGKind(StrEnum):
    """Supported knowledge graph kinds."""

    CODE = "code"
    DOC = "doc"
    META = "meta"
    DIARY = "diary"


@dataclass
class KGEntry:
    """Registry record describing a single DiaryKG instance.

    :param name: Human-readable label (e.g. ``"pepys"``).
    :param kind: KG kind enum value.
    :param repo_path: Corpus root directory.
    :param metadata: Adapter-specific key/value pairs.
                     ``DiaryKGAdapter`` reads ``metadata["source_file"]``
                     for the pipe-delimited diary source file.
    :param is_built: ``True`` when the underlying DB files exist and are
                     non-empty.
    :param sqlite_path: Optional explicit SQLite database path.
    :param lancedb_path: Optional explicit LanceDB directory path.
    """

    name: str
    kind: KGKind
    repo_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    is_built: bool = False
    sqlite_path: Path | None = None
    lancedb_path: Path | None = None


@dataclass
class CrossHit:
    """One ranked result from a DiaryKG semantic query.

    :param kg_name: Source KG name (from ``KGEntry.name``).
    :param kg_kind: Source KG kind.
    :param node_id: Stable unique identifier within the source KG.
    :param name: Human-readable label — the diary entry timestamp.
    :param kind: Node type (``"chunk"`` for diary entries).
    :param score: Relevance score in ``[0.0, 1.0]``.
    :param summary: Short prose excerpt (may be empty).
    :param source_path: Diary source file path (may be empty).
    """

    kg_name: str
    kg_kind: KGKind
    node_id: str
    name: str
    kind: str
    score: float
    summary: str
    source_path: str


@dataclass
class CrossSnippet:
    """Source-grounded diary snippet for inclusion in an LLM context window.

    :param kg_name: Source KG name.
    :param kg_kind: Source KG kind.
    :param node_id: Stable unique identifier within the source KG.
    :param source_path: Diary source file path.
    :param content: Diary text to include in context.
    :param score: Relevance score in ``[0.0, 1.0]``.
    :param lineno: Always ``None`` — diary entries have no line numbers.
    :param end_lineno: Always ``None``.
    """

    kg_name: str
    kg_kind: KGKind
    node_id: str
    source_path: str
    content: str
    score: float
    lineno: int | None = None
    end_lineno: int | None = None

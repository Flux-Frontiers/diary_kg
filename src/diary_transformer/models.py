"""models.py — Core dataclasses for the diary transformer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DiaryEntry:
    """A single parsed diary entry.

    :param timestamp: When the entry was written.
    :param original_type: Source type tag (e.g. ``raw``).
    :param category: Source category tag (e.g. ``DiaryEntry``).
    :param content: Full text of the entry.
    :param source_file: Relative path to the original source file (provenance anchor).
    :param index: Position in the source file (assigned during parsing).
    :param chunks: Pre-segmented chunks (populated by the chunk cache).
    """

    timestamp: datetime
    original_type: str
    category: str
    content: str
    source_file: str = ""
    index: int | None = None
    chunks: list[str] | None = field(default=None, repr=False)


@dataclass
class EntryChunk:
    """A single transformed memory chunk derived from a DiaryEntry.

    :param timestamp: Inherited from the source entry.
    :param semantic_category: Classified topic category.
    :param context_classification: Contextual label (Work, Home, Social, …).
    :param content: Chunk text.
    :param confidence: Classification confidence score.
    :param phase: Processing phase label.
    :param source_entry_index: Index of the originating DiaryEntry.
    :param source_entry: Reference to the originating DiaryEntry.
    :param topics: Topic name → confidence score from the hybrid classifier.
    """

    timestamp: datetime
    semantic_category: str
    context_classification: str
    content: str
    confidence: float = 1.0
    phase: str = "immediate"
    source_entry_index: int = -1
    source_entry: DiaryEntry | None = field(default=None, repr=False)
    topics: dict[str, float] = field(default_factory=dict)

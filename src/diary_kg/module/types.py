"""
diary_kg/module/types.py

Result types and scoring utilities for DiaryKG queries.

Mirrors code_kg.module.types but adapted for diary/journal corpora:
  - no line numbers (entries are timestamped prose, not source files)
  - scores derived from DocKG vector distance
  - snippet content is raw diary text, not source code

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class DiaryQueryResult:
    """Results from a DiaryKG semantic query.

    :param query: Original query string.
    :param returned_hits: Number of hits returned.
    :param hits: Ranked list of raw hit dicts from the underlying DocKG.
    """

    query: str
    returned_hits: int
    hits: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DiarySnippetPack:
    """LLM-ready snippet pack from a DiaryKG query.

    :param query: Original query string.
    :param returned_snippets: Number of snippets returned.
    :param snippets: Ranked list of snippet dicts (content + provenance).
    """

    query: str
    returned_snippets: int
    snippets: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scoring utilities
# ---------------------------------------------------------------------------


def semantic_score_from_distance(distance: float) -> float:
    """Convert an L2/cosine embedding distance to a [0, 1] relevance score.

    Uses the same formula as code_kg: ``score = 1 / (1 + distance)``.

    :param distance: Non-negative embedding distance from vector search.
    :return: Relevance score in ``[0.0, 1.0]``; higher is more relevant.
    """
    return 1.0 / (1.0 + max(0.0, distance))


def normalize_score(score: float) -> float:
    """Clamp a score to ``[0.0, 1.0]``.

    :param score: Raw score value.
    :return: Score clamped to ``[0.0, 1.0]``.
    """
    return max(0.0, min(1.0, float(score)))

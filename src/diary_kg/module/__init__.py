"""
diary_kg.module — KGRAG adapter SDK for DiaryKG.

Mirrors the code_kg.module package structure.

    from diary_kg.module import DiaryKGAdapter
    from diary_kg.primitives import CrossHit, CrossSnippet, KGEntry, KGKind
"""

from diary_kg.module.base import DiaryKGAdapter
from diary_kg.module.types import DiaryQueryResult, DiarySnippetPack

__all__ = [
    "DiaryKGAdapter",
    "DiaryQueryResult",
    "DiarySnippetPack",
]

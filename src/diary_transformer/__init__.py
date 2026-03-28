"""diary_transformer — Plug-and-play diary ingestion package for doc_kg / KGRAG.

Drop this package into any project that needs to ingest diary/journal text into
a structured knowledge graph.  The public surface is intentionally small:

    from diary_transformer import DiaryTransformer, DiaryEntry, EntryChunk
    from diary_transformer import parse_diary, temporally_sample, embed_multiprocess, save_cache

Modules
-------
models          — DiaryEntry, EntryChunk dataclasses
parser          — pipe-delimited diary file parser
chunker         — semantic / sentence-group / hybrid chunking strategies
features        — diversity feature extraction and caching (supports multiprocessing)
classifier      — TF-IDF unsupervised + supervised topic/context classification
state           — resumable processing state management (StateManager)
transformer     — DiaryTransformer orchestrator (main public class)
diary_embedder  — multi-process embedding pipeline (WaveRider PEPYS engine)
cli             — Click entry point (``diary-transformer``)
"""

from .diary_embedder import embed_multiprocess, parse_diary, save_cache, temporally_sample
from .models import DiaryEntry, EntryChunk
from .transformer import DiaryTransformer

__all__ = [
    "DiaryTransformer",
    "DiaryEntry",
    "EntryChunk",
    "parse_diary",
    "temporally_sample",
    "embed_multiprocess",
    "save_cache",
]

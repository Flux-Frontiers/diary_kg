#!/usr/bin/env python3
# diary_embedder.py
# Copyright (c) 2026 Eric G. Suchanek, PhD, Flux-Frontiers
# https://github.com/Flux-Frontiers
# License: Elastic 2.0
# Last revised: 2026-03-27 -egs-
"""
diary_embedder.py
-----------------
Multi-process ingestion pipeline: parse a pipe-delimited diary file,
optionally subsample with temporal diversity, embed every entry via
sentence-transformers (all-mpnet-base-v2), and save the result as a
JSON cache consumable by pepys_manifold_explorer.py and WaveRider missions.

The expensive embedding step is parallelised across CPU cores using
multiprocessing.Pool — each worker loads its own copy of the model and
encodes a shard independently.

Pipeline
--------
1. Parse TIMESTAMP | TYPE | CATEGORY | CONTENT lines.
2. Optionally subsample N entries with even temporal spacing.
3. Shard texts across --workers processes, each running a local
   SentenceTransformer instance.
4. Concatenate shards → float32 (N × 768) matrix.
5. Write JSON cache:  {"embeddings": [...], "texts": [...], "timestamps": [...]}.

Usage (CLI entry point)
-----------------------
  # full corpus (all entries)
  diary-embedder

  # temporally sampled subset
  diary-embedder --n 1000

  # custom paths / model
  diary-embedder \\
      --diary path/to/pepys_enriched_full.txt \\
      --output path/to/my_cache.json \\
      --model sentence-transformers/all-mpnet-base-v2 \\
      --workers 8 \\
      --batch-size 128

Public API (importable)
-----------------------
  from diary_transformer import parse_diary, temporally_sample, embed_multiprocess, save_cache

Requirements
------------
  sentence-transformers >= 5.0, numpy, rich
  No external services — model loaded directly from HuggingFace.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import numpy as np
from rich.console import Console
from sentence_transformers import SentenceTransformer

console = Console()

try:
    _EMBEDDER_VERSION = _pkg_version("diary-kg")
except PackageNotFoundError:
    _EMBEDDER_VERSION = "unknown"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
# Project root is three levels up from src/diary_transformer/diary_embedder.py
_PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DIARY = str(_PROJECT_ROOT / "pepys" / "pepys_enriched_full.txt")
DEFAULT_OUTPUT = str(_PROJECT_ROOT / "pepys_mpnet_embeddings.json")


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------
def write_run_summary(
    output_path: str,
    run_params: dict,
    stats: dict,
    summary_file: str | None = None,
) -> str:
    """Write a Markdown provenance summary alongside the embedding cache.

    The summary is written to ``<output_stem>_run_summary.md`` in the same
    directory as *output_path* unless *summary_file* is given.

    :param output_path: Path to the JSON embedding cache.
    :param run_params: Run parameters dict (timestamp, diary_file, model, etc.).
    :param stats: Metrics dict with keys ``entries_parsed``, ``entries_embedded``,
        ``time_range_start``, ``time_range_end``, ``embedding_shape``, ``runtime_s``.
    :param summary_file: Override output path for the summary.
    :return: Path to the written summary file.
    """
    out = Path(output_path)
    summary_path = Path(summary_file) if summary_file else out.parent / f"{out.stem}_run_summary.md"

    cmd = " ".join(sys.argv)
    ts = run_params.get("timestamp", datetime.now().isoformat())
    dt = datetime.fromisoformat(ts)

    lines = [
        "# Diary Embedder — Run Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Date | {dt.strftime('%Y-%m-%d')} |",
        f"| Time | {dt.strftime('%H:%M:%S')} |",
        f"| Version | {_EMBEDDER_VERSION} |",
        "",
        "## Invocation",
        "",
        "```",
        cmd,
        "```",
        "",
        "## Inputs & Outputs",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Diary file | `{run_params.get('diary_file', '—')}` |",
        f"| Output cache | `{output_path}` |",
        "",
        "## Run Parameters",
        "",
        "| Parameter | Value |",
        "|---|---|",
    ]
    skip = {"timestamp", "diary_file"}
    for key, val in run_params.items():
        if key in skip:
            continue
        label = key.replace("_", " ").title()
        lines.append(f"| {label} | `{val}` |")

    shape = stats.get("embedding_shape", "—")
    lines += [
        "",
        "## Pipeline Statistics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Entries parsed | {stats.get('entries_parsed', '—')} |",
        f"| Entries embedded | {stats.get('entries_embedded', '—')} |",
        f"| Time range | {stats.get('time_range_start', '—')} → {stats.get('time_range_end', '—')} |",
        f"| Embedding shape | {shape[0]} × {shape[1]} float32 |"
        if isinstance(shape, tuple)
        else f"| Embedding shape | {shape} |",
        f"| Runtime | {stats.get('runtime_s', 0):.1f}s |",
        "",
    ]

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[bold green]✓[/bold green] Run summary → {summary_path}")
    return str(summary_path)


# ---------------------------------------------------------------------------
# Diary parser
# ---------------------------------------------------------------------------
def parse_diary(path: str) -> tuple[list[str], list[datetime]]:
    """Parse a pipe-delimited diary file and return (texts, timestamps).

    Expected line format::

        TIMESTAMP | TYPE | CATEGORY | CONTENT

    TYPE and CATEGORY are prepended to CONTENT so topic-level signal is
    preserved in the embedding space.

    :param path: Path to the diary file.
    :return: Tuple of (embed strings, datetime objects), sorted chronologically.
    """
    texts: list[str] = []
    timestamps: list[datetime] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue
            ts_str, entry_type, category, content = [p.strip() for p in parts]
            content = content.strip()
            if not content or content == ".":
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            topic_label = entry_type.replace("_", " ").strip()
            texts.append(f"{topic_label} | {category} | {content}")
            timestamps.append(ts)
    return texts, timestamps


# ---------------------------------------------------------------------------
# Temporal sampler
# ---------------------------------------------------------------------------
def temporally_sample(
    texts: list[str], timestamps: list[datetime], n: int
) -> tuple[list[str], list[datetime]]:
    """Return n entries sampled evenly across the full time span.

    :param texts: Full list of entry strings (chronologically sorted).
    :param timestamps: Corresponding datetime objects.
    :param n: Desired sample size.  If >= len(texts) the full corpus is returned.
    :return: Tuple of (sampled texts, sampled timestamps).
    """
    total = len(texts)
    if n <= 0 or n >= total:
        return texts, timestamps
    indices = [round(i * (total - 1) / (n - 1)) for i in range(n)]
    return [texts[i] for i in indices], [timestamps[i] for i in indices]


# ---------------------------------------------------------------------------
# Per-worker embedding function (runs in a subprocess)
# ---------------------------------------------------------------------------
def _embed_shard(args: tuple) -> np.ndarray:
    """Embed one shard of texts in a subprocess.

    Each worker loads its own SentenceTransformer instance so there is no
    shared state and no GIL contention.

    :param args: (texts_shard, model_id, batch_size, worker_id)
    :return: Float32 array of shape (len(shard), D).
    """
    texts_shard, model_id, batch_size, worker_id = args
    embedder = SentenceTransformer(model_id, trust_remote_code=True)
    vecs = embedder.encode(
        texts_shard,
        batch_size=batch_size,
        convert_to_numpy=True,
        show_progress_bar=(worker_id == 0),  # only first worker shows bar
    )
    return vecs.astype(np.float32)


# ---------------------------------------------------------------------------
# Multi-process embedding orchestrator
# ---------------------------------------------------------------------------
def embed_multiprocess(
    texts: list[str],
    model: str = DEFAULT_MODEL,
    n_workers: int | None = None,
    batch_size: int = 32,
) -> np.ndarray:
    """Embed texts in parallel using multiprocessing.Pool.

    Splits texts into n_workers equal shards, spawns one subprocess per
    shard via multiprocessing.Pool, each loading the model independently.
    Results are concatenated in original order.

    :param texts: List of strings to embed.
    :param model: HuggingFace model id.
    :param n_workers: Number of parallel workers (default: os.cpu_count()).
    :param batch_size: Encoding batch size per worker.
    :return: Float32 array of shape (N, D).
    """
    n_workers = n_workers or os.cpu_count() or 1
    n_workers = min(n_workers, len(texts))
    chunk_size = (len(texts) + n_workers - 1) // n_workers

    shards = [
        texts[i * chunk_size : (i + 1) * chunk_size]
        for i in range(n_workers)
        if texts[i * chunk_size : (i + 1) * chunk_size]
    ]
    actual_workers = len(shards)

    pool_args = [(shard, model, batch_size, idx) for idx, shard in enumerate(shards)]

    console.print(f"  Spawning {actual_workers} workers × {chunk_size} entries each …")
    with multiprocessing.Pool(actual_workers) as pool:
        results = pool.map(_embed_shard, pool_args)

    return np.concatenate(results, axis=0)


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------
def save_cache(
    path: str,
    embeddings: np.ndarray,
    texts: list[str],
    timestamps: list[datetime],
) -> None:
    """Save embeddings + metadata to JSON.

    :param path: Output file path.
    :param embeddings: Float32 (N, D) array.
    :param texts: Aligned list of entry strings.
    :param timestamps: Aligned list of datetime objects.
    """
    data = {
        "embeddings": embeddings.tolist(),
        "texts": texts,
        "timestamps": [ts.isoformat() for ts in timestamps],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    console.print(f"[green]Cache saved ({len(texts)} entries) → {path}[/green]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Diary multi-process embedder — builds JSON cache for manifold analysis"
    )
    p.add_argument(
        "--diary",
        default=DEFAULT_DIARY,
        help=f"Pipe-delimited diary file (default: {DEFAULT_DIARY})",
    )
    p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output JSON cache path (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--n",
        type=int,
        default=0,
        help="Temporally sampled subset size (0 = embed full corpus)",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"HuggingFace model id (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel embedding workers (default: 4)",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Encoding batch size per worker (default: 32)",
    )
    p.add_argument(
        "--max-chars",
        type=int,
        default=0,
        help="Truncate each entry to this many characters before embedding (0 = no limit)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file without prompting",
    )
    p.add_argument(
        "--summary-file",
        default=None,
        help="Path for the Markdown run summary (default: <output-stem>_run_summary.md)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    console.rule("[bold blue]Diary · Multi-Process Embedder")

    diary_path = Path(args.diary)
    if not diary_path.exists():
        console.print(f"[red]Diary file not found: {diary_path}[/red]")
        sys.exit(1)

    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        console.print(
            f"[yellow]Output already exists: {output_path}\nPass --force to overwrite.[/yellow]"
        )
        sys.exit(0)

    if output_path.exists() and args.force:
        output_path.unlink()
        console.print(f"[yellow]Cleared existing cache: {output_path}[/yellow]")

    # Step 1: Parse
    console.print(f"\n[bold]Step 1:[/bold] Parsing {diary_path} …")
    texts, timestamps = parse_diary(str(diary_path))
    n_parsed = len(texts)
    console.print(
        f"  Parsed {n_parsed} total entries  ({timestamps[0].date()} → {timestamps[-1].date()})"
    )

    # Step 2: Truncate
    if args.max_chars:
        n_long = sum(1 for t in texts if len(t) > args.max_chars)
        if n_long:
            console.print(f"  Truncating {n_long} entries to {args.max_chars} chars")
        texts = [t[: args.max_chars] for t in texts]

    # Step 3: Temporal sample
    if args.n and args.n < len(texts):
        texts, timestamps = temporally_sample(texts, timestamps, args.n)
        console.print(
            f"  Temporally sampled {len(texts)} entries  "
            f"({timestamps[0].date()} → {timestamps[-1].date()})"
        )

    # Step 4: Embed
    n_workers = args.workers or 4
    console.print(
        f"\n[bold]Step 2:[/bold] Embedding {len(texts)} entries  "
        f"model={args.model}  workers={n_workers}  batch={args.batch_size} …"
    )
    t0 = time.time()
    try:
        E = embed_multiprocess(
            texts,
            model=args.model,
            n_workers=n_workers,
            batch_size=args.batch_size,
        )
    except Exception as exc:
        console.print(f"[red]Embedding failed: {exc}[/red]")
        raise

    elapsed = time.time() - t0
    console.print(
        f"  Done: {E.shape[0]} × {E.shape[1]} float32  "
        f"in {elapsed:.1f}s  ({elapsed / max(len(texts), 1):.3f}s/entry)"
    )

    # Step 5: Save
    console.print("\n[bold]Step 3:[/bold] Saving cache …")
    save_cache(str(output_path), E, texts, timestamps)

    # Step 6: Run summary
    write_run_summary(
        str(output_path),
        run_params={
            "timestamp": datetime.now().isoformat(),
            "diary_file": str(diary_path),
            "model": args.model,
            "workers": n_workers,
            "batch_size": args.batch_size,
            "n_sample": args.n or "all",
            "max_chars": args.max_chars or "none",
        },
        stats={
            "entries_parsed": n_parsed,
            "entries_embedded": E.shape[0],
            "time_range_start": timestamps[0].date(),
            "time_range_end": timestamps[-1].date(),
            "embedding_shape": (E.shape[0], E.shape[1]),
            "runtime_s": elapsed,
        },
        summary_file=args.summary_file,
    )


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    main()

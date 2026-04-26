#!/usr/bin/env python3
# pepys_ingestion_sweep.py
# Copyright (c) 2026 Eric G. Suchanek, PhD, Flux-Frontiers
# License: Elastic 2.0
"""
pepys_ingestion_sweep.py
------------------------
2-D sweep of full-corpus Pepys embedding speed over workers × batch_size.

For each (workers, batch_size) pair the full corpus is re-embedded from the
pre-parsed texts (no disk I/O between runs) and the wall-clock embedding time
is recorded.  Results are written incrementally so a partial run is never lost.

Output JSON matches the canonical benchmark format used in the WaveRider
mission suite (pepys_mpnet_results.json / pepys_ch5_flight_results.json).

Usage
-----
  # default grid (may take ~30-45 min on M-series Mac)
  python benchmarks/pepys_ingestion_sweep.py

  # quick test: only 2 worker values, 2 batch sizes
  python benchmarks/pepys_ingestion_sweep.py --workers 2 4 --batches 32 64

  # custom output path
  python benchmarks/pepys_ingestion_sweep.py --output benchmarks/my_sweep.json

  # resume / append to existing results (skips completed (workers,batch_size) pairs)
  python benchmarks/pepys_ingestion_sweep.py --resume
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import platform
import sys
import time
from datetime import datetime
from math import ceil
from pathlib import Path

from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from diary_transformer.diary_embedder import (  # noqa: E402
    DEFAULT_DIARY,
    DEFAULT_MODEL,
    _embed_shard,
    parse_diary,
)

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    _VERSION = _pkg_version("diary-kg")
except (ImportError, PackageNotFoundError):
    _VERSION = "unknown"

import numpy as np  # noqa: E402

console = Console()

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_WORKERS = [1, 2, 4, 6, 8, 10, 12, 16, 18]
DEFAULT_BATCHES = [16, 32, 64, 128, 256]
DEFAULT_OUTPUT = str(_REPO_ROOT / "benchmarks" / "pepys_ingestion_sweep_results.json")


# ---------------------------------------------------------------------------
# Single timed run
# ---------------------------------------------------------------------------
def run_one(
    texts: list[str],
    model: str,
    n_workers: int,
    batch_size: int,
) -> dict:
    """Embed *texts* with the given config and return a result dict.

    :param texts: Pre-parsed corpus strings.
    :param model: HuggingFace model id.
    :param n_workers: Number of parallel embedding workers.
    :param batch_size: Encoding batch size per worker.
    :return: Result dict with timing and config metadata.
    """
    n = len(texts)
    actual_workers = min(n_workers, n)
    chunk_size = ceil(n / actual_workers)

    shards = [
        texts[i * chunk_size : (i + 1) * chunk_size]
        for i in range(actual_workers)
        if texts[i * chunk_size : (i + 1) * chunk_size]
    ]
    actual_workers = len(shards)
    pool_args = [(shard, model, batch_size, idx) for idx, shard in enumerate(shards)]

    t0 = time.perf_counter()
    with multiprocessing.Pool(actual_workers) as pool:
        results = pool.map(_embed_shard, pool_args)
    wall_time = time.perf_counter() - t0

    E = np.concatenate(results, axis=0)

    return {
        "workers": n_workers,
        "actual_workers": actual_workers,
        "batch_size": batch_size,
        "chunk_size": chunk_size,
        "wall_time_s": round(wall_time, 3),
        "entries_per_sec": round(n / wall_time, 2),
        "sec_per_entry": round(wall_time / n, 5),
        "embedding_shape": list(E.shape),
    }


# ---------------------------------------------------------------------------
# Incremental save
# ---------------------------------------------------------------------------
def _load_existing(path: str) -> dict | None:
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _save(path: str, doc: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------
def _best_result(results: list[dict]) -> dict:
    return min(results, key=lambda r: r["wall_time_s"])


def _print_progress_table(results: list[dict]) -> None:
    tbl = Table(title="Ingestion Sweep — Results So Far", show_lines=True)
    tbl.add_column("workers", justify="right")
    tbl.add_column("batch_size", justify="right")
    tbl.add_column("chunk_size", justify="right")
    tbl.add_column("wall_time_s", justify="right")
    tbl.add_column("entries/sec", justify="right")
    for r in sorted(results, key=lambda x: (x["wall_time_s"],)):
        tbl.add_row(
            str(r["workers"]),
            str(r["batch_size"]),
            str(r["chunk_size"]),
            f"{r['wall_time_s']:.1f}",
            f"{r['entries_per_sec']:.1f}",
        )
    console.print(tbl)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="2-D sweep of Pepys full-corpus embedding speed: workers × batch_size"
    )
    p.add_argument(
        "--diary",
        default=DEFAULT_DIARY,
        help=f"Pipe-delimited diary file (default: {DEFAULT_DIARY})",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"HuggingFace model id (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--workers",
        nargs="+",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help=f"Worker counts to sweep (default: {DEFAULT_WORKERS})",
    )
    p.add_argument(
        "--batches",
        nargs="+",
        type=int,
        default=DEFAULT_BATCHES,
        metavar="B",
        help=f"Batch sizes to sweep (default: {DEFAULT_BATCHES})",
    )
    p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Skip (workers, batch_size) pairs already present in the output file",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    multiprocessing.set_start_method("spawn", force=True)
    args = parse_args()

    console.rule("[bold blue]Pepys Ingestion Sweep — workers × batch_size")

    # ---- Parse corpus once ----
    diary_path = Path(args.diary)
    if not diary_path.exists():
        console.print(f"[red]Diary file not found: {diary_path}[/red]")
        sys.exit(1)

    console.print(f"\nParsing corpus: {diary_path} …")
    texts, timestamps = parse_diary(str(diary_path))
    n_entries = len(texts)
    date_range = [timestamps[0].isoformat(), timestamps[-1].isoformat()]
    console.print(f"  {n_entries} entries  ({timestamps[0].date()} → {timestamps[-1].date()})")

    # ---- Build benchmark document skeleton ----
    now = datetime.now().isoformat(timespec="seconds")
    doc: dict = {
        "benchmark": "pepys_ingestion_sweep",
        "description": "Full Pepys corpus embedding sweep: wall time vs. workers × batch_size",
        "timestamp": now,
        "version": _VERSION,
        "machine": {
            "platform": platform.system().lower(),
            "arch": platform.machine(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
        },
        "model": args.model,
        "corpus": {
            "file": str(diary_path),
            "n_entries": n_entries,
            "date_range": date_range,
        },
        "sweep_config": {
            "workers": args.workers,
            "batch_sizes": args.batches,
        },
        "results": [],
        "summary": {},
    }

    # ---- Resume: load existing results ----
    completed: set[tuple[int, int]] = set()
    if args.resume:
        existing = _load_existing(args.output)
        if existing:
            doc["results"] = existing.get("results", [])
            completed = {(r["workers"], r["batch_size"]) for r in doc["results"]}
            console.print(f"[yellow]Resuming: {len(completed)} pair(s) already complete[/yellow]")

    # ---- Grid sweep ----
    total = len(args.workers) * len(args.batches)
    done = len(completed)

    for n_workers in args.workers:
        for batch_size in args.batches:
            done += 1
            if (n_workers, batch_size) in completed:
                console.print(
                    f"  [dim]Skip ({n_workers}w × bs{batch_size}) — already complete[/dim]"
                )
                continue

            chunk_size = ceil(n_entries / min(n_workers, n_entries))
            console.print(
                f"\n[bold cyan][{done}/{total}][/bold cyan] "
                f"workers={n_workers}  batch_size={batch_size}  "
                f"chunk_size={chunk_size} …"
            )

            try:
                result = run_one(texts, args.model, n_workers, batch_size)
            except Exception as exc:
                console.print(f"  [red]FAILED: {exc}[/red]")
                result = {
                    "workers": n_workers,
                    "batch_size": batch_size,
                    "chunk_size": chunk_size,
                    "wall_time_s": None,
                    "entries_per_sec": None,
                    "sec_per_entry": None,
                    "embedding_shape": None,
                    "error": str(exc),
                }

            doc["results"].append(result)
            completed.add((n_workers, batch_size))

            if result["wall_time_s"] is not None:
                console.print(
                    f"  → {result['wall_time_s']:.1f}s  "
                    f"({result['entries_per_sec']:.1f} entries/sec)"
                )

            # Incremental save after every run
            _save(args.output, doc)

    # ---- Summary ----
    good = [r for r in doc["results"] if r.get("wall_time_s") is not None]
    if good:
        best = _best_result(good)
        worst = max(good, key=lambda r: r["wall_time_s"])
        doc["summary"] = {
            "total_runs": len(doc["results"]),
            "successful_runs": len(good),
            "best": {
                "workers": best["workers"],
                "batch_size": best["batch_size"],
                "chunk_size": best["chunk_size"],
                "wall_time_s": best["wall_time_s"],
                "entries_per_sec": best["entries_per_sec"],
            },
            "worst": {
                "workers": worst["workers"],
                "batch_size": worst["batch_size"],
                "wall_time_s": worst["wall_time_s"],
                "entries_per_sec": worst["entries_per_sec"],
            },
            "speedup_best_vs_worst": round(worst["wall_time_s"] / best["wall_time_s"], 2)
            if best["wall_time_s"]
            else None,
        }

        _save(args.output, doc)
        console.rule("[bold green]Sweep Complete")
        _print_progress_table(good)
        console.print(
            f"\n[green]Best:[/green] {best['workers']} workers × "
            f"batch_size {best['batch_size']}  →  "
            f"[bold]{best['wall_time_s']:.1f}s[/bold]  "
            f"({best['entries_per_sec']:.1f} entries/sec)"
        )
        console.print(f"Results saved → [bold]{args.output}[/bold]")
    else:
        console.print("[red]No successful runs — check errors above.[/red]")


if __name__ == "__main__":
    main()

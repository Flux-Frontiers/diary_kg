#!/usr/bin/env python3
# pepys_ch5_flight.py
# Copyright (c) 2026 Eric G. Suchanek, PhD, Flux-Frontiers
# https://github.com/Flux-Frontiers
# License: Elastic 2.0
# Last revised: 2026-03-27 -egs-
"""
pepys_ch5_flight.py
--------------------
The Chapter 5 experiment: destination-relative temporal encoding.

This is the *corrected* temporal flight described in WaveRider Chapter 5 —
not the z-scored absolute encoding from T-1, but the destination-relative
formulation:

    temporal_coord = abs(entry.fractional_year - destination.fractional_year)

Under this encoding, the destination has temporal coordinate 0.  Every other
entry has a positive coordinate equal to its distance in time from the
destination.  The KNN graph pulls the turtle toward zero — toward the
destination — as a gravitational effect of the geometry.

Specific flight: Pepys diary, 1663-10-21 → 1664-01-23.
Uses the full 6450-entry mpnet corpus from diary_kg.

Outputs every hop with date, text, and running Kendall tau.
Saves results JSON and prints mission data appendix.

Usage
-----
  python benchmarks/pepys_ch5_flight.py

  # or with custom corpus path
  python benchmarks/pepys_ch5_flight.py \\
      --corpus /path/to/pepys_mpnet_embeddings.json \\
      --origin-date 1663-10-21 \\
      --dest-date 1664-01-23
"""

from __future__ import annotations

import argparse

# Direct import of turtleND
import importlib.util as _ilu
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table

_tnd_path = str(
    Path(__file__).resolve().parent.parent.parent / "proteusPy" / "proteusPy" / "turtleND.py"
)
_spec = _ilu.spec_from_file_location("turtleND", _tnd_path)
assert _spec is not None and _spec.loader is not None, f"Cannot load turtleND from {_tnd_path}"
_tnd_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_tnd_mod)  # type: ignore[union-attr]
TurtleND = _tnd_mod.TurtleND

console = Console()

DEFAULT_CORPUS = str(
    Path(__file__).resolve().parent.parent.parent
    / "diary_kg"
    / "benchmarks"
    / "pepys_mpnet_embeddings.json"
)
DEFAULT_OUT = str(Path(__file__).parent / "pepys_ch5_flight_results.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fractional_year(dt: datetime) -> float:
    return dt.year + (dt.timetuple().tm_yday - 1) / 365.25 + dt.hour / (365.25 * 24)


def load_corpus(path: str) -> tuple[np.ndarray, list[str], list[datetime]]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    embeddings = np.array(data["embeddings"], dtype=np.float32)
    texts = data["texts"]
    timestamps = [datetime.fromisoformat(ts) for ts in data["timestamps"]]
    return embeddings, texts, timestamps


def augment_dest_relative(
    embeddings: np.ndarray,
    fyears: np.ndarray,
    dest_fyear: float,
    alpha: float = 1.0,
) -> np.ndarray:
    """Append destination-relative temporal coordinate as (D+1)-th dimension.

    temporal_coord = abs(fyear_i - fyear_dest)

    Destination lands at 0.  ALL other entries — past *and* future — have
    positive coordinates proportional to their temporal distance from it.
    The greedy direction vector from any node always points toward smaller
    temporal values (toward zero), penalising entries that are temporally
    far from the destination in either direction.  This prevents both
    undershooting *and* overshooting.

    Alpha controls the strength of the temporal pull relative to a single
    semantic axis.  At alpha=1 the temporal axis contributes 1/768 of the
    total signal — negligible.  At alpha≈sqrt(768)≈27.7 it matches the
    full semantic contribution.  alpha=10–20 gives useful temporal gravity
    without destroying semantic content.

    :param embeddings: (N, D) float array (should be L2-normalised).
    :param fyears: (N,) fractional years.
    :param dest_fyear: fractional year of the destination entry.
    :param alpha: temporal weight relative to a single semantic axis.
    :return: (N, D+1) augmented array.
    """
    t_raw = np.abs(fyears - dest_fyear)  # destination = 0, symmetric gravitational basin

    # Scale to match embedding axis magnitude × alpha
    emb_norms = np.linalg.norm(embeddings, axis=1)
    mean_norm = emb_norms.mean()
    scale = alpha * (mean_norm / math.sqrt(embeddings.shape[1]))

    # Normalise to [0, 1] then apply scale
    t_max = t_raw.max()
    t_scaled = (t_raw / t_max) * scale if t_max > 1e-12 else t_raw * scale

    return np.column_stack([embeddings, t_scaled])


def kendall_tau(times: np.ndarray) -> float:
    """Manual Kendall tau — rank correlation between path order and time."""
    n = len(times)
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if times[j] > times[i]:
                concordant += 1
            elif times[j] < times[i]:
                discordant += 1
    denom = concordant + discordant
    return (concordant - discordant) / denom if denom > 0 else 0.0


# ---------------------------------------------------------------------------
# Flight
# ---------------------------------------------------------------------------


def run_flight(
    E_aug: np.ndarray,
    fyears: np.ndarray,
    texts: list[str],
    timestamps: list[datetime],
    origin_idx: int,
    dest_idx: int,
    k: int = 10,
    max_steps: int = 150,
) -> list[dict]:
    """Run destination-directed greedy KNN flight.

    At each step, choose the neighbour whose direction in augmented space
    most aligns with the vector pointing toward the destination.

    :return: List of hop records (index, date, text snippet, running tau).
    """
    from sklearn.neighbors import NearestNeighbors

    N = len(E_aug)
    k = min(k, N - 1)

    console.print(f"  Building KNN graph (k={k}, N={N}) …")
    t0 = time.time()
    nbrs = NearestNeighbors(n_neighbors=k + 1, metric="euclidean")
    nbrs.fit(E_aug)
    _, indices = nbrs.kneighbors(E_aug)
    console.print(f"  KNN built in {time.time() - t0:.1f}s")

    turtle = TurtleND(ndim=E_aug.shape[1], name="PepysCh5")
    turtle.position = E_aug[origin_idx].astype(np.float64)

    current = origin_idx
    path = [origin_idx]
    visited = {origin_idx}

    dest_emb = E_aug[dest_idx].astype(np.float64)

    for step in range(max_steps):
        neighbors = [int(j) for j in indices[current] if j != current and j not in visited]
        if not neighbors:
            break

        direction = dest_emb - E_aug[current]
        dn = np.linalg.norm(direction)
        if dn < 1e-10:
            break
        direction /= dn

        best_score = -np.inf
        best_idx = None
        for j in neighbors:
            step_vec = E_aug[j] - E_aug[current]
            norm = np.linalg.norm(step_vec)
            if norm < 1e-10:
                continue
            score = float(np.dot(step_vec / norm, direction))
            if score > best_score:
                best_score = score
                best_idx = j

        if best_idx is None:
            break

        turtle.position = E_aug[best_idx].astype(np.float64)
        current = best_idx
        path.append(best_idx)
        visited.add(best_idx)

        if best_idx == dest_idx:
            break

    # Build hop records
    path_times = fyears[path]
    hops = []
    for hop_n, idx in enumerate(path):
        running_tau = kendall_tau(path_times[: hop_n + 1]) if hop_n > 1 else None
        hops.append(
            {
                "hop": hop_n,
                "idx": int(idx),
                "date": timestamps[idx].strftime("%Y-%m-%d"),
                "text": texts[idx][:120],
                "fyear": round(float(fyears[idx]), 4),
                "running_tau": (round(running_tau, 4) if running_tau is not None else None),
            }
        )

    return hops


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="WaveRider Chapter 5 temporal flight")
    p.add_argument("--corpus", default=DEFAULT_CORPUS, help="Path to pepys_mpnet_embeddings.json")
    p.add_argument("--origin-date", default="1663-10-21", help="Target origin date (YYYY-MM-DD)")
    p.add_argument(
        "--origin-entry",
        type=int,
        default=0,
        help="Which entry on origin date to use (0-indexed)",
    )
    p.add_argument("--dest-date", default="1664-01-23", help="Target destination date (YYYY-MM-DD)")
    p.add_argument(
        "--dest-entry",
        type=int,
        default=0,
        help="Which entry on dest date to use (0-indexed)",
    )
    p.add_argument(
        "--alpha",
        type=float,
        default=10.0,
        help="Temporal weight (alpha=1 ≈ 1 semantic axis; alpha≈27.7 ≈ full semantic weight; default: 10)",
    )
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--max-steps", type=int, default=150)
    p.add_argument(
        "--pca-dim",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Project embeddings to N dims via PCA before augmenting the temporal axis. "
            "Recalibrate alpha: at pca_dim=D, alpha≈5*sqrt(D) matches full semantic weight. "
            "Default: None (no reduction; use full 768D)."
        ),
    )
    p.add_argument("--out", default=DEFAULT_OUT)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    console.rule("[bold blue]WaveRider Chapter 5 — Destination-Relative Temporal Flight")

    # ------------------------------------------------------------------
    # Load corpus
    # ------------------------------------------------------------------
    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        console.print(f"[red]Corpus not found: {corpus_path}[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Loading corpus:[/bold] {corpus_path.name} …")
    E, texts, timestamps = load_corpus(str(corpus_path))
    N, D = E.shape
    console.print(
        f"  {N} entries × {D} dims  ({min(timestamps).date()} → {max(timestamps).date()})"
    )

    # L2-normalise
    norms = np.linalg.norm(E, axis=1, keepdims=True)
    E = E / np.clip(norms, 1e-8, None)

    # ------------------------------------------------------------------
    # Optional PCA dimensionality reduction
    # ------------------------------------------------------------------
    pca_var_explained = None
    if args.pca_dim is not None:
        from sklearn.decomposition import PCA

        target = min(args.pca_dim, D)
        console.print(f"\n[bold]PCA reduction:[/bold] {D}D → {target}D …")
        t0 = time.time()
        pca = PCA(n_components=target, random_state=42)
        E = pca.fit_transform(E).astype(np.float32)
        pca_var_explained = float(pca.explained_variance_ratio_.sum())
        D = E.shape[1]
        console.print(f"  Variance explained: {pca_var_explained:.4f}  ({time.time() - t0:.1f}s)")

    fyears = np.array([fractional_year(t) for t in timestamps])

    # ------------------------------------------------------------------
    # Find origin and destination indices
    # ------------------------------------------------------------------
    def entries_on_date(date_str: str) -> list[int]:
        return [i for i, t in enumerate(timestamps) if t.strftime("%Y-%m-%d") == date_str]

    origin_candidates = entries_on_date(args.origin_date)
    dest_candidates = entries_on_date(args.dest_date)

    if not origin_candidates:
        console.print(f"[red]No entries found for origin date {args.origin_date}[/red]")
        sys.exit(1)
    if not dest_candidates:
        console.print(f"[red]No entries found for dest date {args.dest_date}[/red]")
        sys.exit(1)

    origin_idx = origin_candidates[min(args.origin_entry, len(origin_candidates) - 1)]
    dest_idx = dest_candidates[min(args.dest_entry, len(dest_candidates) - 1)]

    console.print(f"\n[bold]Origin:[/bold]  [{origin_idx}] {timestamps[origin_idx].date()}")
    console.print(f"  {texts[origin_idx][:100]}")
    console.print(f"\n[bold]Dest:  [/bold] [{dest_idx}] {timestamps[dest_idx].date()}")
    console.print(f"  {texts[dest_idx][:100]}")

    dest_fyear = float(fyears[dest_idx])
    span_days = int((fyears[dest_idx] - fyears[origin_idx]) * 365.25)
    console.print(f"\n  Temporal span: {span_days} days")

    # ------------------------------------------------------------------
    # Build destination-relative augmented space
    # ------------------------------------------------------------------
    console.print(f"\n[bold]Augmenting:[/bold] destination-relative encoding (α={args.alpha}) …")
    E_aug = augment_dest_relative(E, fyears, dest_fyear, alpha=args.alpha)
    console.print(f"  {D}D → {E_aug.shape[1]}D  (temporal axis appended)")
    t_col = E_aug[:, -1]
    console.print(
        f"  Temporal axis: origin={t_col[origin_idx]:.4f}, "
        f"dest={t_col[dest_idx]:.4f} (=0), "
        f"max={t_col.max():.4f}  (α={args.alpha})"
    )

    # ------------------------------------------------------------------
    # Fly
    # ------------------------------------------------------------------
    console.print(
        f"\n[bold]Flying:[/bold] {args.origin_date} → {args.dest_date} "
        f"(max {args.max_steps} hops, k={args.k}) …"
    )
    hops = run_flight(
        E_aug,
        fyears,
        texts,
        timestamps,
        origin_idx,
        dest_idx,
        k=args.k,
        max_steps=args.max_steps,
    )

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    path_times = fyears[[h["idx"] for h in hops]]
    final_tau = kendall_tau(path_times)
    monotonicity = float(np.mean(np.diff(path_times) > 0)) if len(path_times) > 1 else 1.0
    reached = hops[-1]["idx"] == dest_idx

    console.print()
    table = Table(
        title=f"Hop Log — {len(hops)} hops  τ={final_tau:.4f}  reached={reached}",
        show_header=True,
    )
    table.add_column("Hop", justify="right", style="dim")
    table.add_column("Date", style="cyan")
    table.add_column("τ (running)", justify="right", style="green")
    table.add_column("Entry (truncated)")

    for h in hops:
        tau_str = f"{h['running_tau']:.3f}" if h["running_tau"] is not None else "—"
        table.add_row(str(h["hop"]), h["date"], tau_str, h["text"][:80])
    console.print(table)

    # ------------------------------------------------------------------
    # Mission Data Appendix
    # ------------------------------------------------------------------
    console.rule("[bold]Mission Data Appendix")
    appendix = Table(show_header=False, box=None)
    appendix.add_column("Parameter", style="bold cyan")
    appendix.add_column("Value")
    rows = [
        ("Corpus", f"Pepys mpnet, {N} entries, {D}D"),
        ("Encoding", "Destination-relative: abs(fyear_i − fyear_dest), symmetric basin"),
        (
            "Origin",
            f"[{origin_idx}] {timestamps[origin_idx].date()} — {texts[origin_idx][:70]}",
        ),
        (
            "Destination",
            f"[{dest_idx}] {timestamps[dest_idx].date()} — {texts[dest_idx][:70]}",
        ),
        ("Temporal span", f"{span_days} days"),
        ("α", str(args.alpha)),
        ("k", str(args.k)),
        ("Path length", str(len(hops))),
        ("Reached destination", str(reached)),
        ("Final Kendall τ", f"{final_tau:.4f}"),
        ("Monotonicity", f"{monotonicity:.1%}"),
        ("First hop date", hops[1]["date"] if len(hops) > 1 else "—"),
        ("Last hop date", hops[-1]["date"]),
    ]
    for k_, v in rows:
        appendix.add_row(k_, v)
    console.print(appendix)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    results = {
        "corpus": str(corpus_path),
        "N": N,
        "D": D,
        "pca_dim": args.pca_dim,
        "pca_var_explained": pca_var_explained,
        "alpha": args.alpha,
        "k": args.k,
        "encoding": "destination_relative_abs",
        "origin_idx": origin_idx,
        "dest_idx": dest_idx,
        "origin_date": timestamps[origin_idx].isoformat(),
        "dest_date": timestamps[dest_idx].isoformat(),
        "span_days": span_days,
        "path_length": len(hops),
        "reached_destination": reached,
        "final_kendall_tau": round(final_tau, 4),
        "monotonicity": round(monotonicity, 4),
        "hops": hops,
    }

    class _NpEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, np.floating):
                return float(o)
            return super().default(o)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, cls=_NpEncoder)
    console.print(f"\n[dim]Results saved → {args.out}[/dim]")
    console.rule("[bold green]Done")


if __name__ == "__main__":
    main()

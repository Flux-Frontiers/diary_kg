#!/usr/bin/env python3
"""
mcp_server.py — DiaryKG MCP Server

Exposes the DiaryKG semantic search and text-pack pipeline as Model Context
Protocol (MCP) tools for MCP-compatible agents (Claude Code, Claude Desktop,
GitHub Copilot, etc.).

Tools
-----
query_diary   — semantic search; returns ranked JSON hit list
pack_diary    — semantic search + Markdown text pack for LLM ingestion
diary_stats   — corpus metadata + KG node/edge counts

Usage
-----
    diarykg-mcp --repo /path/to/project [--source diary.txt] [--model <name>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from diary_kg.kg import DEFAULT_MODEL, DiaryKG

_kg: DiaryKG | None = None  # pylint: disable=invalid-name


def _get_kg() -> DiaryKG:
    """Return the global DiaryKG instance, raising if not initialised."""
    if _kg is None:
        raise RuntimeError("DiaryKG not initialised. Run via 'diarykg-mcp --repo /path/to/project'")
    return _kg


mcp = FastMCP(
    "diarykg",
    instructions=(
        "DiaryKG is a semantic knowledge graph for diary and journal corpora. "
        "Use these tools to search diary entries, retrieve source text, and "
        "inspect corpus statistics."
    ),
)


@mcp.tool()
def query_diary(q: str, k: int = 8) -> str:
    """Semantic search over the diary corpus; returns ranked JSON hit list.

    Each hit contains: node_id, score, summary, source_file, timestamp,
    category, context.
    """
    hits = _get_kg().query(q, k=k)
    return json.dumps(hits, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
def pack_diary(q: str, k: int = 8) -> str:
    """Semantic search + Markdown text pack for LLM ingestion.

    Returns the top-k diary snippets matching *q* formatted as Markdown
    sections, ready to paste into an LLM context window.
    """
    snippets = _get_kg().pack(q, k=k)
    if not snippets:
        return f"_No diary snippets found for query: {q!r}_"

    parts = [f"# DiaryKG Pack: {q!r}\n"]
    for s in snippets:
        ts = s.get("timestamp") or ""
        src = s.get("source_file") or ""
        header = f"## {src}"
        if ts:
            header += f" @ {ts[:10]}"
        parts.append(header)
        parts.append(f"```\n{s.get('content', '')}\n```")
    return "\n\n".join(parts)


@mcp.tool()
def diary_stats() -> str:
    """Return corpus metadata and KG node/edge counts as JSON.

    Combines DiaryKG.info() (chunk count, entry count, temporal span,
    topic/context distributions) with DiaryKG.stats() (node_count,
    edge_count).
    """
    kg = _get_kg()
    info = kg.info()
    stats = kg.stats()
    combined = {**info, **stats}
    return json.dumps(combined, indent=2, ensure_ascii=False, default=str)


def _parse_args(argv: list | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="diarykg-mcp",
        description="DiaryKG MCP server — exposes diary knowledge graph tools to AI agents.",
    )
    p.add_argument("--repo", default=".", help="Project root directory (default: .)")
    p.add_argument(
        "--source",
        default=None,
        help="Relative path to diary .txt source inside --repo (required on first build)",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Sentence-transformer model name (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport: stdio (default) or sse",
    )
    return p.parse_args(argv)


def main(argv: list | None = None) -> None:
    """Start the DiaryKG MCP server and expose tools over the chosen transport."""
    global _kg  # pylint: disable=global-statement

    args = _parse_args(argv)
    repo = Path(args.repo).resolve()

    if not repo.is_dir():
        print(f"ERROR: --repo '{repo}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    kg_dir = repo / DiaryKG.KG_DIR
    db = kg_dir / "graph.sqlite"
    lancedb_dir = kg_dir / "lancedb"

    if not db.exists():
        print(
            f"WARNING: SQLite database not found at '{db}'.\n"
            f"Run 'diarykg build --source <file>' first.",
            file=sys.stderr,
        )

    print(
        f"DiaryKG MCP server starting\n"
        f"  repo     : {repo}\n"
        f"  db       : {db}\n"
        f"  lancedb  : {lancedb_dir}\n"
        f"  model    : {args.model}\n"
        f"  transport: {args.transport}",
        file=sys.stderr,
    )

    _kg = DiaryKG(root=repo, source_file=args.source, model=args.model)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

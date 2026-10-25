#!/usr/bin/env python3
"""
mcp_server.py — DiaryKG MCP Server

Serves a diary corpus's knowledge graph to any MCP-compatible agent over the
fleet's shared server base, :mod:`kg_utils.mcp`.

The server answers the fleet's canonical tools -- ``stats``, ``query``,
``pack``, ``get_node``, ``neighbors`` -- under the same names as every other
KG server. ``stats``, ``query`` and ``pack`` are DiaryKG's own: ``stats``
adds the corpus's temporal span and topic counts, and ``query`` and ``pack``
rank diary entries by fused dense + keyword (BM25) retrieval, carrying each
entry's date and source. ``get_node`` and ``neighbors`` are the shared ones.

The tool list is not kept by hand anywhere: each tool's docstring is its
description, the server's instructions are generated from them, and::

    diarykg mcp --manifest

prints the whole list as JSON without opening the graph.

Usage
-----
::

    diarykg mcp --repo /path/to/project

``--db`` and ``--vectors`` default to ``.diarykg/graph.sqlite`` and
``.diarykg/vectors.sqlite``; a relative path is taken from ``--repo``.
``diarykg-mcp`` is the same command under its older name.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from kg_utils.mcp import Context, KGServer, kg_from, make_server

from diary_kg import __version__
from diary_kg.kg import DEFAULT_MODEL, DiaryKG

PREAMBLE = (
    "DiaryKG is a semantic knowledge graph for diary and journal corpora. Each "
    "diary entry is chunked into 'chunk:<file>:<0000>' nodes carrying its date "
    "(timestamp), topic category and context; documents ('doc:<file>'), sections "
    "and topics ('topic:<slug>') hold them together. Edges: CONTAINS, NEXT "
    "(adjacent entries), SIMILAR_TO, HAS_TOPIC, MENTIONS_ENTITY, HAS_KEYWORD.\n\n"
    "## Recommended workflows\n\n"
    "- **Orientation**: stats (entry count, temporal span, topic distribution)\n"
    "- **Find entries on a subject**: query → get_node\n"
    "- **Read them**: pack with a descriptive query\n"
    "- **Read around an entry**: neighbors(node_id, rels=['NEXT']) for the entries "
    "beside it; query/pack with hop=1 to bring each hit's neighbourhood along"
)


def stats(*, ctx: Context) -> dict[str, Any]:
    """
    Corpus overview: entry and chunk counts, temporal span, topic and context counts, node and edge totals.
    """
    kg: DiaryKG = kg_from(ctx)
    return {**kg.info(), **kg.stats()}


def query(
    q: str,
    k: int = 8,
    hop: int = 0,
    max_nodes: int = 25,
    rels: list[str] | None = None,
    *,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search the diary: ranked entries with their dates, topics, context and source.

    Seeds fuse dense (vector) and keyword (BM25) matches over entry chunks. Use
    ``pack`` instead when you want the entries' text.

    :param q: Natural-language query.
    :param k: Entry chunks to seed from (default 8).
    :param hop: Graph hops to bring along from each seed (0-5, default 0:
        the seeds alone).
    :param max_nodes: Most results, seeds included (default 25).
    :param rels: Edge types to expand along when hop > 0; omit for the defaults.
    """
    hits = kg_from(ctx).query(q, k=k, hop=hop, max_nodes=max_nodes, rels=rels)
    return {"query": q, "hits": hits}


def pack(
    q: str,
    k: int = 8,
    hop: int = 0,
    max_nodes: int = 15,
    rels: list[str] | None = None,
    *,
    ctx: Context,
) -> str:
    """
    Search the diary and return the matching entries' text as Markdown, dated and sourced.

    :param q: Natural-language query.
    :param k: Entry chunks to seed from (default 8).
    :param hop: Graph hops to bring along from each seed (0-5, default 0).
    :param max_nodes: Most entries, seeds included (default 15).
    :param rels: Edge types to expand along when hop > 0; omit for the defaults.
    """
    snippets = kg_from(ctx).pack(q, k=k, hop=hop, max_nodes=max_nodes, rels=rels)
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


def build_server(
    repo: str | Path,
    db: str | Path | None = None,
    vectors: str | Path | None = None,
    model: str | None = None,
) -> KGServer:
    """Build the DiaryKG MCP server for one project, without opening its graph.

    The diary's source file is read from ``.diarykg/config.json``, written by
    ``diarykg build``.

    :param repo: Project root holding ``.diarykg/``.
    :param db: Graph database; ``None`` for ``<repo>/.diarykg/graph.sqlite``.
    :param vectors: Vector store; ``None`` for ``<repo>/.diarykg/vectors.sqlite``.
    :param model: Embedding model; ``None`` for :data:`DEFAULT_MODEL`.
    :return: The server; serve it with :func:`kg_utils.mcp.run`.
    """
    root = Path(repo).resolve()

    def open_kg() -> DiaryKG:
        return DiaryKG(root, model=model or DEFAULT_MODEL, db_path=db, vectors_path=vectors)

    server = make_server(
        open_kg, name="diarykg", kind="diary", version=__version__, instructions=PREAMBLE
    )
    server.canonical("stats")(stats)
    server.canonical("query")(query)
    server.canonical("pack")(pack)
    return server


def _drop_source(argv: list[str]) -> list[str]:
    """Drop the pre-0.101.0 ``--source`` flag, which serving never needed.

    Claude Desktop and Copilot configs hard-code ``diarykg-mcp`` with it; the
    source file comes from ``.diarykg/config.json``. Accepted, with a note, for
    one minor release.
    """
    out: list[str] = []
    dropped = False
    it = iter(argv)
    for arg in it:
        if arg == "--source":
            next(it, None)
            dropped = True
        elif arg.startswith("--source="):
            dropped = True
        else:
            out.append(arg)
    if dropped:
        print(
            "diarykg-mcp: --source is ignored (read from .diarykg/config.json) "
            "and will be refused after 0.101.x",
            file=sys.stderr,
        )
    return out


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``diarykg-mcp``: the same command as ``diarykg mcp``.

    :param argv: Arguments; ``None`` for ``sys.argv[1:]``.
    """
    from diary_kg.cli import mcp_command  # pylint: disable=import-outside-toplevel

    args = _drop_source(sys.argv[1:] if argv is None else argv)
    mcp_command.main(args=args, prog_name="diarykg-mcp")


if __name__ == "__main__":
    main()

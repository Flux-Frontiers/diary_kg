"""tests/test_mcp_server.py

The DiaryKG MCP server on the fleet's shared base, ``kg_utils.mcp``, and the
DiaryKG surface it serves.

Import-level regression tests first: the server's import of ``mcp`` breaks at
import time, not call time, when an incompatible ``mcp`` release is installed
(mcp 2.0 removed ``mcp.server.fastmcp``), and only for people installing from
PyPI.

Then what step 3 of kgrag_priv's MCP centralization plan promises: the five
canonical tools under the same names as every fleet server; ``stats``,
``query`` and ``pack`` keep DiaryKG's own answers; ``get_node`` works on a
diary; ``stats``, ``get_node`` and ``neighbors`` never load the model; the
manifest answers without a graph; ``diarykg``'s other commands do not import
``mcp``; a project with no graph is refused; and a real stdio subprocess serves.

The diary is built through DocKG with a deterministic keyword embedder, then
enriched by DiaryKG exactly as ``build()`` does, so no model is downloaded.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from click.testing import CliRunner
from kg_utils.mcp import CANONICAL_TOOLS, manifest
from kg_utils.stats import stats_problems
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

import diary_kg
from diary_kg.cli import cli
from diary_kg.kg import DiaryKG
from diary_kg.mcp_server import _drop_source, build_server

_SRC = str(Path(diary_kg.__file__).resolve().parents[1])

_ENTRIES = {
    "0000_1660-01-01.md": ("1660-01-01T00:00", "health", "Home", "Whales were sighted at sea."),
    "0001_1660-01-02.md": ("1660-01-02T09:00", "work", "Office", "To the office about the navy."),
    "0002_1660-01-03.md": ("1660-01-03T20:00", "social", "Home", "Home to supper and so to bed."),
}


class _KeywordEmbedder:
    """One dimension per keyword, plus a constant so no vector is zero."""

    _words = ("whale", "office", "navy", "supper", "bed")
    dim = len(_words) + 1
    model_name = "keyword-test"

    def embed_texts(self, texts, encode_batch_size: int = 128):
        return [[float(w in t.lower()) for w in self._words] + [0.01] for t in texts]

    def embed_query(self, query: str):
        return self.embed_texts([query])[0]


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr("doc_kg.kg.make_embedder", lambda *_a, **_k: _KeywordEmbedder())


@pytest.fixture
def diary(tmp_path: Path, fake_model) -> Path:
    """A built, enriched three-entry diary under ``<root>/.diarykg``."""
    from doc_kg import DocKG  # noqa: PLC0415

    root = tmp_path / "project"
    kg_dir = root / ".diarykg"
    corpus = kg_dir / "corpus"
    corpus.mkdir(parents=True)
    for name, (ts, cat, ctx, text) in _ENTRIES.items():
        corpus.joinpath(name).write_text(
            f"---\ntimestamp: {ts}\ncategory: {cat}\ncontext: {ctx}\n"
            f"source_file: pepys.txt\n---\n\n{text}\n",
            encoding="utf-8",
        )
    (kg_dir / "config.json").write_text(json.dumps({"source_file": "pepys.txt"}))
    dockg = DocKG(
        corpus,
        kg_dir / "graph.sqlite",
        kg_dir / "vectors.sqlite",
        chunk_strategy="fixed",
        enable_topics=False,
        enable_entities=False,
        enable_keywords=False,
    )
    dockg.build(wipe=True, discover_similar=False)
    dockg.close()
    assert DiaryKG(root)._enrich_metadata() == len(_ENTRIES)
    return root


def _session(server, fn):
    async def main():
        async with create_connected_server_and_client_session(server) as client:
            return await fn(client)

    return anyio.run(main)


def _refuse_model(monkeypatch):
    def refuse(*_a, **_k):
        raise RuntimeError("embedding model load refused by test")

    monkeypatch.setattr("doc_kg.kg.make_embedder", refuse)


# ---------------------------------------------------------------------------
# Import level
# ---------------------------------------------------------------------------


def test_server_module_imports():
    """The module must import cleanly against the installed mcp release."""
    importlib.import_module("diary_kg.mcp_server")


def test_fastmcp_import_path_exists():
    """``mcp.server.fastmcp`` must exist -- mcp 2.0 removed it."""
    importlib.import_module("mcp.server.fastmcp")


def test_entry_point_target_exists():
    """``diarykg-mcp`` resolves to diary_kg.mcp_server:main."""
    assert callable(importlib.import_module("diary_kg.mcp_server").main)


# ---------------------------------------------------------------------------
# DiaryKG's canonical surface
# ---------------------------------------------------------------------------


def test_hop_zero_is_the_seed_list(diary):
    kg = DiaryKG(diary)
    hits = kg.query("whale", k=2)
    assert hits[0]["source_file"] == "pepys.txt"
    assert hits[0]["timestamp"] == "1660-01-01T00:00"
    assert all(h["hop"] == 0 and h["via_seed"] == h["node_id"] for h in hits)
    kg.close()


def test_hop_brings_the_neighbourhood_after_every_seed(diary):
    kg = DiaryKG(diary)
    seeds = kg.query("whale", k=1)
    hits = kg.query("whale", k=1, hop=1)
    assert hits[: len(seeds)] == seeds
    later = hits[len(seeds) :]
    assert later and all(h["hop"] == 1 and h["via_seed"] == seeds[0]["node_id"] for h in later)
    assert all(h["score"] <= seeds[0]["score"] for h in later)
    assert len(kg.query("whale", k=1, hop=1, max_nodes=1)) == 1
    assert kg.query("whale", k=1, hop=1, rels=["NO_SUCH_REL"]) == seeds
    kg.close()


@pytest.mark.parametrize(("kwargs", "name"), [({"hop": 6}, "hop"), ({"max_nodes": 0}, "max_nodes")])
def test_out_of_range_arguments_name_the_parameter(diary, kwargs, name):
    kg = DiaryKG(diary)
    with pytest.raises(ValueError, match=name):
        kg.pack("whale", **kwargs)
    kg.close()


def test_node_and_neighbors_read_the_graph_only(diary, monkeypatch):
    _refuse_model(monkeypatch)
    kg = DiaryKG(diary)
    chunk = next(n for n in kg._load_dockg().store.query_nodes(kinds=["chunk"]))["id"]
    assert kg.node(chunk)["id"] == chunk
    assert kg.node("nope") is None
    near = kg.neighbors(chunk, direction="in")
    assert near["edges"] and all(e["dst"] == chunk for e in near["edges"])
    assert kg.neighbors("nope") is None
    kg.close()


def test_explicit_paths_are_honoured(tmp_path):
    kg = DiaryKG(tmp_path, db_path=tmp_path / "g.sqlite", vectors_path=tmp_path / "v.sqlite")
    assert (kg.db_path, kg.vectors_path) == (tmp_path / "g.sqlite", tmp_path / "v.sqlite")
    assert kg.repo_root == tmp_path.resolve()


# ---------------------------------------------------------------------------
# The tool surface, through a real MCP client
# ---------------------------------------------------------------------------


def test_exactly_the_canonical_tools(tmp_path):
    assert [t["name"] for t in manifest(build_server(tmp_path))["tools"]] == list(CANONICAL_TOOLS)


def test_graph_tools_answer_without_a_model(diary, monkeypatch):
    _refuse_model(monkeypatch)
    chunk = "chunk:0000_1660-01-01.md:0000"

    async def calls(client: ClientSession):
        return (
            await client.call_tool("stats", {}),
            await client.call_tool("get_node", {"node_id": chunk}),
            await client.call_tool("neighbors", {"node_id": chunk}),
            await client.call_tool("get_node", {"node_id": "nope"}),
            await client.call_tool("query", {"q": "whale"}),
        )

    stats, node, near, missing, query = _session(build_server(diary), calls)
    assert not stats.isError
    assert stats.structuredContent["kind"] == "diary"
    assert stats.structuredContent["temporal_span"]["start"] == "1660-01-01T00:00"
    assert stats.structuredContent["nodes"]["total"] > 0
    assert stats_problems(stats.structuredContent) == []
    assert not node.isError and node.structuredContent["id"] == chunk
    assert not near.isError and near.structuredContent["edges"]
    assert missing.isError and "no node with id 'nope'" in missing.content[0].text
    assert query.isError and "embedding model load refused by test" in query.content[0].text


def test_query_and_pack_through_mcp(diary):
    async def calls(client: ClientSession):
        return (
            await client.call_tool("query", {"q": "whale", "k": 2}),
            await client.call_tool("pack", {"q": "office navy", "k": 1}),
            await client.call_tool("query", {"q": "whale", "k": 1, "hop": 1, "max_nodes": 2}),
        )

    found, packed, expanded = _session(build_server(diary), calls)
    hits = found.structuredContent["hits"]
    assert hits[0]["timestamp"] == "1660-01-01T00:00" and hits[0]["category"] == "health"
    assert "## pepys.txt @ 1660-01-02" in packed.content[0].text
    assert [h["hop"] for h in expanded.structuredContent["hits"]] == [0, 1]


def test_banner_reports_the_store_actually_serving(diary, capsys):
    _session(build_server(diary), lambda c: c.call_tool("stats", {}))
    err = capsys.readouterr().err
    assert "diarykg: serving" in err
    assert f"db      : {diary.resolve() / '.diarykg' / 'graph.sqlite'}" in err
    assert f"vectors : {diary.resolve() / '.diarykg' / 'vectors.sqlite'}" in err


def test_a_project_without_a_graph_is_refused_not_served_empty(tmp_path):
    with pytest.raises(BaseException) as info:  # noqa: PT011 -- ExceptionGroup from the task group
        _session(build_server(tmp_path), lambda c: c.call_tool("stats", {}))
    assert "no graph at" in repr(info.value) or any(
        "no graph at" in str(e) for e in getattr(info.value, "exceptions", ())
    )
    assert not (tmp_path / ".diarykg").exists()


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_manifest_answers_without_a_graph_and_creates_nothing(tmp_path):
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["canonical"] == list(CANONICAL_TOOLS)
    assert not (tmp_path / ".diarykg").exists()


def test_the_old_script_name_is_the_same_command_and_ignores_source(tmp_path):
    via_cli = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"]).output
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "from diary_kg.mcp_server import main; main()",
            "--repo",
            str(tmp_path),
            "--source",
            "pepys.txt",
            "--manifest",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(via_cli) == json.loads(run.stdout)
    assert "--source is ignored" in run.stderr


def test_drop_source_handles_both_spellings():
    assert _drop_source(["--repo", ".", "--source", "x.txt", "--manifest"]) == [
        "--repo",
        ".",
        "--manifest",
    ]
    assert _drop_source(["--source=x.txt", "--repo", "."]) == ["--repo", "."]


def test_sse_is_refused(tmp_path):
    result = CliRunner().invoke(
        cli, ["mcp", "--repo", str(tmp_path), "--transport", "sse", "--manifest"]
    )
    assert result.exit_code == 2


def test_other_commands_do_not_import_mcp():
    out = subprocess.run(
        [sys.executable, "-c", "import sys, diary_kg.cli; print('mcp' in sys.modules)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "False"


def test_stdio_subprocess_serves(diary):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from diary_kg.mcp_server import main; main()", "--repo", str(diary)],
        env={**os.environ, "PYTHONPATH": _SRC},
    )

    async def run():
        with open(diary / "stderr.log", "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as client:
                    init = await client.initialize()
                    tools = await client.list_tools()
                    stats = await client.call_tool("stats", {})
                    return init, tools, stats

    init, tools, stats = anyio.run(run)
    assert (init.serverInfo.name, init.serverInfo.version) == ("diarykg", diary_kg.__version__)
    assert [t.name for t in tools.tools] == list(CANONICAL_TOOLS)
    assert stats.structuredContent["chunk_count"] == len(_ENTRIES)
    err = (diary / "stderr.log").read_text(encoding="utf-8")
    assert "diarykg MCP server starting (stdio)" in err and "diarykg: serving" in err

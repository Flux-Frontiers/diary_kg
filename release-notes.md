# Release Notes -- v0.101.0

> Released: 2026-10-25

Step 3 of the fleet's MCP centralization (kgrag_priv
`docs/MCP_CENTRALIZATION_PLAN.md`, sweep item 93). **Needs kgmodule-utils
0.29.0** (for `kg_utils.mcp`) **and doc-kg 0.29.0** (for `DocKG.neighbors()`,
and because it removed `dockg build --vector-backend`). The floors are
`kgmodule-utils[mcp]>=0.29.0` and `doc-kg>=0.29.0`, and the `[mcp]` extra
replaces the direct `mcp` pin.

### Changed

- **`DiaryKG.stats()` returns the fleet stats shape.** It was
  `{"node_count", "edge_count", "kind"}`, with `"n/a"` counts on failure; it is
  now `{"kind": "diary", "nodes": {"total", "by_kind"}, "edges": {"total",
  "by_rel"}}` (kgrag_priv FLEET_STANDARDS, "KG stats shape"), built from the
  DocKG store by `kg_utils.stats.stats_from_store`, so it carries the per-kind
  and per-relation breakdowns too. A failure, including one loading the DocKG,
  gives empty counts and an `error`. The `stats` MCP tool is the same shape
  plus `info()`'s corpus measures, and passes the server base's shape check;
  the adapter's `stats()`, `analyze()` and `snapshot save` read it. Snapshot
  metrics keep `total_nodes`/`total_edges`.

- **The MCP server is built on `kg_utils.mcp`.** It serves the fleet's five
  canonical tools under the same names as every other KG server: `stats`,
  `query`, `pack`, `get_node` and `neighbors`. `stats`, `query` and `pack` are
  DiaryKG's own: `stats` is the old `diary_stats` (corpus info plus node and
  edge counts), and `query` and `pack` keep the fused dense + BM25 ranking with
  each entry's date and source. `query` now returns `{"query", "hits"}`. The
  server's instructions are generated from the tools' docstrings, and
  `diarykg mcp --manifest` prints the tool list as JSON without opening a
  graph. Each session prints the store it is actually serving to stderr, and a
  project with no graph is refused (`no graph at ...`) rather than served
  empty. Under stdio, stray prints go to stderr instead of corrupting the
  protocol stream.
- **`diarykg mcp` is the MCP command**, with the fleet's standard flags:
  `--repo`, `--db`, `--vectors`, `--model`,
  `--transport stdio|streamable-http`, `--host`, `--port`, `--manifest`. The
  setup guide already pointed configs at it; it now exists. `diarykg-mcp` is
  the same command under its older name. Registering it does not import `mcp`,
  so every other `diarykg` command starts without it.
- `DiaryKG.query()` and `DiaryKG.pack()` take keyword-only `hop`, `max_nodes`
  and `rels`. The default `hop=0` returns exactly the old seed list; `hop` > 0
  appends the graph neighbourhood of those entries, ranked after every seed.
  Every hit carries `hop` and `via_seed`.
- `DiaryKG(..., *, db_path=None, vectors_path=None)`, with read-only
  `repo_root`, `db_path`, `vectors_path` and `model_name` properties.

### Added

- `DiaryKG.node(node_id)` and `DiaryKG.neighbors(node_id, *, rels, direction,
  limit)`, answered by the backing DocKG. Graph only; no model is loaded.

### Fixed

- **`diarykg snapshot show` printed `None` for nodes and edges.** It read
  `node_count`/`edge_count` from the snapshot metrics, which record
  `total_nodes`/`total_edges`.

- The `dockg build` subprocess fallback (in `DiaryKG.build()` and
  `rebuild_index()`) and `diary-transformer`'s build command no longer pass
  `--vector-backend`. doc-kg 0.29.0 removed that flag, so both would exit 2. A
  test now checks every flag the fallback passes against the installed
  `dockg build`.

### Removed

- **MCP tool names `query_diary`, `pack_diary` and `diary_stats`**, with no
  aliases: use `query`, `pack` and `stats`.
- `diarykg-mcp --transport sse`. `diarykg-mcp --source` is ignored with a
  warning (serving reads the source from `.diarykg/config.json`) and will be
  refused after 0.101.x.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

# Release Notes — v0.93.4

> Released: 2026-07-29

A dependency-correctness release. The headline is a hard upper bound on `mcp`: a clean
`pip install diary-kg` could resolve mcp 2.x, which crashes `diarykg-mcp` on import before
it registers a single tool. If your MCP server failed to start with a `ModuleNotFoundError`
on `mcp.server.fastmcp`, upgrading fixes it.

## What changed

**`mcp` bounded below 2.0.** mcp 2.0 split FastMCP out into a standalone `fastmcp` package
and removed the bundled `mcp.server.fastmcp` module. Because `diary_kg/mcp_server.py`
imports `FastMCP` at module scope and registers all three tools with decorators, the
previous unbounded `mcp>=1.0.0` let a fresh install pick up 2.x and fail immediately at
import. Developers never saw it — a pinned lock file keeps every local checkout working,
which is exactly how this reached the index across the KG family before anyone noticed. The
bound stays until the server is ported to the standalone `fastmcp` package.

**Import-level tests so it cannot recur silently.** A new `tests/test_mcp_server.py` builds
the real `FastMCP` instance and checks all three tools register, so an incompatible `mcp`
breaks CI at import time rather than in a user's terminal. One test asserts
`mcp.server.fastmcp` exists directly, so a future break names the actual incompatibility
instead of surfacing as an opaque `ImportError`.

**Housekeeping: `.gitignore` normalized across the KG fleet.** All eleven KG repos now
share one canonical set of ignore rules — databases, vector indexes and model caches are
ignored; `snapshots/` never is.

## Upgrading

Nothing to do beyond upgrading. `pip install --upgrade diary-kg` pulls a compatible `mcp`;
no rebuild, no migration, no API change. If you had pinned `mcp` yourself to work around the
crash, you can drop that pin.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

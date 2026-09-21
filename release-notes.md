# Release Notes -- v0.100.0

> Released: 2026-09-21

DiaryKG's MCP server now closes the corpus database when it shuts down instead
of leaving the handle to process exit. Nothing else changes: no index rebuild,
no migration, no CLI change.

## What changed

**The MCP server closes the graph on shutdown.** `diarykg-mcp` wires an
`asynccontextmanager` into `FastMCP(lifespan=...)`, so the underlying SQLite
connection is released when the server stops. One hook covers both the stdio
and SSE transports, because both route through the same underlying
`Server.run()`.

DiaryKG holds its handle indirectly, through the DocKG it constructs on demand,
so the shutdown path closes that and drops the reference. A later query simply
rebuilds it, which means closing does not end the object's usable life.

This is the resource-cleanup pattern the fleet standardised on, verified here
against a real server run rather than a stubbed `close`.

## Upgrading

Nothing to do. If you run `diarykg-mcp` inside a long-lived process, it now
leaves no database handle behind when it stops.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_

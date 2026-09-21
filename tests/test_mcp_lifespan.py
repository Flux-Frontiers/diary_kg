"""The MCP server's lifespan hook closes the graph's SQLite connection on
shutdown -- the resource-cleanup pattern genealogy_kg set and kgrag_priv's
FLEET_STANDARDS.md records (sweep item 5). FastMCP's ``lifespan=`` fires on
both the stdio and SSE transports, since both route through the same
underlying ``Server.run()``.

Drives the real server through ``mcp.shared.memory``'s in-process transport:
an actual ``Server.run()``/lifespan cycle, not a mock of ``close``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from diary_kg import mcp_server
from diary_kg.kg import DiaryKG

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_lifespan_closes_kg_on_server_shutdown(built_kg_root: Path) -> None:
    # DiaryKG holds its SQLite handle indirectly, through the DocKG it builds
    # on demand; `close()` drops that reference after closing it, so the
    # attribute going back to None is the observable effect of the shutdown.
    # A built root is required -- DiaryKG refuses to open a DocKG without one.
    kg = DiaryKG(built_kg_root)
    kg.stats()  # constructs the DocKG, opening the connection
    assert kg._dockg is not None  # noqa: SLF001
    mcp_server._kg = kg
    try:
        async with create_connected_server_and_client_session(mcp_server.mcp) as session:
            await session.call_tool("diary_stats", {})

        # The server task has fully unwound by the time the block above
        # exits, so the lifespan's `finally: kg.close()` has already run.
        assert kg._dockg is None  # noqa: SLF001 - the lifespan closed and dropped it
    finally:
        mcp_server._kg = None


async def test_lifespan_is_a_noop_when_kg_was_never_set() -> None:
    # main() always sets _kg before mcp.run(), but the lifespan itself
    # must not blow up if it somehow runs first.
    assert mcp_server._kg is None
    async with create_connected_server_and_client_session(mcp_server.mcp):
        pass
    assert mcp_server._kg is None

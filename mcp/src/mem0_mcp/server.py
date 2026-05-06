# pyright: reportMissingImports=false
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from mem0_mcp.client import Mem0Client
from mem0_mcp.config import settings

mcp = FastMCP("mem0-mcp-server")


def _get_request_api_key() -> str:
    """Extract X-API-Key from the incoming HTTP request headers."""
    headers = get_http_headers()
    return headers.get("x-api-key", "")


def _get_request_agent_id() -> str:
    """Extract X-Agent-Id from the incoming HTTP request headers."""
    headers = get_http_headers()
    return headers.get("x-agent-id", "")


def _build_client(api_key: str = "", api_url: str | None = None, agent_id: str = None) -> Mem0Client:
    resolved_key = api_key or settings.MEM0_API_KEY or _get_request_api_key()
    resolved_agent = agent_id or settings.MEM0_AGENT_ID or _get_request_agent_id() or None
    return Mem0Client(
        base_url=api_url or settings.MEM0_API_URL,
        api_key=resolved_key,
        agent_id=resolved_agent,
    )


async def _close_client(client: Mem0Client) -> None:
    await client._client.aclose()  # noqa: SLF001


@mcp.tool(description="Add new memories for a user.")
async def add_memories(
    messages: list[dict[str, Any]],
    user_id: str,
    api_key: str = "",
    api_url: str | None = None,
    agent_id: str = "",
) -> dict[str, Any]:
    """Add memories using Mem0 API POST /memories."""
    client = _build_client(api_key=api_key, api_url=api_url, agent_id=agent_id or None)
    try:
        return await client.add_memories(messages=messages, user_id=user_id)
    finally:
        await _close_client(client)


@mcp.tool(description="Search memories for a user.")
async def search_memory(
    query: str,
    user_id: str,
    api_key: str = "",
    limit: int = 10,
    api_url: str | None = None,
    agent_id: str = "",
) -> dict[str, Any]:
    """Search memories using Mem0 API POST /search."""
    client = _build_client(api_key=api_key, api_url=api_url, agent_id=agent_id or None)
    try:
        return await client.search_memory(query=query, user_id=user_id, limit=limit)
    finally:
        await _close_client(client)


@mcp.tool(description="List all memories for a user.")
async def list_memories(
    user_id: str,
    api_key: str = "",
    api_url: str | None = None,
    agent_id: str = "",
) -> dict[str, Any]:
    """List memories using Mem0 API GET /memories."""
    client = _build_client(api_key=api_key, api_url=api_url, agent_id=agent_id or None)
    try:
        return await client.list_memories(user_id=user_id)
    finally:
        await _close_client(client)


@mcp.tool(description="Get one memory by ID.")
async def get_memory(
    memory_id: str,
    user_id: str,
    api_key: str = "",
    api_url: str | None = None,
) -> dict[str, Any]:
    """Get memory using Mem0 API GET /memories/{memory_id}."""
    _ = user_id
    client = _build_client(api_key=api_key, api_url=api_url)
    try:
        return await client.get_memory(memory_id=memory_id)
    finally:
        await _close_client(client)


@mcp.tool(description="Delete one memory by ID.")
async def delete_memory(
    memory_id: str,
    user_id: str,
    api_key: str = "",
    api_url: str | None = None,
) -> dict[str, Any]:
    """Delete memory using Mem0 API DELETE /memories/{memory_id}."""
    _ = user_id
    client = _build_client(api_key=api_key, api_url=api_url)
    try:
        return await client.delete_memory(memory_id=memory_id)
    finally:
        await _close_client(client)
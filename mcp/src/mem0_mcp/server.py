# pyright: reportMissingImports=false
import time
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.requests import Request
from starlette.responses import JSONResponse

from mem0_mcp.client import Mem0Client
from mem0_mcp.config import settings

_user_id_cache: dict[str, tuple[str, float]] = {}

mcp = FastMCP("mem0-mcp-server")


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Kubernetes readiness/liveness probe endpoint."""
    return JSONResponse({"status": "ok"})


def _get_request_api_key() -> str:
    """Extract X-API-Key from the incoming HTTP request headers."""
    headers = get_http_headers()
    return headers.get("x-api-key", "")


def _get_request_agent_id() -> str:
    """Extract X-Agent-Id from the incoming HTTP request headers."""
    headers = get_http_headers()
    return headers.get("x-agent-id", "")


def _get_request_user_id() -> str:
    """Extract X-User-Id from the incoming HTTP request headers."""
    headers = get_http_headers()
    return headers.get("x-user-id", "")


async def _resolve_user_id_from_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    cached = _user_id_cache.get(api_key)
    if cached and time.time() - cached[1] < settings.MEM0_USER_CACHE_TTL:
        return cached[0]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.MEM0_API_URL}/auth/me",
                headers={"X-API-Key": api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            user_id = str(response.json()["id"])
            _user_id_cache[api_key] = (user_id, time.time())
            return user_id
    except Exception:
        return ""


async def _resolve_user_id(user_id: str = "", api_key: str = "") -> str:
    return user_id or settings.MEM0_USER_ID or _get_request_user_id() or await _resolve_user_id_from_api_key(api_key)


def _build_client(api_key: str = "", api_url: str | None = None, agent_id: str | None = None) -> Mem0Client:
    resolved_key = api_key or settings.MEM0_API_KEY or _get_request_api_key()
    resolved_agent = agent_id or settings.MEM0_AGENT_ID or _get_request_agent_id() or ""
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
    user_id: str = "",
    api_key: str = "",
    api_url: str | None = None,
    agent_id: str = "",
) -> dict[str, Any]:
    """Add memories using Mem0 API POST /memories."""
    resolved_key = api_key or settings.MEM0_API_KEY or _get_request_api_key()
    resolved_user_id = await _resolve_user_id(user_id, api_key=resolved_key)
    client = _build_client(api_key=api_key, api_url=api_url, agent_id=agent_id or None)
    try:
        return await client.add_memories(messages=messages, user_id=resolved_user_id)
    finally:
        await _close_client(client)


@mcp.tool(description="Search memories for a user.")
async def search_memory(
    query: str,
    user_id: str = "",
    api_key: str = "",
    limit: int = 10,
    api_url: str | None = None,
    agent_id: str = "",
) -> dict[str, Any]:
    """Search memories using Mem0 API POST /search."""
    resolved_key = api_key or settings.MEM0_API_KEY or _get_request_api_key()
    resolved_user_id = await _resolve_user_id(user_id, api_key=resolved_key)
    client = _build_client(api_key=api_key, api_url=api_url, agent_id=agent_id or None)
    try:
        return await client.search_memory(query=query, user_id=resolved_user_id, limit=limit)
    finally:
        await _close_client(client)


@mcp.tool(description="List all memories for a user.")
async def list_memories(
    user_id: str = "",
    api_key: str = "",
    api_url: str | None = None,
    agent_id: str = "",
) -> dict[str, Any]:
    """List memories using Mem0 API GET /memories."""
    resolved_key = api_key or settings.MEM0_API_KEY or _get_request_api_key()
    resolved_user_id = await _resolve_user_id(user_id, api_key=resolved_key)
    client = _build_client(api_key=api_key, api_url=api_url, agent_id=agent_id or None)
    try:
        return await client.list_memories(user_id=resolved_user_id)
    finally:
        await _close_client(client)


@mcp.tool(description="Get one memory by ID.")
async def get_memory(
    memory_id: str,
    user_id: str = "",
    api_key: str = "",
    api_url: str | None = None,
) -> dict[str, Any]:
    """Get memory using Mem0 API GET /memories/{memory_id}."""
    client = _build_client(api_key=api_key, api_url=api_url)
    try:
        return await client.get_memory(memory_id=memory_id)
    finally:
        await _close_client(client)


@mcp.tool(description="Delete one memory by ID.")
async def delete_memory(
    memory_id: str,
    user_id: str = "",
    api_key: str = "",
    api_url: str | None = None,
) -> dict[str, Any]:
    """Delete memory using Mem0 API DELETE /memories/{memory_id}."""
    client = _build_client(api_key=api_key, api_url=api_url)
    try:
        return await client.delete_memory(memory_id=memory_id)
    finally:
        await _close_client(client)

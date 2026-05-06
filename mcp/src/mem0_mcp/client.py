from typing import Any

import httpx

from mem0_mcp.config import settings


class Mem0Client:
    def __init__(self, base_url: str = None, api_key: str = None, agent_id: str = None):
        base_url = base_url or settings.MEM0_API_URL
        api_key = api_key or settings.MEM0_API_KEY
        self._agent_id = agent_id or settings.MEM0_AGENT_ID or None
        self._client = httpx.AsyncClient(base_url=base_url, headers={"X-API-Key": api_key})

    def _resolve_agent_id(self, agent_id: str = None) -> str:
        """Resolve agent_id: per-call > config."""
        return agent_id or self._agent_id

    async def add_memories(self, messages: list, user_id: str, agent_id: str = None, **kwargs: Any) -> dict:
        payload = {"messages": messages, "user_id": user_id, **kwargs}
        resolved_agent_id = self._resolve_agent_id(agent_id)
        if resolved_agent_id:
            payload["agent_id"] = resolved_agent_id
        response = await self._client.post("/memories", json=payload)
        response.raise_for_status()
        return response.json()

    async def search_memory(self, query: str, user_id: str, agent_id: str = None, limit: int = 10, **kwargs: Any) -> dict:
        payload = {"query": query, "user_id": user_id, "limit": limit, **kwargs}
        resolved_agent_id = self._resolve_agent_id(agent_id)
        if resolved_agent_id:
            payload["agent_id"] = resolved_agent_id
        response = await self._client.post("/search", json=payload)
        response.raise_for_status()
        return response.json()

    async def list_memories(self, user_id: str, agent_id: str = None, **kwargs: Any) -> dict:
        params = {"user_id": user_id, **kwargs}
        resolved_agent_id = self._resolve_agent_id(agent_id)
        if resolved_agent_id:
            params["agent_id"] = resolved_agent_id
        response = await self._client.get("/memories", params=params)
        response.raise_for_status()
        return response.json()

    async def get_memory(self, memory_id: str) -> dict:
        response = await self._client.get(f"/memories/{memory_id}")
        response.raise_for_status()
        return response.json()

    async def delete_memory(self, memory_id: str) -> dict:
        response = await self._client.delete(f"/memories/{memory_id}")
        response.raise_for_status()
        return response.json()
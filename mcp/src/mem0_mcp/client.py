from typing import Any

import httpx


class Mem0Client:
    def __init__(self, base_url: str, api_key: str):
        self._client = httpx.AsyncClient(base_url=base_url, headers={"X-API-Key": api_key})

    async def add_memories(self, messages: list, user_id: str, **kwargs: Any) -> dict:
        response = await self._client.post("/memories", json={"messages": messages, "user_id": user_id, **kwargs})
        response.raise_for_status()
        return response.json()

    async def search_memory(self, query: str, user_id: str, limit: int = 10, **kwargs: Any) -> dict:
        response = await self._client.post(
            "/search",
            json={"query": query, "user_id": user_id, "limit": limit, **kwargs},
        )
        response.raise_for_status()
        return response.json()

    async def list_memories(self, user_id: str, **kwargs: Any) -> dict:
        response = await self._client.get("/memories", params={"user_id": user_id, **kwargs})
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

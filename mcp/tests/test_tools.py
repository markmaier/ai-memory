# pyright: reportMissingImports=false
import json

import httpx
import pytest
import respx

from mem0_mcp.server import add_memories, delete_memory, get_memory, list_memories, search_memory


@pytest.mark.asyncio
@respx.mock
async def test_add_memories_happy_path(api_url: str, api_key: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"results": [{"id": "1"}]}))

    result = await add_memories(
        messages=[{"role": "user", "content": "remember this"}],
        user_id="u1",
        api_key=api_key,
        api_url=api_url,
    )

    assert result == {"results": [{"id": "1"}]}
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_add_memories_sends_expected_payload_and_api_key(api_url: str, api_key: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    await add_memories(
        messages=[{"role": "user", "content": "hello"}],
        user_id="user-123",
        api_key=api_key,
        api_url=api_url,
    )

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == api_key
    assert json.loads(request.content.decode()) == {
        "messages": [{"role": "user", "content": "hello"}],
        "user_id": "user-123",
    }


@pytest.mark.asyncio
@respx.mock
async def test_search_memory_happy_path(api_url: str, api_key: str):
    route = respx.post(f"{api_url}/search").mock(return_value=httpx.Response(200, json={"results": []}))

    result = await search_memory(
        query="what do I like?",
        user_id="u1",
        api_key=api_key,
        limit=7,
        api_url=api_url,
    )

    request = route.calls.last.request
    assert json.loads(request.content.decode()) == {"query": "what do I like?", "user_id": "u1", "limit": 7}
    assert result == {"results": []}


@pytest.mark.asyncio
@respx.mock
async def test_list_memories_happy_path(api_url: str, api_key: str):
    route = respx.get(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"results": [{"id": "a"}]}))

    result = await list_memories(user_id="u9", api_key=api_key, api_url=api_url)

    request = route.calls.last.request
    assert request.url.params["user_id"] == "u9"
    assert result == {"results": [{"id": "a"}]}


@pytest.mark.asyncio
@respx.mock
async def test_get_memory_happy_path(api_url: str, api_key: str):
    route = respx.get(f"{api_url}/memories/m-1").mock(return_value=httpx.Response(200, json={"id": "m-1"}))

    result = await get_memory(memory_id="m-1", user_id="u1", api_key=api_key, api_url=api_url)

    assert route.called
    assert result == {"id": "m-1"}


@pytest.mark.asyncio
@respx.mock
async def test_delete_memory_happy_path(api_url: str, api_key: str):
    route = respx.delete(f"{api_url}/memories/m-2").mock(
        return_value=httpx.Response(200, json={"message": "Memory deleted successfully"})
    )

    result = await delete_memory(memory_id="m-2", user_id="u1", api_key=api_key, api_url=api_url)

    assert route.called
    assert result == {"message": "Memory deleted successfully"}


@pytest.mark.asyncio
@respx.mock
async def test_search_memory_propagates_401(api_url: str, api_key: str):
    respx.post(f"{api_url}/search").mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await search_memory(query="q", user_id="u1", api_key=api_key, api_url=api_url)

    assert exc_info.value.response.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_get_memory_propagates_401(api_url: str, api_key: str):
    respx.get(f"{api_url}/memories/m-401").mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await get_memory(memory_id="m-401", user_id="u1", api_key=api_key, api_url=api_url)

    assert exc_info.value.response.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_add_memories_propagates_500(api_url: str, api_key: str):
    respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(500, json={"detail": "server error"}))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await add_memories(messages=[{"role": "user", "content": "x"}], user_id="u1", api_key=api_key, api_url=api_url)

    assert exc_info.value.response.status_code == 500


@pytest.mark.asyncio
@respx.mock
async def test_list_memories_propagates_500(api_url: str, api_key: str):
    respx.get(f"{api_url}/memories").mock(return_value=httpx.Response(500, json={"detail": "server error"}))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await list_memories(user_id="u1", api_key=api_key, api_url=api_url)

    assert exc_info.value.response.status_code == 500


@pytest.mark.asyncio
@respx.mock
async def test_delete_memory_propagates_500(api_url: str, api_key: str):
    respx.delete(f"{api_url}/memories/m-500").mock(return_value=httpx.Response(500, json={"detail": "server error"}))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await delete_memory(memory_id="m-500", user_id="u1", api_key=api_key, api_url=api_url)

    assert exc_info.value.response.status_code == 500


@pytest.mark.asyncio
@respx.mock
async def test_get_memory_includes_api_key_header(api_url: str, api_key: str):
    route = respx.get(f"{api_url}/memories/header-check").mock(return_value=httpx.Response(200, json={"id": "header-check"}))

    await get_memory(memory_id="header-check", user_id="u1", api_key=api_key, api_url=api_url)

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == api_key

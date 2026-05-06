# pyright: reportMissingImports=false
import json
from unittest.mock import patch

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


# --- X-API-Key header passthrough tests ---


@pytest.mark.asyncio
@respx.mock
async def test_add_memories_uses_request_header_when_no_env_key(api_url: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": "from-header"}
    ):
        mock_settings.MEM0_API_KEY = ""
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            user_id="u1",
            api_key="",
            api_url=api_url,
        )

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "from-header"


@pytest.mark.asyncio
@respx.mock
async def test_search_memory_uses_request_header_when_no_env_key(api_url: str):
    route = respx.post(f"{api_url}/search").mock(return_value=httpx.Response(200, json={"results": []}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": "header-key"}
    ):
        mock_settings.MEM0_API_KEY = ""
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await search_memory(query="test", user_id="u1", api_key="", api_url=api_url)

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "header-key"


@pytest.mark.asyncio
@respx.mock
async def test_env_key_takes_precedence_over_request_header(api_url: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": "from-header"}
    ):
        mock_settings.MEM0_API_KEY = "env-key"
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            user_id="u1",
            api_key="",
            api_url=api_url,
        )

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "env-key"


@pytest.mark.asyncio
@respx.mock
async def test_explicit_api_key_takes_precedence_over_all(api_url: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": "from-header"}
    ):
        mock_settings.MEM0_API_KEY = "env-key"
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            user_id="u1",
            api_key="explicit-key",
            api_url=api_url,
        )

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "explicit-key"


@pytest.mark.asyncio
@respx.mock
async def test_empty_key_when_no_env_and_no_header(api_url: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={}
    ):
        mock_settings.MEM0_API_KEY = ""
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            user_id="u1",
            api_key="",
            api_url=api_url,
        )

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_list_memories_uses_request_header_when_no_env_key(api_url: str):
    route = respx.get(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"results": []}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": "list-header-key"}
    ):
        mock_settings.MEM0_API_KEY = ""
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await list_memories(user_id="u1", api_key="", api_url=api_url)

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "list-header-key"


@pytest.mark.asyncio
@respx.mock
async def test_delete_memory_uses_request_header_when_no_env_key(api_url: str):
    route = respx.delete(f"{api_url}/memories/m-del").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": "del-header-key"}
    ):
        mock_settings.MEM0_API_KEY = ""
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await delete_memory(memory_id="m-del", user_id="u1", api_key="", api_url=api_url)

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "del-header-key"


@pytest.mark.asyncio
@respx.mock
async def test_get_memory_uses_request_header_when_no_env_key(api_url: str):
    route = respx.get(f"{api_url}/memories/m-get").mock(return_value=httpx.Response(200, json={"id": "m-get"}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": "get-header-key"}
    ):
        mock_settings.MEM0_API_KEY = ""
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""

        await get_memory(memory_id="m-get", user_id="u1", api_key="", api_url=api_url)

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "get-header-key"

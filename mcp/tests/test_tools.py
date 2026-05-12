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


# --- X-User-Id header passthrough tests ---


@pytest.mark.asyncio
@respx.mock
async def test_add_memories_uses_request_user_id_header(api_url: str, api_key: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key, "x-user-id": "header-user"}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            api_key=api_key,
            api_url=api_url,
        )

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "header-user"


@pytest.mark.asyncio
@respx.mock
async def test_env_user_id_takes_precedence_over_header(api_url: str, api_key: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key, "x-user-id": "header-user"}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = "env-user"

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            api_key=api_key,
            api_url=api_url,
        )

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "env-user"


@pytest.mark.asyncio
@respx.mock
async def test_explicit_user_id_takes_precedence_over_all(api_url: str, api_key: str):
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key, "x-user-id": "header-user"}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = "env-user"

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            user_id="explicit-user",
            api_key=api_key,
            api_url=api_url,
        )

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "explicit-user"


@pytest.mark.asyncio
@respx.mock
async def test_search_memory_uses_request_user_id_header(api_url: str, api_key: str):
    route = respx.post(f"{api_url}/search").mock(return_value=httpx.Response(200, json={"results": []}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key, "x-user-id": "search-header-user"}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""

        await search_memory(query="test", api_key=api_key, api_url=api_url)

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "search-header-user"


@pytest.mark.asyncio
@respx.mock
async def test_list_memories_uses_request_user_id_header(api_url: str, api_key: str):
    route = respx.get(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"results": []}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key, "x-user-id": "list-header-user"}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""

        await list_memories(api_key=api_key, api_url=api_url)

    request = route.calls.last.request
    assert request.url.params["user_id"] == "list-header-user"


# --- user_id auto-resolution from /auth/me tests ---


@pytest.mark.asyncio
@respx.mock
async def test_add_memories_resolves_user_id_from_me_endpoint(api_url: str, api_key: str):
    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    respx.get(f"{api_url}/auth/me").mock(
        return_value=httpx.Response(200, json={"id": "uuid-from-me", "name": "Test", "email": "t@t.com", "role": "admin"})
    )
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""
        mock_settings.MEM0_USER_CACHE_TTL = 300

        await add_memories(messages=[{"role": "user", "content": "hi"}], api_key=api_key, api_url=api_url)

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "uuid-from-me"


@pytest.mark.asyncio
@respx.mock
async def test_user_id_cache_prevents_duplicate_me_calls(api_url: str, api_key: str):
    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    me_route = respx.get(f"{api_url}/auth/me").mock(
        return_value=httpx.Response(200, json={"id": "uuid-cached", "name": "T", "email": "t@t.com", "role": "admin"})
    )
    respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""
        mock_settings.MEM0_USER_CACHE_TTL = 300

        await add_memories(messages=[{"role": "user", "content": "first"}], api_key=api_key, api_url=api_url)
        await add_memories(messages=[{"role": "user", "content": "second"}], api_key=api_key, api_url=api_url)

    assert me_route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_user_id_cache_expires_after_ttl(api_url: str, api_key: str):
    import time as time_module

    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    me_route = respx.get(f"{api_url}/auth/me").mock(
        return_value=httpx.Response(200, json={"id": "uuid-v1", "name": "T", "email": "t@t.com", "role": "admin"})
    )
    respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""
        mock_settings.MEM0_USER_CACHE_TTL = 1

        await add_memories(messages=[{"role": "user", "content": "first"}], api_key=api_key, api_url=api_url)
        assert me_route.call_count == 1

        # Expire the cache by patching time.time in the server module
        with patch("mem0_mcp.server.time") as mock_time:
            mock_time.time.return_value = time_module.time() + 2
            await add_memories(messages=[{"role": "user", "content": "second"}], api_key=api_key, api_url=api_url)

    assert me_route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_me_endpoint_failure_returns_empty_user_id(api_url: str, api_key: str):
    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    respx.get(f"{api_url}/auth/me").mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""
        mock_settings.MEM0_USER_CACHE_TTL = 300

        await add_memories(messages=[{"role": "user", "content": "hi"}], api_key=api_key, api_url=api_url)

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_me_endpoint_network_error_returns_empty_user_id(api_url: str, api_key: str):
    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    respx.get(f"{api_url}/auth/me").mock(side_effect=httpx.ConnectError("connection refused"))
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""
        mock_settings.MEM0_USER_CACHE_TTL = 300

        await add_memories(messages=[{"role": "user", "content": "hi"}], api_key=api_key, api_url=api_url)

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_explicit_user_id_takes_precedence_over_me_resolution(api_url: str, api_key: str):
    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    me_route = respx.get(f"{api_url}/auth/me").mock(
        return_value=httpx.Response(200, json={"id": "uuid-from-me", "name": "T", "email": "t@t.com", "role": "admin"})
    )
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""
        mock_settings.MEM0_USER_CACHE_TTL = 300

        await add_memories(
            messages=[{"role": "user", "content": "hi"}],
            user_id="explicit-user",
            api_key=api_key,
            api_url=api_url,
        )

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "explicit-user"
    assert me_route.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_env_user_id_takes_precedence_over_me_resolution(api_url: str, api_key: str):
    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    me_route = respx.get(f"{api_url}/auth/me").mock(
        return_value=httpx.Response(200, json={"id": "uuid-from-me", "name": "T", "email": "t@t.com", "role": "admin"})
    )
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = "env-user"
        mock_settings.MEM0_USER_CACHE_TTL = 300

        await add_memories(messages=[{"role": "user", "content": "hi"}], api_key=api_key, api_url=api_url)

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "env-user"
    assert me_route.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_header_user_id_takes_precedence_over_me_resolution(api_url: str, api_key: str):
    from mem0_mcp.server import _user_id_cache

    _user_id_cache.clear()
    me_route = respx.get(f"{api_url}/auth/me").mock(
        return_value=httpx.Response(200, json={"id": "uuid-from-me", "name": "T", "email": "t@t.com", "role": "admin"})
    )
    route = respx.post(f"{api_url}/memories").mock(return_value=httpx.Response(200, json={"ok": True}))

    with patch("mem0_mcp.server.settings") as mock_settings, patch(
        "mem0_mcp.server.get_http_headers", return_value={"x-api-key": api_key, "x-user-id": "header-user"}
    ):
        mock_settings.MEM0_API_KEY = api_key
        mock_settings.MEM0_API_URL = api_url
        mock_settings.MEM0_AGENT_ID = ""
        mock_settings.MEM0_USER_ID = ""
        mock_settings.MEM0_USER_CACHE_TTL = 300

        await add_memories(messages=[{"role": "user", "content": "hi"}], api_key=api_key, api_url=api_url)

    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["user_id"] == "header-user"
    assert me_route.call_count == 0

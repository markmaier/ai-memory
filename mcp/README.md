# mem0-mcp-server

Scaffold for the Mem0 MCP server.

## Environment

- `MEM0_API_URL` — Mem0 API base URL (`http://localhost:8000` by default)
- `MEM0_API_KEY` — (optional) default API key passed through to Mem0. When unset, the server forwards the `X-API-Key` header from the incoming HTTP request to the Mem0 API.
- `MEM0_AGENT_ID` — (optional) custom agent ID sent as `X-Agent-Id` header
- `MEM0_USER_ID` — (optional) default user ID for all tool calls. When unset, the server reads the `X-User-Id` header from the incoming HTTP request.
- `MEM0_USER_CACHE_TTL` — (optional) TTL in seconds for the API-key-to-user-id cache (default: 300)
- `MCP_HOST` — bind host (`0.0.0.0` by default)
- `MCP_PORT` — bind port (`8080` by default)

## Authentication

The MCP server authenticates with the Mem0 API server using the `X-API-Key` header. The key is resolved in priority order:

1. `api_key` parameter passed per tool call
2. `MEM0_API_KEY` environment variable
3. `X-API-Key` header from the incoming HTTP request (passthrough)

This allows deployments where each MCP client provides its own API key without configuring a shared secret on the MCP server.

## User Identity

The `user_id` parameter is optional on every tool. When omitted, it is resolved in priority order:

1. `user_id` parameter passed per tool call
2. `MEM0_USER_ID` environment variable
3. `X-User-Id` header from the incoming HTTP request (passthrough)
4. `id` from `GET /auth/me` response — automatic fallback using the resolved API key (result cached for `MEM0_USER_CACHE_TTL` seconds)

This allows MCP clients to set their user identity once via headers instead of passing `user_id` on every call.

## Local setup

```bash
cd mcp
pip install -e ".[dev]"
python -c "from mem0_mcp.config import settings; print(settings.MEM0_API_URL)"
```

## Docker

```bash
cd mcp
docker build -t mem0-mcp-server .
```

## MCP client connection

This service is intended to expose streamable HTTP MCP endpoints in a later task. Point your MCP client at the service URL once tools are added.

# OpenMemory HOWTO

> **⚠️ Sunsetting Notice:** OpenMemory is being sunset. For local self-hosted memory with a dashboard, please use the [Mem0 self-hosted server](https://docs.mem0.ai/open-source/overview) instead. Get started with `cd server && make bootstrap`. See the [self-hosted docs](https://docs.mem0.ai/open-source/setup) for configuration details.

## Table of Contents

- [Quick-Start (Local Setup)](#quick-start-local-setup)
  - [Prerequisites](#prerequisites)
  - [1. Clone and navigate](#1-clone-and-navigate)
  - [2. Configure environment](#2-configure-environment)
  - [3. Start services](#3-start-services)
  - [4. Verify](#4-verify)
- [Personal Memory Configuration](#personal-memory-configuration)
  - [Understanding user_id](#understanding-user_id)
  - [LLM Provider Configuration](#llm-provider-configuration)
  - [Embedder Configuration](#embedder-configuration)
  - [Settings UI](#settings-ui)
  - [Verification](#verification)
- [Team Deployment (Kubernetes)](#team-deployment-kubernetes)
- [Multi-User Access (OIDC)](#multi-user-access-oidc)
- [Shared Team/Project Memory](#shared-teamproject-memory)
- [MCP Client Setup](#mcp-client-setup)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Further Resources](#further-resources)

## Quick-Start (Local Setup)

### Prerequisites

- **Docker** and **Docker Compose** (v2+)
- An **OpenAI API key** — or a local Ollama instance if you want fully offline operation
- Git

No Python or Node.js installation required for running the stack. Both are only needed if you're doing active development on the API or UI.

### 1. Clone and navigate

```bash
git clone https://github.com/mem0ai/mem0.git
cd mem0/openmemory
```

### 2. Configure environment

Copy the example files and fill in your values:

```bash
cp api/.env.example api/.env
```

Open `api/.env` and set at minimum:

```env
OPENAI_API_KEY=sk-...        # your OpenAI key
USER=your_name               # becomes your user_id — pick something meaningful
```

The UI reads its config from `docker-compose.yml` via the `USER` env var, so you don't need a separate `ui/.env` for basic local use. If you want to override the API URL (for example, when the UI runs on a different host), create `ui/.env`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8765
NEXT_PUBLIC_USER_ID=your_name   # must match USER in api/.env
```

### 3. Start services

Using the Makefile (recommended):

```bash
make build   # builds the API and UI images
make up      # starts all three services in the background
```

Or directly with Docker Compose:

```bash
docker-compose up -d
```

This starts three services:

| Service | Container | Port |
|---|---|---|
| Qdrant vector store | `mem0_store` | 6333 |
| OpenMemory API + MCP | `openmemory-mcp` | 8765 |
| OpenMemory UI | `openmemory-ui` | 3001 |

### 4. Verify

Check the API is up:

```bash
curl http://localhost:8765/docs
# Should return HTML for the Swagger UI
```

Check the API health directly:

```bash
curl http://localhost:8765/v1/memories/ \
  -H "Content-Type: application/json"
# Should return a JSON list (empty on first run)
```

Open the UI in your browser:

```
http://localhost:3001
```

You should see the OpenMemory dashboard. If the page loads but shows no data, that's expected — you haven't added any memories yet.

## Personal Memory Configuration

### Understanding user_id

Every memory in OpenMemory is scoped to a user. The `USER` variable in `api/.env` sets that identity for your local instance. Whatever value you put there becomes the `user_id` attached to every memory you create, search, or delete.

```env
USER=alice   # all memories belong to "alice"
```

The UI reads this same value via `NEXT_PUBLIC_USER_ID` (injected automatically from `USER` in `docker-compose.yml`), so the dashboard shows only your memories by default.

Keep `USER` consistent across restarts. Changing it doesn't migrate existing memories — they stay under the old user_id in Qdrant.

### LLM Provider Configuration

By default, OpenMemory uses OpenAI's `gpt-4o-mini`. To switch providers, set these variables in `api/.env`:

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | Provider name (`openai`, `ollama`, `anthropic`, `groq`, etc.) | `openai` |
| `LLM_MODEL` | Model name for the chosen provider | `gpt-4o-mini` |
| `LLM_API_KEY` | API key for the provider (falls back to `OPENAI_API_KEY`) | `OPENAI_API_KEY` |
| `LLM_BASE_URL` | Custom base URL for the LLM API | Provider default |
| `OLLAMA_BASE_URL` | Ollama endpoint (takes precedence over `LLM_BASE_URL` for Ollama) | `http://localhost:11434` |

**OpenAI (default)** — no extra config needed beyond `OPENAI_API_KEY`:

```env
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

**Ollama (fully local)** — requires Ollama running on the host. See [ollama.ai](https://ollama.ai) for installation:

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:latest
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Note: use `host.docker.internal` instead of `localhost` when Ollama runs on the host machine and the API runs inside Docker.

**Anthropic:**

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
LLM_API_KEY=sk-ant-...
```

After changing LLM config, restart the API container:

```bash
docker-compose restart openmemory-mcp
```

### Embedder Configuration

Embeddings convert text into vectors for semantic search. The embedder must be compatible with the vectors already stored in Qdrant — changing the embedder after you've added memories will break search until you clear and re-add them.

| Variable | Description | Default |
|---|---|---|
| `EMBEDDER_PROVIDER` | Provider name (`openai`, `ollama`) | `openai` |
| `EMBEDDER_MODEL` | Embedding model name | `text-embedding-3-small` |
| `EMBEDDER_API_KEY` | API key (falls back to `OPENAI_API_KEY`) | `OPENAI_API_KEY` |
| `EMBEDDER_BASE_URL` | Custom base URL for the embedder API | Provider default |

For a fully local setup paired with Ollama:

```env
EMBEDDER_PROVIDER=ollama
EMBEDDER_MODEL=nomic-embed-text
```

For OpenAI (default), no extra config is needed.

### Settings UI

Navigate to `http://localhost:3001/settings` to review your current configuration. The Settings page shows:

- The active user_id (pulled from `NEXT_PUBLIC_USER_ID`)
- The API endpoint the UI is talking to
- Connected MCP clients (if any are configured)

You can't change env vars from the UI — it's read-only. To change config, edit `api/.env` and restart the relevant container.

### Verification

Add a test memory through the UI:

1. Open `http://localhost:3001`
2. Click **Add Memory** (or use the input field on the dashboard)
3. Type something like `I prefer dark mode` and submit

Then confirm it was stored via the API:

```bash
curl "http://localhost:8765/v1/memories/?user_id=your_name"
```

Replace `your_name` with the value you set for `USER`. The response should include the memory you just added.

## Team Deployment (Kubernetes)

Kubernetes lets your team share a single, persistent OpenMemory instance instead of each person running their own. Memories survive pod restarts, and everyone connects to the same Qdrant vector store.

### ⚠️ Database Requirement

**SQLite is not suitable for multi-pod deployments.** The default SQLite database lives on a single pod's local filesystem. When Kubernetes reschedules that pod, or when you run more than one API replica, pods won't share state and you'll get split-brain data.

You must set `DATABASE_URL` to a PostgreSQL connection string before deploying to Kubernetes:

```
DATABASE_URL=postgresql://openmemory:yourpassword@postgres-host:5432/openmemory
```

For production, use a managed database service (AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL). This removes the operational burden of running PostgreSQL yourself and gives you automated backups, failover, and connection pooling.

If you want to run PostgreSQL inside the cluster for development or testing, a basic StatefulSet works — see the example below.

### Architecture Overview

Three services map directly from Docker Compose to Kubernetes:

| Service | Image | Port | Notes |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant` | 6333 | Needs a PersistentVolumeClaim for storage |
| `openmemory-api` | `mem0/openmemory-mcp` | 8765 | Reads env vars from ConfigMap + Secret |
| `openmemory-ui` | `mem0/openmemory-ui:latest` | 3000 (exposed as 3001) | Needs `NEXT_PUBLIC_API_URL` pointing at the API service |

### Example Kubernetes Manifests

> **These are examples only — adapt to your environment.** Adjust resource limits, storage class names, image tags, and ingress configuration for your cluster.

**Namespace**

```yaml
# Example only — adapt to your environment
apiVersion: v1
kind: Namespace
metadata:
  name: openmemory
```

**ConfigMap** (non-sensitive configuration)

```yaml
# Example only — adapt to your environment
apiVersion: v1
kind: ConfigMap
metadata:
  name: openmemory-config
  namespace: openmemory
data:
  USER: "default_user"
  LLM_PROVIDER: "openai"
  LLM_MODEL: "gpt-4o-mini"
  EMBEDDER_PROVIDER: "openai"
  NEXT_PUBLIC_API_URL: "http://openmemory-api:8765"
```

**Secret** (sensitive values — use your secrets manager in production)

```yaml
# Example only — adapt to your environment
apiVersion: v1
kind: Secret
metadata:
  name: openmemory-secrets
  namespace: openmemory
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-..."
  DATABASE_URL: "postgresql://openmemory:yourpassword@postgres-host:5432/openmemory"
  OIDC_ISSUER_URL: ""   # set this to enable OIDC (see Multi-User Access section)
```

**Qdrant PersistentVolumeClaim**

```yaml
# Example only — adapt to your environment
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qdrant-storage
  namespace: openmemory
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

**Qdrant Deployment + Service**

```yaml
# Example only — adapt to your environment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qdrant
  namespace: openmemory
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
        - name: qdrant
          image: qdrant/qdrant
          ports:
            - containerPort: 6333
          volumeMounts:
            - name: storage
              mountPath: /qdrant/storage
      volumes:
        - name: storage
          persistentVolumeClaim:
            claimName: qdrant-storage
---
apiVersion: v1
kind: Service
metadata:
  name: qdrant
  namespace: openmemory
spec:
  selector:
    app: qdrant
  ports:
    - port: 6333
      targetPort: 6333
```

**API Deployment + Service**

```yaml
# Example only — adapt to your environment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openmemory-api
  namespace: openmemory
spec:
  replicas: 1
  selector:
    matchLabels:
      app: openmemory-api
  template:
    metadata:
      labels:
        app: openmemory-api
    spec:
      containers:
        - name: api
          image: mem0/openmemory-mcp:latest
          ports:
            - containerPort: 8765
          envFrom:
            - configMapRef:
                name: openmemory-config
            - secretRef:
                name: openmemory-secrets
          env:
            - name: QDRANT_HOST
              value: "qdrant"
            - name: QDRANT_PORT
              value: "6333"
---
apiVersion: v1
kind: Service
metadata:
  name: openmemory-api
  namespace: openmemory
spec:
  selector:
    app: openmemory-api
  ports:
    - port: 8765
      targetPort: 8765
```

**UI Deployment + Service**

```yaml
# Example only — adapt to your environment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openmemory-ui
  namespace: openmemory
spec:
  replicas: 1
  selector:
    matchLabels:
      app: openmemory-ui
  template:
    metadata:
      labels:
        app: openmemory-ui
    spec:
      containers:
        - name: ui
          image: mem0/openmemory-ui:latest
          ports:
            - containerPort: 3000
          env:
            - name: NEXT_PUBLIC_API_URL
              valueFrom:
                configMapKeyRef:
                  name: openmemory-config
                  key: NEXT_PUBLIC_API_URL
            - name: NEXT_PUBLIC_USER_ID
              valueFrom:
                configMapKeyRef:
                  name: openmemory-config
                  key: USER
---
apiVersion: v1
kind: Service
metadata:
  name: openmemory-ui
  namespace: openmemory
spec:
  selector:
    app: openmemory-ui
  ports:
    - port: 3001
      targetPort: 3000
```

### Deploying

```bash
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f qdrant.yaml
kubectl apply -f api.yaml
kubectl apply -f ui.yaml
```

Check that pods come up:

```bash
kubectl get pods -n openmemory
```

### Verification

Forward the API port locally and confirm the server responds:

```bash
kubectl port-forward svc/openmemory-api 8765:8765 -n openmemory
curl http://localhost:8765/docs
```

You should see the FastAPI interactive docs page. To verify the UI:

```bash
kubectl port-forward svc/openmemory-ui 3001:3001 -n openmemory
# then open http://localhost:3001 in your browser
```

## Multi-User Access (OIDC)

By default, OpenMemory uses a single `USER` identity for all requests. OIDC lets each team member authenticate with their own credentials so their memories stay isolated from everyone else's.

### How It Works

When `OIDC_ISSUER_URL` is set, the `/mcp/auth/{client_name}/http` endpoint requires a Bearer token in the `Authorization` header. The server validates the token against the provider's JWKS endpoint, then reads the `preferred_username` claim from the JWT payload. That claim becomes the `user_id` for all memory operations in that session.

Each team member gets their own memory namespace automatically, just by authenticating.

**Important:** The token is validated once at connection time. If the token expires mid-session, the existing SSE connection continues until it closes. The next connection attempt will require a fresh token.

### Configuration

Set these environment variables on the API pod:

```bash
OIDC_ISSUER_URL=https://your-provider.com/realms/your-realm
OIDC_AUDIENCE=your-client-id   # optional — not currently validated, reserved for future use
```

For Keycloak, `OIDC_ISSUER_URL` is the realm URL, for example:
```
https://keycloak.example.com/realms/my-realm
```

For Google, it's:
```
https://accounts.google.com
```

The server fetches JWKS keys from `{OIDC_ISSUER_URL}/protocol/openid-connect/certs` and caches them for 5 minutes. If `OIDC_ISSUER_URL` is empty, the authenticated endpoint returns `503 OAuth not configured`.

### JWT Claim Mapping

| JWT claim | OpenMemory field | Notes |
|---|---|---|
| `preferred_username` | `user_id` | Required. Request fails with 401 if missing. |
| `name` | display name | Optional, stored if present. |
| `email` | email | Optional, stored if present. |

Your OIDC provider must include `preferred_username` in access tokens. Most providers do by default, but check your token configuration if you see `401 Token missing preferred_username claim`.

### Authenticated MCP URL

Instead of the unauthenticated URL (which embeds the user ID in the path), use:

```
http://your-api-host:8765/mcp/auth/{client_name}/http
```

Your MCP client must send the Bearer token in the `Authorization` header on each connection. The `{client_name}` segment identifies the connecting application (for example `claude`, `cursor`, or `vscode`).

### Supported Providers

Any OIDC-compliant provider works. Setup guides for common ones:

- **Keycloak**: [keycloak.org/docs](https://www.keycloak.org/documentation)
- **Auth0**: [auth0.com/docs](https://auth0.com/docs)
- **Azure AD / Entra ID**: [learn.microsoft.com/azure/active-directory](https://learn.microsoft.com/en-us/azure/active-directory/)
- **Google**: [developers.google.com/identity/openid-connect](https://developers.google.com/identity/openid-connect/openid-connect)

### Security Notes

- Tokens are validated at connection time only. A long-lived SSE session won't re-check the token after the initial handshake.
- The `aud` (audience) claim is not currently validated even when `OIDC_AUDIENCE` is set. The variable is reserved for future use.
- Signature validation uses RS256 via JWKS. The JWKS client caches keys for 300 seconds.
- If `OIDC_ISSUER_URL` is not set, the `/mcp/auth/` endpoint is disabled entirely (returns 503). The unauthenticated endpoints remain available.

## Shared Team/Project Memory

Sometimes you want a pool of memories that the whole team can read and write, separate from anyone's personal memories. OpenMemory doesn't have a built-in sharing model, but you can get this with a simple naming convention.

### The Pattern

Multiple people connect using the **same `user_id`** to share a single memory pool. Because memories are scoped by `user_id`, anyone using the same ID sees the same memories.

### How It Works

Each team member configures **two MCP server connections** in their editor or agent:

1. **Personal connection** — uses their own user ID, memories are private:
   ```
   http://your-api-host:8765/mcp/claude/sse/alice
   ```

2. **Shared connection** — uses a shared team ID, memories are visible to everyone on the team:
   ```
   http://your-api-host:8765/mcp/claude/sse/team-backend
   ```

When the agent adds a memory via the shared connection, it goes into the `team-backend` pool. When it searches via the shared connection, it searches that same pool.

### Setup Steps

1. **Pick a naming convention** for shared IDs. Something like `team-{project}` or `shared-{team}` works well. Keep it consistent across the team.

2. **Each team member adds a second MCP server entry.** In Claude Desktop, for example:

   ```json
   {
     "mcpServers": {
       "openmemory-personal": {
         "url": "http://your-api-host:8765/mcp/claude/sse/alice"
       },
       "openmemory-team": {
         "url": "http://your-api-host:8765/mcp/claude/sse/team-backend"
       }
     }
   }
   ```

3. **Instruct your agent** which connection to use for which purpose. Personal context goes to `openmemory-personal`; shared project knowledge goes to `openmemory-team`.

### Trade-offs

Be honest with your team about what this pattern does and doesn't give you:

| Aspect | Reality |
|---|---|
| Attribution | No. Memories in the shared pool have no record of who added them. |
| Access control | None. Any team member can read, update, or delete any shared memory. |
| Isolation | All-or-nothing. You can't give one person read-only access. |
| Concurrent writes | Safe. Qdrant handles concurrent writes without data corruption. |
| Separation from personal | Clean. Personal and shared memories live under different user IDs and never mix. |

This pattern works well for shared project context, team conventions, or reference knowledge that everyone should be able to search. It's not suitable for sensitive data where you need per-person access control.

## MCP Client Setup

OpenMemory exposes MCP over SSE, so any MCP-compatible client can connect with a single URL. This section covers five clients in detail. For all examples, replace `<your-server>` with your server's hostname or IP address. For local deployments, that's `localhost:8765`.

### URL Patterns

Three URL patterns are available depending on your access model:

| Pattern | URL | When to use |
|---|---|---|
| **Personal (unauthenticated)** | `http://<your-server>:8765/mcp/<client>/sse/<user-id>` | Single user or local dev. No auth required. |
| **Shared team / project** | `http://<your-server>:8765/mcp/<client>/sse/team-<project>` | Multiple people sharing one memory namespace. Use a descriptive project name. |
| **Authenticated (OIDC)** | `http://<your-server>:8765/mcp/auth/<client>/http` | Production deployments with `OIDC_ISSUER_URL` configured. User identity comes from the JWT. |

The `<client>` segment is a label that scopes memories by tool. Use `opencode`, `claude`, `copilot`, `cursor`, or any slug that makes sense for your workflow.

### Quick Install

The `@openmemory/install` package handles config file edits for supported clients automatically:

```bash
npx @openmemory/install local http://<your-server>:8765/mcp/<client>/sse/<user-id> --client <client>
```

Example for a user `alice` connecting Claude Code locally:

```bash
npx @openmemory/install local http://localhost:8765/mcp/claude/sse/alice --client claude
```

Run this once per client. The tool writes the correct config file for you.

---

### OpenCode

**Config file:** `~/.opencode/config.json`

#### Single connection (personal)

```json
{
  "mcpServers": {
    "openmemory": {
      "type": "sse",
      "url": "http://<your-server>:8765/mcp/opencode/sse/<user-id>"
    }
  }
}
```

#### Dual connection (personal + shared team)

Connect two namespaces at once so your personal memories and team memories are both available in every session:

```json
{
  "mcpServers": {
    "openmemory-personal": {
      "type": "sse",
      "url": "http://<your-server>:8765/mcp/opencode/sse/<user-id>"
    },
    "openmemory-team": {
      "type": "sse",
      "url": "http://<your-server>:8765/mcp/opencode/sse/team-<project>"
    }
  }
}
```

#### Authenticated (OIDC)

```json
{
  "mcpServers": {
    "openmemory": {
      "type": "sse",
"url": "http://<your-server>:8765/mcp/auth/opencode/http"
    }
  }
}
```

**Verification:** After saving the config, start a new OpenCode session and ask it to remember something. Then open the OpenMemory UI at `http://<your-server>:3001` and confirm the memory appears.

Or use the quick-install shortcut:

```bash
npx @openmemory/install local http://localhost:8765/mcp/opencode/sse/<user-id> --client opencode
```

---

### Claude Code

**Config file:** `~/.claude/claude_desktop_config.json` (Claude Desktop) or the MCP config for Claude Code CLI.

#### Single connection (personal)

```json
{
  "mcpServers": {
    "openmemory": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://<your-server>:8765/mcp/claude/sse/<user-id>"
      ]
    }
  }
}
```

#### Dual connection (personal + shared team)

```json
{
  "mcpServers": {
    "openmemory-personal": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://<your-server>:8765/mcp/claude/sse/<user-id>"
      ]
    },
    "openmemory-team": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://<your-server>:8765/mcp/claude/sse/team-<project>"
      ]
    }
  }
}
```

#### Authenticated (OIDC)

```json
{
  "mcpServers": {
    "openmemory": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
"http://<your-server>:8765/mcp/auth/claude/http"
      ]
    }
  }
}
```

**Verification:** Restart Claude Desktop (or reload the MCP server in Claude Code CLI). Ask Claude to save a memory, then check the OpenMemory UI at `http://<your-server>:3001`.

Or use the quick-install shortcut:

```bash
npx @openmemory/install local http://localhost:8765/mcp/claude/sse/<user-id> --client claude
```

---

### GitHub Copilot

Add the MCP server to your VS Code `settings.json`:

```json
{
  "github.copilot.chat.mcp.servers": {
    "openmemory": {
      "type": "sse",
      "url": "http://<your-server>:8765/mcp/copilot/sse/<user-id>"
    }
  }
}
```

For a shared team namespace:

```json
{
  "github.copilot.chat.mcp.servers": {
    "openmemory-team": {
      "type": "sse",
      "url": "http://<your-server>:8765/mcp/copilot/sse/team-<project>"
    }
  }
}
```

For authenticated access:

```json
{
  "github.copilot.chat.mcp.servers": {
    "openmemory": {
      "type": "sse",
"url": "http://<your-server>:8765/mcp/auth/copilot/http"
    }
  }
}
```

Or use the quick-install shortcut:

```bash
npx @openmemory/install local http://localhost:8765/mcp/copilot/sse/<user-id> --client copilot
```

---

### IntelliJ

> ⚠️ **IntelliJ MCP support status varies by version** — verify your IDE supports MCP connections before proceeding. Check the JetBrains plugin marketplace or your IDE's AI settings for MCP configuration options.

If your IntelliJ version supports MCP, configure the SSE endpoint in the MCP connection settings:

| Setting | Value |
|---|---|
| Transport | SSE |
| URL (personal) | `http://<your-server>:8765/mcp/intellij/sse/<user-id>` |
| URL (team) | `http://<your-server>:8765/mcp/intellij/sse/team-<project>` |
| URL (authenticated) | `http://<your-server>:8765/mcp/auth/intellij/http` |

Refer to your IDE's documentation for the exact steps to add an MCP server.

---

### Cursor

**Config file:** `.cursor/mcp.json` in your project root, or `~/.cursor/mcp.json` for a global config.

#### Personal connection

```json
{
  "mcpServers": {
    "openmemory": {
      "url": "http://<your-server>:8765/mcp/cursor/sse/<user-id>"
    }
  }
}
```

#### Shared team namespace

```json
{
  "mcpServers": {
    "openmemory-team": {
      "url": "http://<your-server>:8765/mcp/cursor/sse/team-<project>"
    }
  }
}
```

#### Authenticated (OIDC)

```json
{
  "mcpServers": {
    "openmemory": {
"url": "http://<your-server>:8765/mcp/auth/cursor/http"
    }
  }
}
```

Or use the quick-install shortcut:

```bash
npx @openmemory/install local http://localhost:8765/mcp/cursor/sse/<user-id> --client cursor
```

## Configuration Reference

All environment variables are set in `api/.env` (backend) or `ui/.env` (frontend). Copy the example files to get started:

```bash
cp api/.env.example api/.env
```

### Backend Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | — | **Yes** | Primary API key for LLM and embedding calls. |
| `USER` | `default_user` | No | User identifier that scopes all memory operations. |
| `LLM_PROVIDER` | `openai` | No | LLM provider name. Supported values: `openai`, `ollama`, `anthropic`, `groq`, `together`, `deepseek`, and others. |
| `LLM_MODEL` | `gpt-4o-mini` | No | Model name for the selected LLM provider. For Ollama, defaults to `llama3.1:latest`. |
| `LLM_API_KEY` | `OPENAI_API_KEY` | No | API key for the LLM provider. Falls back to `OPENAI_API_KEY` if not set. |
| `LLM_BASE_URL` | Provider default | No | Custom base URL for the LLM API endpoint. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | No | Ollama endpoint. Takes precedence over `LLM_BASE_URL` when using Ollama. |
| `EMBEDDER_PROVIDER` | `openai` | No | Embedding provider name. Supported values: `openai`, `ollama`. |
| `EMBEDDER_MODEL` | `text-embedding-3-small` | No | Embedding model name. For Ollama, defaults to `nomic-embed-text`. |
| `EMBEDDER_API_KEY` | `OPENAI_API_KEY` | No | API key for the embedding provider. Falls back to `OPENAI_API_KEY` if not set. |
| `EMBEDDER_BASE_URL` | Provider default | No | Custom base URL for the embedding API endpoint. |
| `DATABASE_URL` | SQLite (local file) | No | Database connection string. Set to a PostgreSQL URL for multi-pod Kubernetes deployments. |

### OIDC Variables

These variables enable authenticated multi-user access. Leave them empty for single-user local deployments.

| Variable | Default | Required | Description |
|---|---|---|---|
| `OIDC_ISSUER_URL` | `""` | No | OIDC issuer URL (for example `https://keycloak.example.com/realms/my-realm`). Setting this enables the `/mcp/auth/` endpoints. |
| `OIDC_AUDIENCE` | `""` | No | OIDC audience value. Reserved for future token validation — not currently enforced. |

### Frontend Variables

Set these in `ui/.env`. For local Docker Compose deployments, `docker-compose.yml` injects them automatically from the backend env, so you only need this file when running the UI outside Docker.

| Variable | Default | Required | Description |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | — | **Yes** | Base URL for the OpenMemory API. Example: `http://localhost:8765`. |
| `NEXT_PUBLIC_USER_ID` | — | **Yes** | User ID the UI queries. Must match `USER` in `api/.env`. |

## Troubleshooting

### Issue 1: Port Already in Use

**Symptom**: `docker-compose up` fails with `Bind for 0.0.0.0:8765 failed: port is already allocated` (or similar for ports 3001 or 6333).

**Cause**: Another process is already listening on one of the three ports OpenMemory needs: `8765` (API), `3001` (UI), or `6333` (Qdrant).

**Fix**: Find and stop the conflicting process, or remap the port in `docker-compose.yml`.

```bash
# Find what's using port 8765
sudo lsof -i :8765
# or
sudo ss -tlnp | grep 8765

# Stop the conflicting process, then retry
docker-compose up -d
```

To remap instead of stopping the conflict, change the host-side port in `docker-compose.yml`:

```yaml
# Change 8765 to an available port, e.g. 8766
ports:
  - "8766:8765"
```

Then update `NEXT_PUBLIC_API_URL` in your UI env to match the new port.

---

### Issue 2: OIDC Authentication Errors

**Symptom**: MCP client connections to `/mcp/auth/...` return `503 Service Unavailable`, or API calls return `401 Unauthorized`.

**Cause**: Two distinct problems share similar symptoms.

- `503` means `OIDC_ISSUER_URL` is empty or not set. The JWKS client can't initialise without it, so the auth endpoint fails immediately.
- `401` means the issuer URL is set but wrong, or the token has expired. Tokens are only validated at connection time, so an expired token won't be caught until the next reconnect.

**Fix**:

For `503` — set the correct issuer URL in `api/.env`:

```env
OIDC_ISSUER_URL=https://your-keycloak-host/realms/your-realm
```

Then restart the API:

```bash
docker-compose restart openmemory-mcp
docker-compose logs openmemory-mcp | grep -i oidc
```

For `401` — verify the issuer URL matches exactly what your identity provider advertises (check `/.well-known/openid-configuration`), then reconnect your MCP client to force a fresh token exchange.

---

### Issue 3: Memories Not Appearing

**Symptom**: You add a memory through the UI or API, but the dashboard shows nothing, or search returns empty results.

**Cause**: Three common culprits.

- The `USER` env var in `api/.env` doesn't match `NEXT_PUBLIC_USER_ID` in the UI config. Memories were stored under a different `user_id` than the UI is querying.
- The app is paused in the UI. Paused apps don't process new memories.
- Qdrant (`mem0_store`) isn't healthy, so vectors aren't being written.

**Fix**:

Check that your user IDs match:

```bash
# What the API uses
grep USER api/.env

# What the UI queries
grep NEXT_PUBLIC_USER_ID ui/.env
# or check docker-compose.yml — NEXT_PUBLIC_USER_ID is set from $USER
```

Check Qdrant health:

```bash
curl http://localhost:6333/healthz
# Should return: {"title":"qdrant - vector search engine","version":"..."}
```

Check the API logs for write errors:

```bash
docker-compose logs openmemory-mcp --tail=50
```

If the app is paused, open `http://localhost:3001`, find the app in the sidebar, and toggle it back to active.

---

### Issue 4: Docker Compose Services Not Starting

**Symptom**: Containers exit immediately after `docker-compose up`, or health checks keep failing and containers restart in a loop.

**Cause**: The most common reasons are a missing or empty `OPENAI_API_KEY`, a missing `api/.env` file, or volume permission issues on the mounted `./api` directory.

**Fix**:

Check container logs first:

```bash
docker-compose logs openmemory-mcp
docker-compose logs mem0_store
docker-compose logs openmemory-ui
```

Verify `api/.env` exists and has the required key:

```bash
ls -la api/.env
grep OPENAI_API_KEY api/.env
```

If the file is missing, create it from the example:

```bash
cp api/.env.example api/.env
# then set OPENAI_API_KEY and USER
```

For volume permission errors (common on Linux), check that the `./api` directory is readable by the container user:

```bash
ls -la api/
# If needed:
chmod -R 755 api/
```

After fixing, bring the stack back up cleanly:

```bash
docker-compose down && docker-compose up -d
```

---

### Issue 5: MCP Client Can't Connect

**Symptom**: Your AI tool (Claude, Cursor, etc.) shows an MCP server error, connection timeout, or "server not found" when trying to use OpenMemory tools.

**Cause**: Wrong URL format in the MCP client config, the `openmemory-mcp` container isn't running, or a firewall is blocking port `8765`.

**Fix**:

First, confirm the server is reachable:

```bash
curl http://localhost:8765/docs
# Should return HTML. If it hangs or refuses, the container isn't up.

docker-compose ps openmemory-mcp
docker-compose logs openmemory-mcp --tail=20
```

Check your MCP client config uses the correct URL format:

```
http://localhost:8765/mcp/<client-name>/sse/<user-id>
```

Replace `<client-name>` with your client (e.g., `claude`, `cursor`) and `<user-id>` with the value you set for `USER`. The SSE path is required — a bare `http://localhost:8765` won't work.

If the server is running but unreachable from another machine, check that port `8765` is open in your firewall:

```bash
# On the server host
sudo ufw status
sudo iptables -L -n | grep 8765
```

---

### Issue 6: LLM or Embedder Errors

**Symptom**: Memory operations fail with errors like `AuthenticationError`, `model not found`, `RateLimitError`, or `Connection refused` in the API logs.

**Cause**: Invalid or missing API key, a model name that doesn't exist for the configured provider, or hitting rate limits on the provider's API.

**Fix**:

Check the API logs for the specific error:

```bash
docker-compose logs openmemory-mcp --tail=50 | grep -i error
```

For authentication errors, verify your key is set and valid:

```bash
grep OPENAI_API_KEY api/.env
# Test the key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $(grep OPENAI_API_KEY api/.env | cut -d= -f2)"
```

For "model not found" errors, check that `LLM_MODEL` matches a model your API key has access to:

```env
# Common mistake: using a model name from a different provider
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini   # correct for OpenAI
# NOT: LLM_MODEL=claude-sonnet-4-20250514  (that's Anthropic)
```

For rate limiting, the API will log `429` responses. Either wait and retry, or switch to a model tier with higher limits. After fixing any env var, restart the container:

```bash
docker-compose restart openmemory-mcp
```

---

### Issue 7: Kubernetes Pod CrashLoopBackOff

**Symptom**: The `openmemory-api` pod keeps restarting. `kubectl get pods` shows `CrashLoopBackOff` or `Error` status.

**Cause**: Three common causes in Kubernetes deployments.

- A required Secret (e.g., `OPENAI_API_KEY`) doesn't exist or isn't mounted correctly.
- `DATABASE_URL` points to a PostgreSQL instance that isn't reachable, or is still using the default SQLite path (which breaks with multiple replicas).
- The PersistentVolumeClaim for Qdrant storage isn't bound.

**Fix**:

Read the crash logs first:

```bash
kubectl logs <pod-name> --previous
kubectl describe pod <pod-name>
```

Check that the required Secret exists and has the expected keys:

```bash
kubectl get secret openmemory-secrets -o jsonpath='{.data}' | jq 'keys'
```

If the pod logs show a database connection error, verify `DATABASE_URL` is set to a reachable PostgreSQL instance. SQLite (`sqlite:///./openmemory.db`) won't work across multiple pods because each pod gets its own local file:

```bash
kubectl get secret openmemory-secrets -o jsonpath='{.data.DATABASE_URL}' | base64 -d
# Should be something like: postgresql://user:pass@postgres-service:5432/openmemory
```

Check PVC status for Qdrant:

```bash
kubectl get pvc
# STATUS should be "Bound" — if it's "Pending", the StorageClass may not be provisioning volumes
kubectl describe pvc <qdrant-pvc-name>
```

For a PVC stuck in `Pending`, check that your cluster has a default StorageClass:

```bash
kubectl get storageclass
```

## Further Resources

### API Documentation

The OpenMemory API serves interactive Swagger docs at runtime:

- **Local:** `http://localhost:8765/docs`
- **Remote:** `http://<your-server>:8765/docs`

The docs include all REST endpoints, request/response schemas, and a built-in request runner. No separate API client needed for exploration.

### MCP Specification

OpenMemory implements the [Model Context Protocol](https://modelcontextprotocol.io). The spec covers transport types (SSE, Streamable HTTP), tool definitions, and client integration patterns. Useful if you're building a custom MCP client or debugging connection issues.

### OIDC Provider Guides

- **Keycloak** (self-hosted): [keycloak.org/docs](https://www.keycloak.org/docs) — covers realm setup, client configuration, and token customization.
- **Auth0** (managed): [auth0.com/docs](https://auth0.com/docs) — covers application setup, token scopes, and the `preferred_username` claim.

Both providers work with OpenMemory's OIDC integration out of the box. The key requirement is that access tokens include the `preferred_username` claim.

### Mem0 Self-Hosted Server (Successor)

OpenMemory is being sunset. The actively maintained replacement is the [Mem0 self-hosted server](https://docs.mem0.ai/open-source/overview), which provides the same local memory capabilities with a more complete feature set and ongoing support.

To migrate, see the [self-hosted setup guide](https://docs.mem0.ai/open-source/setup). The core memory API is compatible, so existing integrations need minimal changes.

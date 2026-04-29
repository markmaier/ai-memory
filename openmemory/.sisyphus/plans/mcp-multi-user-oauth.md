# MCP Multi-User OAuth: JWT-Based Identity for OpenMemory

## TL;DR

> **Quick Summary**: Add JWT-based user identity extraction to the OpenMemory MCP server so multiple users share the same URL per AI agent, with `preferred_username` from Keycloak as the `user_id`. Also includes the already-applied SSE POST handler bug fix.
>
> **Deliverables**:
> - `auth.py` — JWT validation utility with JWKS caching
> - New authenticated MCP routes (`/mcp/{client_name}/sse` without user_id in path)
> - User enrichment (name/email from JWT) on first connect
> - Config additions for OIDC settings
> - UI update showing authenticated MCP URLs
> - SSE POST handler fix (already applied, just needs commit)
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 → Task 3 → Task 4 → Task 6 → Final

---

## Context

### Original Request
MCP server (`ai-memory`) authenticates via OAuth but fails to activate. After diagnosing, two issues found: (1) SSE POST handler bug swallowing responses, and (2) user identity hardcoded in URL path instead of extracted from JWT token. User wants multi-user, multi-agent support with shared URLs.

### Interview Summary
**Key Discussions**:
- `preferred_username` from Keycloak JWT confirmed as user_id source (decoded real token: `"preferred_username": "maier"`)
- All users share same URL per agent: `/mcp/{client_name}/sse` (no `/{user_id}` suffix)
- Old URL-based routes kept for backward compatibility (local dev without OAuth)
- User model already has `name` and `email` columns — no migration needed
- No `aud` claim in Keycloak access token — audience validation must be optional
- 5-min token TTL, OpenCode handles refresh
- OpenCode sends `Authorization: Bearer` header on SSE connections (confirmed via curl)

**Research Findings**:
- SSE POST handler was broken — replaced `request._send` with no-op, swallowing transport responses (fix already applied)
- `user_id_var` and `client_name_var` ContextVars already exist in `mcp_server.py`
- `get_or_create_user` in `db.py` handles user provisioning
- PyJWT + `PyJWKClient` is the standard approach for FastAPI JWT validation with JWKS caching
- Keycloak JWKS endpoint: `https://dev-silver.fra.nip-non-prod.cloud.netcetera.com/realms/nca_users/protocol/openid-connect/certs`

### Metis Review
**Identified Gaps** (addressed):
- Token expiry during long SSE streams → validate only at connection establishment (SSE is long-lived)
- JWKS endpoint unreachable at startup → fail auth gracefully (503), don't block server start
- Empty `preferred_username` claim → reject with 401, don't create user with empty ID
- `user_id_var` concurrency → ContextVar is per-task in asyncio, safe for concurrent requests
- Cross-user data isolation → already handled by `user_id` filtering in existing queries (verified)

---

## Work Objectives

### Core Objective
Enable multi-user MCP access via JWT identity extraction so multiple users share the same MCP endpoint URL, with user isolation maintained by existing `user_id` filtering.

### Concrete Deliverables
- `openmemory/api/app/utils/auth.py` — new file
- `openmemory/api/app/mcp_server.py` — new authenticated routes + SSE POST fix
- `openmemory/api/app/utils/db.py` — enriched `get_or_create_user`
- `openmemory/api/app/config.py` — OIDC env vars
- `openmemory/api/requirements.txt` — `PyJWT[crypto]`
- `openmemory/api/.env.example` — documented OIDC vars
- `openmemory/ui/components/dashboard/Install.tsx` — authenticated URL display

### Definition of Done
- [ ] `curl -H "Authorization: Bearer <valid_jwt>" https://.../mcp/openmemory/sse` → SSE stream with MCP handshake
- [ ] `curl https://.../mcp/openmemory/sse/maier` → still works (backward compat)
- [ ] Expired/invalid token → 401 JSON error
- [ ] User record enriched with name/email after first JWT-authenticated connect
- [ ] Two different users' memories are isolated (no cross-user leakage)

### Must Have
- JWT validation with JWKS caching (PyJWT)
- `preferred_username` extraction as `user_id`
- New route: `/mcp/{client_name}/sse` (authenticated, no user_id in path)
- Backward-compatible old routes: `/mcp/{client_name}/sse/{user_id}`
- User enrichment (name, email) from JWT claims
- SSE POST handler fix committed

### Must NOT Have (Guardrails)
- NO database migrations (use existing columns)
- NO RBAC/role-based access (just extract username)
- NO server-side token refresh (client handles it)
- NO user management UI
- NO `aud` validation requirement (Keycloak doesn't include it)
- NO breaking changes to existing unauthenticated routes
- NO `python-jose` or `authlib` — PyJWT only
- NO logout/token revocation handling

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest in `openmemory/api/`)
- **Automated tests**: Tests-after (add test for auth.py)
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **API/Backend**: Use Bash (curl) — Send requests, assert status + response fields
- **Auth flows**: Use Bash (Python one-liner) — Decode JWT, validate claims

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — all independent):
├── Task 1: auth.py — JWT validation utility [quick]
├── Task 2: config.py + requirements.txt + .env.example [quick]
└── Task 3: SSE POST handler fix commit [quick]

Wave 2 (Core — depends on Wave 1):
├── Task 4: New authenticated MCP routes in mcp_server.py (depends: 1, 2) [deep]
├── Task 5: User enrichment in db.py (depends: 1) [quick]
└── Task 6: Unit test for auth.py (depends: 1) [quick]

Wave 3 (Polish — depends on Wave 2):
├── Task 7: UI Install.tsx update (depends: 4) [quick]
└── Task 8: Integration smoke test (depends: 4, 5) [unspecified-high]

Wave FINAL (After ALL tasks):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real QA — curl-based end-to-end (unspecified-high)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 4, 5, 6 |
| 2 | — | 4 |
| 3 | — | — |
| 4 | 1, 2 | 7, 8 |
| 5 | 1 | 8 |
| 6 | 1 | — |
| 7 | 4 | — |
| 8 | 4, 5 | — |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 `quick`, T2 `quick`, T3 `quick`
- **Wave 2**: 3 tasks — T4 `deep`, T5 `quick`, T6 `quick`
- **Wave 3**: 2 tasks — T7 `quick`, T8 `unspecified-high`
- **FINAL**: 4 tasks — F1 `oracle`, F2 `unspecified-high`, F3 `unspecified-high`, F4 `deep`

---

## TODOs

- [ ] 1. Create JWT validation utility (`auth.py`)

  **What to do**:
  - Create `openmemory/api/app/utils/auth.py`
  - Implement `decode_jwt(token: str) -> dict` that:
    - Uses `PyJWKClient` to fetch/cache JWKS from Keycloak
    - Decodes JWT with RS256 algorithm
    - Validates `exp`, `iss` claims
    - Does NOT require `aud` (Keycloak doesn't include it)
    - Returns decoded payload dict
  - Implement `get_user_from_token(request: Request) -> dict | None` that:
    - Extracts `Authorization: Bearer <token>` from request headers
    - Calls `decode_jwt`, returns payload or None
    - Handles `ExpiredSignatureError`, `InvalidTokenError` gracefully
  - Implement `require_jwt_user(request: Request) -> dict` (FastAPI dependency) that:
    - Calls `get_user_from_token`
    - Raises `HTTPException(401)` if no valid token
    - Raises `HTTPException(401)` if `preferred_username` is empty/missing
    - Returns decoded payload
  - JWKS client must be module-level singleton with built-in caching (PyJWKClient default: 300s)
  - Read `OIDC_ISSUER_URL` from config to construct JWKS URL: `{OIDC_ISSUER_URL}/protocol/openid-connect/certs`

  **Must NOT do**:
  - No `aud` validation
  - No `python-jose` or `authlib` — PyJWT only
  - No server-side refresh token handling

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `openmemory/api/app/utils/permissions.py` — existing utility module pattern in this project
  - `openmemory/api/main.py:43-65` — OAuth protected resource metadata setup (shows OIDC URLs already configured)

  **API/Type References**:
  - `openmemory/api/app/config.py` — where to read OIDC_ISSUER_URL from

  **External References**:
  - PyJWT docs: `https://pyjwt.readthedocs.io/en/stable/usage.html#retrieve-rsa-signing-keys-from-a-jwks-endpoint`
  - Keycloak JWKS: `https://dev-silver.fra.nip-non-prod.cloud.netcetera.com/realms/nca_users/protocol/openid-connect/certs`

  **WHY Each Reference Matters**:
  - `permissions.py` — shows the file organization pattern for utils in this project
  - `main.py` OAuth setup — shows the OIDC URLs are already available; don't reinvent discovery
  - PyJWT JWKS docs — exact API for `PyJWKClient` with caching

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Valid JWT decodes successfully
    Tool: Bash (python one-liner)
    Preconditions: Fresh Keycloak token obtained via refresh
    Steps:
      1. Get fresh token: curl -s -X POST https://dev-silver.fra.nip-non-prod.cloud.netcetera.com/realms/nca_users/protocol/openid-connect/token -d "grant_type=refresh_token&client_id=ai-memory-cli&refresh_token=<from_mcp_auth_json>" | jq -r .access_token
      2. In Python: from app.utils.auth import decode_jwt; result = decode_jwt("<token>")
      3. Assert result["preferred_username"] == "maier"
      4. Assert result["iss"] == "https://dev-silver.fra.nip-non-prod.cloud.netcetera.com/realms/nca_users"
    Expected Result: Decoded payload with preferred_username and iss claims
    Evidence: .sisyphus/evidence/task-1-valid-jwt-decode.txt

  Scenario: Expired token raises appropriate error
    Tool: Bash (python one-liner)
    Preconditions: An expired JWT (wait 5min or use a previously captured one)
    Steps:
      1. Call decode_jwt with expired token
      2. Expect jwt.ExpiredSignatureError
    Expected Result: ExpiredSignatureError raised
    Evidence: .sisyphus/evidence/task-1-expired-token.txt

  Scenario: Missing preferred_username rejected
    Tool: Bash (python one-liner)
    Preconditions: Mock a token payload without preferred_username
    Steps:
      1. Call require_jwt_user with token that decodes but has no preferred_username
      2. Expect HTTPException(401)
    Expected Result: 401 error raised
    Evidence: .sisyphus/evidence/task-1-missing-username.txt
  ```

  **Commit**: YES (groups with Task 2)
  - Message: `feat(mcp): add JWT validation utility and OIDC config`
  - Files: `openmemory/api/app/utils/auth.py`

- [ ] 2. Add OIDC config, PyJWT dependency, and env documentation

  **What to do**:
  - Add to `openmemory/api/app/config.py`:
    - `OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", "")` — empty default means auth disabled
    - `OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "")` — optional, for future use
  - Add to `openmemory/api/requirements.txt`:
    - `PyJWT[crypto]>=2.8.0`
  - Add to `openmemory/api/.env.example`:
    - `OIDC_ISSUER_URL=` with comment explaining it enables JWT auth
    - `OIDC_AUDIENCE=` with comment saying optional

  **Must NOT do**:
  - Don't add more than these two env vars
  - Don't add `authlib` or `python-jose`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 4
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `openmemory/api/app/config.py` — existing env var pattern (see `USER_ID`, `DEFAULT_APP_ID`)
  - `openmemory/api/requirements.txt` — existing dependency list
  - `openmemory/api/.env.example` — existing env documentation

  **WHY Each Reference Matters**:
  - `config.py` — follow the exact `os.getenv()` pattern used for existing vars
  - `requirements.txt` — add in alphabetical order or at end, match version pinning style

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Config vars load correctly
    Tool: Bash (python)
    Preconditions: Set OIDC_ISSUER_URL env var
    Steps:
      1. OIDC_ISSUER_URL=https://example.com python -c "from app.config import OIDC_ISSUER_URL; print(OIDC_ISSUER_URL)"
      2. Assert output is "https://example.com"
    Expected Result: Config value matches env var
    Evidence: .sisyphus/evidence/task-2-config-vars.txt

  Scenario: Default is empty when unset
    Tool: Bash (python)
    Steps:
      1. python -c "from app.config import OIDC_ISSUER_URL; print(repr(OIDC_ISSUER_URL))"
      2. Assert output is "''"
    Expected Result: Empty string default
    Evidence: .sisyphus/evidence/task-2-config-default.txt
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `feat(mcp): add JWT validation utility and OIDC config`
  - Files: `config.py`, `requirements.txt`, `.env.example`

- [ ] 3. Commit the SSE POST handler fix (already applied)

  **What to do**:
  - The fix is already applied in the working tree (`mcp_server.py`)
  - Review the diff to confirm only the POST handler is changed
  - Also commit the other working tree changes if they're related (check `database.py`, `routers/__init__.py`, `main.py`, `docker-compose.yml`)
  - Create a focused commit for the SSE fix

  **Must NOT do**:
  - Don't modify the fix — it's already correct
  - Don't bundle unrelated changes

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `openmemory/api/app/mcp_server.py:465-493` — the SSE POST handler (already fixed)

  **WHY Each Reference Matters**:
  - The fix replaces a broken handler that swallowed transport responses with the correct `await sse.handle_post_message(scope, receive, send)` call

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Commit exists with correct message
    Tool: Bash (git)
    Steps:
      1. git log --oneline -1
      2. Assert message contains "fix(mcp)" and "SSE POST"
    Expected Result: Clean commit with descriptive message
    Evidence: .sisyphus/evidence/task-3-commit.txt
  ```

  **Commit**: YES
  - Message: `fix(mcp): fix SSE POST handler swallowing transport responses`
  - Files: `openmemory/api/app/mcp_server.py` (and related files if applicable)

- [ ] 4. Add authenticated MCP routes to `mcp_server.py`

  **What to do**:
  - Add new route handler for `GET /mcp/{client_name}/sse` (WITHOUT `/{user_id}`) that:
    - Calls `require_jwt_user(request)` to get JWT payload
    - Extracts `preferred_username` as `user_id`
    - Sets `user_id_var` and `client_name_var` ContextVars
    - Calls `get_or_create_user` (with name/email enrichment from Task 5)
    - Delegates to `sse.handle_sse(request.scope, request.receive, request._send)`
  - Add corresponding POST handler for the authenticated route
  - Keep existing `/mcp/{client_name}/sse/{user_id}` routes unchanged (backward compat)
  - Handle auth errors gracefully: 401 JSON response, not HTML error page
  - If `OIDC_ISSUER_URL` is empty, the new routes should return 503 "OAuth not configured"

  **Must NOT do**:
  - Don't modify existing unauthenticated route handlers
  - Don't add RBAC/role checks
  - Don't validate `aud` claim

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 5, 6 in Wave 2)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `openmemory/api/app/mcp_server.py:380-463` — existing `handle_sse` and `handle_mcp_message` functions with ContextVar setup
  - `openmemory/api/app/mcp_server.py:20-22` — `user_id_var` and `client_name_var` ContextVar definitions
  - `openmemory/api/main.py:80-110` — route registration pattern (how routes are mounted)

  **API/Type References**:
  - `openmemory/api/app/utils/auth.py` — `require_jwt_user(request)` (from Task 1)
  - `openmemory/api/app/utils/db.py:get_or_create_user` — user provisioning function

  **WHY Each Reference Matters**:
  - `mcp_server.py:380-463` — copy the EXACT pattern of existing handlers, just swap user_id source from URL path to JWT
  - `main.py` route registration — understand how routes are added to know where to register new ones
  - `auth.py` — the dependency you'll call to extract user identity

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Authenticated SSE connects successfully
    Tool: Bash (curl)
    Preconditions: Fresh Keycloak token
    Steps:
      1. curl -s -N -H "Authorization: Bearer <valid_jwt>" http://localhost:8765/mcp/openmemory/sse --max-time 5
      2. Assert response headers contain content-type: text/event-stream
      3. Assert SSE stream starts with endpoint event
    Expected Result: SSE stream established with MCP endpoint
    Failure Indicators: 401/403/500 status, no SSE events
    Evidence: .sisyphus/evidence/task-4-auth-sse-connect.txt

  Scenario: No token returns 401
    Tool: Bash (curl)
    Steps:
      1. curl -s -w "%{http_code}" http://localhost:8765/mcp/openmemory/sse
      2. Assert HTTP status is 401
      3. Assert response body contains "detail"
    Expected Result: 401 with JSON error body
    Evidence: .sisyphus/evidence/task-4-no-token-401.txt

  Scenario: Invalid token returns 401
    Tool: Bash (curl)
    Steps:
      1. curl -s -w "%{http_code}" -H "Authorization: Bearer invalid.token.here" http://localhost:8765/mcp/openmemory/sse
      2. Assert HTTP status is 401
    Expected Result: 401 with JSON error body
    Evidence: .sisyphus/evidence/task-4-invalid-token-401.txt

  Scenario: Old route still works without auth
    Tool: Bash (curl)
    Steps:
      1. curl -s -N http://localhost:8765/mcp/openmemory/sse/maier --max-time 5
      2. Assert response headers contain content-type: text/event-stream
    Expected Result: SSE stream established (backward compat)
    Evidence: .sisyphus/evidence/task-4-backward-compat.txt
  ```

  **Commit**: YES (groups with Task 5)
  - Message: `feat(mcp): add authenticated MCP routes with JWT user identity`
  - Files: `openmemory/api/app/mcp_server.py`

- [ ] 5. Enrich user record with name/email from JWT

  **What to do**:
  - Modify `get_or_create_user` in `openmemory/api/app/utils/db.py` to accept optional `name` and `email` params
  - When creating a new user: populate `name` and `email` from JWT claims
  - When user exists but `name`/`email` are NULL: update them from JWT (one-time enrichment)
  - JWT claims to use: `name` (full name), `email`, `preferred_username` (already used as user_id)
  - Don't overwrite non-NULL values (user might have been manually set)

  **Must NOT do**:
  - No database migration
  - No new columns — use existing `name` and `email` on User model

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 6 in Wave 2)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 8
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `openmemory/api/app/utils/db.py:get_or_create_user` — the function to modify
  - `openmemory/api/app/models.py:User` — User model showing `name` (String, nullable) and `email` (String, unique, nullable) columns

  **WHY Each Reference Matters**:
  - `db.py` — the exact function to modify; understand its current signature and callers
  - `models.py:User` — confirm `name` and `email` columns exist and their constraints (email is unique)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: New user created with name and email
    Tool: Bash (python)
    Preconditions: Database running, no user "testuser123" exists
    Steps:
      1. Call get_or_create_user(db, "testuser123", name="Test User", email="test@example.com")
      2. Query: SELECT name, email FROM users WHERE user_id='testuser123'
      3. Assert name == "Test User" and email == "test@example.com"
    Expected Result: User created with enriched fields
    Evidence: .sisyphus/evidence/task-5-new-user-enriched.txt

  Scenario: Existing user with NULL name gets enriched
    Tool: Bash (python)
    Preconditions: User "testuser456" exists with name=NULL
    Steps:
      1. Call get_or_create_user(db, "testuser456", name="Enriched Name", email="enriched@example.com")
      2. Query user record
      3. Assert name == "Enriched Name"
    Expected Result: NULL fields updated, non-NULL fields preserved
    Evidence: .sisyphus/evidence/task-5-enrichment-update.txt
  ```

  **Commit**: YES (groups with Task 4)
  - Message: `feat(mcp): add authenticated MCP routes with JWT user identity`
  - Files: `openmemory/api/app/utils/db.py`

- [ ] 6. Unit test for auth.py

  **What to do**:
  - Create `openmemory/api/tests/test_auth.py`
  - Test `decode_jwt` with mocked JWKS endpoint (don't call real Keycloak in tests)
  - Test `require_jwt_user` with valid token, expired token, missing username, no auth header
  - Use `unittest.mock.patch` to mock `PyJWKClient`
  - Follow existing test patterns in `openmemory/api/tests/`

  **Must NOT do**:
  - No real Keycloak calls in unit tests
  - No integration tests (that's Task 8)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5 in Wave 2)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `openmemory/api/tests/test_mcp_server.py` — existing test patterns for MCP components
  - `openmemory/api/app/utils/auth.py` — the module under test (from Task 1)

  **WHY Each Reference Matters**:
  - `test_mcp_server.py` — follow same test structure, fixture patterns, imports

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Tests pass
    Tool: Bash
    Steps:
      1. cd openmemory/api && python -m pytest tests/test_auth.py -v
      2. Assert all tests pass
    Expected Result: 4+ tests pass, 0 failures
    Evidence: .sisyphus/evidence/task-6-test-results.txt
  ```

  **Commit**: YES
  - Message: `test(mcp): add unit tests for JWT auth utility`
  - Files: `openmemory/api/tests/test_auth.py`
  - Pre-commit: `pytest tests/test_auth.py`

- [ ] 7. Update UI Install component for authenticated URLs

  **What to do**:
  - Modify `openmemory/ui/components/dashboard/Install.tsx`
  - When OIDC is configured (detected via API or env), show the authenticated URL format:
    - `https://<host>/mcp/<client_name>/sse` (no user_id suffix)
    - Include note about OAuth configuration needed in MCP client
  - Keep showing the old URL format as fallback for local dev
  - Show example OpenCode config snippet with `oauth` section

  **Must NOT do**:
  - No user management UI
  - No OAuth flow in the UI itself

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 8 in Wave 3)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `openmemory/ui/components/dashboard/Install.tsx` — the component to modify (URL generation logic)
  - `openmemory/ui/hooks/useAppsApi.ts` — API hooks that may expose OIDC status

  **WHY Each Reference Matters**:
  - `Install.tsx` — the exact component; find where URLs are constructed and add authenticated variant
  - `useAppsApi.ts` — see if there's an existing way to detect OIDC availability from frontend

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Authenticated URL shown when OIDC available
    Tool: Bash (grep)
    Steps:
      1. Read Install.tsx, verify it conditionally renders authenticated URL
      2. Grep for the pattern "/mcp/" without user_id in URL construction
    Expected Result: Component renders both URL formats with conditional logic
    Evidence: .sisyphus/evidence/task-7-install-urls.txt

  Scenario: Build succeeds
    Tool: Bash
    Steps:
      1. cd openmemory/ui && npm run build
      2. Assert exit code 0
    Expected Result: Build passes with no TypeScript errors
    Evidence: .sisyphus/evidence/task-7-build.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): show authenticated MCP URLs in Install component`
  - Files: `openmemory/ui/components/dashboard/Install.tsx`

- [ ] 8. Integration smoke test (end-to-end)

  **What to do**:
  - Write a shell script or pytest test that:
    1. Obtains a fresh Keycloak token via refresh token
    2. Connects to authenticated SSE endpoint with Bearer token
    3. Sends MCP `initialize` message via POST
    4. Asserts MCP `initialize` response comes back via SSE
    5. Verifies user was created/enriched in the database
  - This tests the full flow: auth → route → ContextVar → MCP handshake → user provisioning
  - Also test backward compat: same flow on old URL without auth

  **Must NOT do**:
  - Don't hardcode tokens — use refresh flow
  - Don't test against production — use local Docker or dev cluster

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 7 in Wave 3)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: Tasks 4, 5

  **References**:

  **Pattern References**:
  - `openmemory/api/tests/test_mcp_server.py` — existing MCP test patterns
  - `/home/myuser/.local/share/opencode/mcp-auth.json` — where refresh tokens are stored

  **WHY Each Reference Matters**:
  - `test_mcp_server.py` — existing test setup for MCP server, may have fixtures to reuse
  - `mcp-auth.json` — source of refresh token for obtaining fresh access tokens

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full MCP handshake with JWT auth
    Tool: Bash (curl + python)
    Preconditions: API running locally or on dev cluster
    Steps:
      1. Get fresh token via Keycloak refresh endpoint
      2. curl -N -H "Authorization: Bearer <token>" http://localhost:8765/mcp/openmemory/sse → capture SSE endpoint URL
      3. POST initialize message to the endpoint URL with Bearer token
      4. Assert SSE stream returns initialize response with serverInfo
    Expected Result: Full MCP handshake completes with JWT-authenticated user
    Failure Indicators: 401, timeout, no SSE events, missing serverInfo
    Evidence: .sisyphus/evidence/task-8-full-handshake.txt

  Scenario: User record enriched after handshake
    Tool: Bash (python)
    Preconditions: After successful handshake from scenario above
    Steps:
      1. Query database for user with user_id matching preferred_username
      2. Assert name and email are populated from JWT claims
    Expected Result: User record has name and email from Keycloak token
    Evidence: .sisyphus/evidence/task-8-user-enriched.txt
  ```

  **Commit**: NO (evidence only, no committed test file needed — or optionally commit as integration test)

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint). For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run linter, check for `as any`/`@ts-ignore`, empty catches, `console.log` in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction.
  Output: `Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task. Test cross-task integration. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Group | Message | Files | Pre-commit |
|-------|---------|-------|------------|
| Task 3 | `fix(mcp): fix SSE POST handler swallowing transport responses` | `mcp_server.py` | — |
| Tasks 1,2 | `feat(mcp): add JWT validation utility and OIDC config` | `auth.py`, `config.py`, `requirements.txt`, `.env.example` | — |
| Tasks 4,5 | `feat(mcp): add authenticated MCP routes with JWT user identity` | `mcp_server.py`, `db.py` | — |
| Task 6 | `test(mcp): add unit tests for JWT auth utility` | `tests/test_auth.py` | `pytest tests/test_auth.py` |
| Tasks 7 | `feat(ui): show authenticated MCP URLs in Install component` | `Install.tsx` | — |

---

## Success Criteria

### Verification Commands
```bash
# Auth endpoint works
curl -s -H "Authorization: Bearer <valid_jwt>" https://ai-memory.nip-non-prod.cloud.netcetera.com/mcp/openmemory/sse  # Expected: SSE stream (text/event-stream)

# Backward compat
curl -s https://ai-memory.nip-non-prod.cloud.netcetera.com/mcp/openmemory/sse/maier  # Expected: SSE stream

# Invalid token rejected
curl -s -H "Authorization: Bearer invalid" https://ai-memory.nip-non-prod.cloud.netcetera.com/mcp/openmemory/sse  # Expected: 401

# Unit tests pass
cd openmemory/api && pytest tests/test_auth.py  # Expected: PASS
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] OpenCode can connect via new URL format

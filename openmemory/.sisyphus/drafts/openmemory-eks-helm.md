# Draft: OpenMemory EKS Helm Chart Deployment

## Requirements (confirmed)
- Create a Helm chart for openmemory
- Chart location: `/home/myuser/GIT/nip-application-deployment/charts/`
- Deploy to namespace: `nip-ai-memory`
- Deployment config in: `/home/myuser/GIT/nip-application-deployment/deployments/dev-silver/`
- Protected by EnvoyGateway
- OAuth against `vsdi_integration@prev-silver-mercury` realm (from kubectl)
- Database: Serverless RDS Aurora PostgreSQL (not in-cluster)

## Technical Decisions
- (pending exploration results)

## Research Findings

### Openmemory Architecture (confirmed)
**3 services:**
1. **API/MCP Server** (`openmemory-mcp`)
   - FastAPI + uvicorn on port `8765`
   - Embeds MCP server at `/mcp` path (SSE transport)
   - SQLAlchemy DB via `DATABASE_URL` (defaults to SQLite)
   - Alembic migrations
   - Auto-creates tables + default user/app on startup
   - Key env: `DATABASE_URL`, `OPENAI_API_KEY`, `USER`, `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDER_PROVIDER`, `EMBEDDER_MODEL`
   - Vector store selection: env-driven (Qdrant default via `QDRANT_HOST`/`QDRANT_PORT`, pgvector via `PG_HOST`/`PG_PORT`, etc.)

2. **UI** (`openmemory-ui`)
   - Next.js 15, standalone output, port `3000`
   - Stateless - no persistent storage needed
   - Key env: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_USER_ID`
   - Runtime env substitution for `NEXT_PUBLIC_*` vars via entrypoint.sh

3. **Vector Store** (default: Qdrant)
   - Image: `qdrant/qdrant`, port `6333`
   - Needs persistent volume at `/mem0/storage`
   - Alternative: pgvector, Redis, Chroma, Milvus, Elasticsearch, etc.

**Database:** SQLAlchemy with Alembic. `DATABASE_URL` env var. Defaults to SQLite.
**No explicit health endpoint** in API - need `/docs` or custom.
**Startup order:** DB must be reachable before API starts (table creation at import time).

### EKS Deployment Patterns (confirmed)
**Repository structure:**
- Charts: `charts/<name>/<version>/` (Chart.yaml, values.yaml, templates/)
- Deployments: `deployments/dev-silver/<app>/` (app-config.yaml + values.yaml)
- ArgoCD: ApplicationSet scans `deployments/dev-silver/*/app-config.yaml`
- **ArgoCD destination namespace HARDCODED to `nip-dev-silver`** — user wants `nip-ai-memory` → CONFLICT

**EnvoyGateway pattern (from didoc chart):**
- Supports shared gateway (`nip-envoy-gateway/envoy-gateway`) or dedicated per-app
- HTTPRoute per host, SecurityPolicy per HTTPRoute for OIDC
- OIDC: issuer, authorizationEndpoint, tokenEndpoint, clientID, clientSecretRef
- JWT claim-to-header extraction (preferred_username, email)
- redirectURL auto-computed as `https://<host>/oauth2/callback`

**ExternalSecret pattern:**
- `ClusterSecretStore: aws-secrets-manager`
- `dataFrom.extract.key: /nip/keycloak/...`
- `dataTemplate` maps keys to secret fields

**OAuth reference (didoc-public):**
- Issuer: `https://id.netcetera.com/realms/vsdi_integration`
- Secret path: `/nip/keycloak/prod-silver-mercury/vsdi_integration/client-secret/didoc-public`

**Container images:**
- ECR pattern: `230970045646.dkr.ecr.eu-central-1.amazonaws.com/nca-497-5/<app>`

## Decisions Made
1. **Namespace**: Separate ApplicationSet for `nip-ai-memory` (new file in argocd/)
2. **Vector store**: Qdrant in-cluster (StatefulSet + PVC) for vector similarity search
3. **LLM/Embedder**: OpenAI (gpt-4o-mini + text-embedding-3-small) — need OPENAI_API_KEY in AWS Secrets Manager
4. **Gateway**: Shared `nip-envoy-gateway/envoy-gateway` with cross-namespace parentRef (didoc pattern)
5. **Hostname**: `memory.id.netcetera.com`
6. **Container images**: ECR in same account (230970045646)
7. **URL routing**: Single hostname, path-based
8. **MCP access**: External
9. **OIDC client**: Needs creation (prerequisite)
10. **Code patches**: Include in plan (database.py fix + /healthz + CORS)
11. **Auth strategy**: OIDC for UI+API routes, MCP open (separate HTTPRoute)
12. **ReferenceGrant**: NOT needed (following didoc Pattern A — HTTPRoutes in app namespace)
13. **Database**: Aurora PostgreSQL for history/metadata only (DATABASE_URL replaces default SQLite ~/.mem0/history.db)

## Defaults Applied
- USER env var: "openmemory" (not OS $USER)
- Health checks: /healthz for API readiness (code patch), / for UI
- DB topology: Aurora PostgreSQL for history/metadata, Qdrant for vectors (separate concerns)
- Replicas: 1 each (API + UI + Qdrant)
- Resources: API 200m/256Mi req, 500m/512Mi lim; UI 100m/128Mi req, 250m/256Mi lim
- Migration: init container with alembic upgrade head

## Scope Boundaries
- INCLUDE: Helm chart, deployment config, EnvoyGateway routes, OAuth config, RDS integration, ExternalSecrets
- EXCLUDE: (TBD)

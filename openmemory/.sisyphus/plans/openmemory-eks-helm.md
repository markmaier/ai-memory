# OpenMemory EKS Helm Chart Deployment

## TL;DR

> **Quick Summary**: Create a Helm chart and deployment config to run OpenMemory (FastAPI API + Next.js UI + Qdrant) on EKS with EnvoyGateway OIDC protection, Qdrant for vector similarity search, RDS Aurora PostgreSQL for history/metadata (replacing default SQLite), and external MCP access.
> 
> **Deliverables**:
> - Helm chart at `charts/openmemory/1.0.0/` in the nip-application-deployment repo
> - ArgoCD ApplicationSet for `nip-ai-memory` namespace
> - Deployment values at `deployments/dev-silver/openmemory/`
> - Code patches in the openmemory source (database.py fix, /healthz endpoint, configurable CORS)
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves + final verification
> **Critical Path**: Code patches + Chart scaffold → Templates → Deployment values + Validation → Final Verification

---

## Context

### Original Request
Deploy OpenMemory in EKS environment using a Helm chart at `/home/myuser/GIT/nip-application-deployment/charts/`, running in namespace `nip-ai-memory` in the dev-silver environment, protected by EnvoyGateway with OAuth against the `vsdi_integration@prev-silver-mercury` realm, using serverless RDS Aurora PostgreSQL.

### Interview Summary
**Key Discussions**:
- **Namespace**: `nip-ai-memory` requires a new ArgoCD ApplicationSet (existing one targets `nip-dev-silver`)
- **Vector store**: Qdrant deployed in-cluster (StatefulSet) for vector similarity search
- **Database**: Aurora PostgreSQL for history/metadata DB (`DATABASE_URL` replaces default SQLite `~/.mem0/history.db`)
- **LLM/Embedder**: OpenAI (gpt-4o-mini + text-embedding-3-small)
- **Gateway**: Shared `nip-envoy-gateway/envoy-gateway` (cross-namespace parentRef, didoc pattern)
- **Hostname**: `memory.id.netcetera.com` with single-hostname path-based routing
- **Auth**: OIDC for UI + API routes; MCP route left open (separate HTTPRoute)
- **Code patches**: database.py SQLite fix, /healthz endpoint, CORS restriction — included in plan
- **Container images**: Build from Dockerfiles, push to ECR (same account `230970045646`)
- **OIDC client**: Needs creation in `vsdi_integration@prev-silver-mercury` realm (manual prerequisite)

**Research Findings**:
- OpenMemory architecture: 3 services (API port 8765, UI port 3000, Qdrant port 6333), SQLAlchemy + Alembic for metadata, env-driven vector store selection, MCP embedded in API at `/mcp`
- API routes: `/api/v1/memories`, `/api/v1/apps`, `/api/v1/stats`, `/api/v1/config`, `/api/v1/backup`, `/mcp/*`, `/docs`, `/redoc`
- `didoc` chart (12.0.0) is the closest blueprint for EnvoyGateway + OIDC + ExternalSecrets patterns
- ArgoCD ApplicationSet scans `deployments/<env>/*/app-config.yaml`, destination namespace per AppSet
- ExternalSecret: `ClusterSecretStore: aws-secrets-manager`, `dataFrom.extract`

### Metis Review
**Identified Gaps** (addressed):
- **`database.py` blocker**: SQLite-only `connect_args={"check_same_thread": False}` crashes with PostgreSQL → Code patch task added
- **Zero auth on API/MCP**: → OIDC SecurityPolicy covers UI+API; MCP left open as separate HTTPRoute
- **`$USER` env var**: Reads OS user in containers → Explicitly set to "openmemory" in Helm values
- **Aurora Serverless connection drop**: → `pool_recycle=300` in database.py patch
- **CORS `allow_origins=["*"]`**: → Configurable via `CORS_ALLOWED_ORIGINS` env var
- **Schema migration**: `create_all()` isn't Alembic → Init container runs `alembic upgrade head`
- **UI runtime env substitution**: `NEXT_PUBLIC_API_URL` must be browser-reachable URL → Set to `https://memory.id.netcetera.com`
- **ReferenceGrant**: NOT needed — following didoc Pattern A (HTTPRoutes in app namespace with parentRef to shared gateway)

---

## Work Objectives

### Core Objective
Create a production-ready Helm chart that deploys OpenMemory (API + UI + Qdrant) on EKS with OIDC protection via EnvoyGateway, Qdrant for vector similarity search, Aurora PostgreSQL for history/metadata, and exposed at `memory.id.netcetera.com`.

### Concrete Deliverables
- `charts/openmemory/1.0.0/` — Complete Helm chart (Chart.yaml, values.yaml, _helpers.tpl, templates/)
- `argocd/nip-non-prod/applications/dev-silver-ai-memory.yaml` — ArgoCD ApplicationSet
- `deployments/dev-silver/openmemory/app-config.yaml` + `values.yaml` — Environment overrides
- Patched `openmemory/api/app/database.py` — PostgreSQL-safe engine config
- New `openmemory/api/app/routers/health.py` — `/healthz` endpoint for K8s probes
- Patched `openmemory/api/main.py` — CORS configurable via env var, health router included

### Definition of Done
- [ ] `helm lint charts/openmemory/1.0.0/` passes with no errors
- [ ] `helm template openmemory charts/openmemory/1.0.0/ -f deployments/dev-silver/openmemory/values.yaml` renders all expected resources
- [ ] Rendered output contains: 2 Deployments, 1 StatefulSet, 3 Services, 1 ConfigMap, 2+ ExternalSecrets, 2 HTTPRoutes, 1 SecurityPolicy, 1 PVC
- [ ] SecurityPolicy targets only the protected HTTPRoute (not MCP)
- [ ] All env vars correctly split between ConfigMap (non-sensitive) and ExternalSecret (sensitive)
- [ ] Code patches pass: `python -c "from app.database import engine"` with `DATABASE_URL=postgresql://...`

### Must Have
- Two separate Deployments (API + UI) with independent scaling
- Qdrant StatefulSet with PersistentVolumeClaim for vector storage
- Three Services (API, UI, Qdrant)
- OIDC SecurityPolicy on protected HTTPRoute (UI + API routes)
- Unprotected MCP HTTPRoute (separate from OIDC-protected routes)
- ExternalSecrets for: OIDC client secret, OPENAI_API_KEY, database credentials
- ConfigMap for non-sensitive env vars (including `QDRANT_HOST`, `QDRANT_PORT`)
- `DATABASE_URL` pointing to Aurora PostgreSQL (replacing default SQLite `~/.mem0/history.db`)
- Init container for Alembic migration on API Deployment
- Readiness/liveness probes on all workloads (API, UI, Qdrant)
- ArgoCD ApplicationSet targeting `nip-ai-memory` namespace

### Must NOT Have (Guardrails)
- **NO RDS/Aurora provisioning** — prerequisite, not part of chart
- **NO Keycloak client creation** — prerequisite, documented in plan
- **NO CI/CD pipeline** — ECR push is out of scope
- **NO monitoring/observability** — no ServiceMonitor, Grafana dashboard, or structured logging
- **NO NetworkPolicy/CiliumNetworkPolicy** — unless explicitly requested later
- **NO HPA/PDB** — no autoscaling or disruption budgets
- **NO multi-environment** — only dev-silver, no staging/prod pre-engineering
- **NO application logic changes** beyond the three targeted patches (database.py, healthz, CORS)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: NO (Helm chart, no app test framework applicable)
- **Automated tests**: None (Helm charts validated via `helm lint` + `helm template`)
- **Framework**: helm CLI + kubectl dry-run

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Helm chart tasks**: Use Bash (`helm template`, `helm lint`, `grep` on rendered output)
- **Code patch tasks**: Use Bash (`python -c "..."` import checks, `grep` for patterns)
- **ArgoCD tasks**: Use Bash (`kubectl --dry-run=client -f ...` or YAML validation)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation, 3 parallel):
├── Task 1: Code patches in openmemory source [unspecified-high]
├── Task 2: Helm chart scaffold (Chart.yaml, _helpers.tpl, values.yaml) [unspecified-high]
└── Task 3: ArgoCD ApplicationSet for nip-ai-memory [quick]

Wave 2 (After Task 2 — chart templates, 4 parallel):
├── Task 4: Workload templates (API + UI deployments, Qdrant StatefulSet, services) [unspecified-high]
├── Task 5: Config templates (configmap + external-secrets) [quick]
├── Task 6: Gateway templates (httproutes + securitypolicy) [unspecified-high]
└── Task 7: ALB Ingress template for ExternalDNS [quick]

Wave 3 (After Wave 2 — deployment config + validation, 2 parallel):
├── Task 8: Dev-silver deployment values [quick]
└── Task 9: Full chart validation (helm lint + helm template) [unspecified-high]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real QA — helm template + manifest inspection (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1    | —         | 9      | 1    |
| 2    | —         | 4,5,6,7| 1    |
| 3    | —         | 8      | 1    |
| 4    | 2         | 8,9    | 2    |
| 5    | 2         | 8,9    | 2    |
| 6    | 2         | 8,9    | 2    |
| 7    | 2         | 8,9    | 2    |
| 8    | 3,4,5,6,7 | 9      | 3    |
| 9    | 1,4,5,6,7,8| F1-F4 | 3    |

### Agent Dispatch Summary

- **Wave 1**: **3** — T1 → `unspecified-high`, T2 → `unspecified-high`, T3 → `quick`
- **Wave 2**: **4** — T4 → `unspecified-high`, T5 → `quick`, T6 → `unspecified-high`, T7 → `quick`
- **Wave 3**: **2** — T8 → `quick`, T9 → `unspecified-high`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## Prerequisites (Manual Steps — NOT Part of This Plan)

Before deploying the Helm chart, these external resources must be provisioned:

### 1. RDS Aurora PostgreSQL Serverless v2
- Create database `openmemory` with user `openmemory`
- This database stores history/metadata only (NOT vectors — Qdrant handles that)
- Note the endpoint, port, database name, username, and password
- No pgvector extension needed — vector search is handled by Qdrant

### 2. Keycloak OIDC Client
- Create client `openmemory` in `vsdi_integration@prev-silver-mercury` realm
- Set redirect URI: `https://memory.id.netcetera.com/oauth2/callback`
- Note the client ID and client secret
- Store in AWS Secrets Manager at `/nip/keycloak/prev-silver-mercury/vsdi_integration/client-secret/openmemory`
  - Keys: `clientId`, `secret`

### 3. AWS Secrets Manager Secrets
- `/nip/openmemory/openai-api-key` — Key: `apiKey` (OpenAI API key)
- `/nip/openmemory/database` — Keys: `host`, `port`, `dbname`, `username`, `password`
- `/nip/keycloak/prev-silver-mercury/vsdi_integration/client-secret/openmemory` — Keys: `clientId`, `secret`

### 4. ECR Repositories
- Create `openmemory-api` and `openmemory-ui` repos in `230970045646.dkr.ecr.eu-central-1.amazonaws.com`
- Build and push images from `openmemory/api/Dockerfile` and `openmemory/ui/Dockerfile`

### 5. Shared EnvoyGateway Configuration
- Verify the shared Gateway at `nip-envoy-gateway/envoy-gateway` has `allowedRoutes.namespaces` that includes `nip-ai-memory` (or `from: All`)
- If not, update the Gateway to allow routes from `nip-ai-memory`

---

## TODOs

- [ ] 1. Code Patches — PostgreSQL-safe database.py, /healthz endpoint, configurable CORS

  **What to do**:
  - **Patch `openmemory/api/app/database.py`**:
    - Make `connect_args` conditional: only apply `{"check_same_thread": False}` when `DATABASE_URL` starts with `sqlite`
    - Add `pool_recycle=300` to `create_engine()` for Aurora Serverless auto-pause resilience
    - Add `pool_pre_ping=True` for stale connection detection
  - **Create `openmemory/api/app/routers/health.py`**:
    - New router with `GET /healthz` endpoint
    - Returns `{"status": "ok"}` with 200
    - Optionally checks DB connectivity (try `SELECT 1` via SessionLocal, catch exceptions)
  - **Patch `openmemory/api/main.py`**:
    - Import and include the health router: `app.include_router(health_router)`
    - Make CORS `allow_origins` configurable via env var `CORS_ALLOWED_ORIGINS` (comma-separated, default `"*"`)
    - Read env: `os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")`

  **Must NOT do**:
  - Do NOT change any business logic in existing routers
  - Do NOT modify the Alembic migration chain
  - Do NOT add new dependencies to requirements.txt
  - Do NOT change the API port or startup behavior

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Python code patches across 3 files, requires understanding SQLAlchemy engine config and FastAPI middleware
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright-cli`: No browser interaction needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 9 (validation needs patched code for import test)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `openmemory/api/app/database.py` — Current engine config with SQLite-only `connect_args={"check_same_thread": False}` on line ~15. This is the blocker: `check_same_thread` is not a valid psycopg2 argument and will crash.
  - `openmemory/api/main.py:15-21` — Current CORS middleware with hardcoded `allow_origins=["*"]`. Change to env-driven.
  - `openmemory/api/app/routers/__init__.py` — Router barrel file. Add health_router export here.
  - `openmemory/api/app/routers/memories.py:20-27` — Example of existing router pattern (APIRouter with prefix and tags). Follow this for health.py.

  **External References**:
  - SQLAlchemy `create_engine` docs: `pool_recycle`, `pool_pre_ping` parameters for connection health with cloud databases

  **WHY Each Reference Matters**:
  - `database.py` is the crash site — the patch must conditionally apply connect_args
  - `main.py` is where CORS middleware is configured and where the health router must be registered
  - Existing router pattern ensures the new health router follows the same structure

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: PostgreSQL engine creates without crash
    Tool: Bash
    Preconditions: openmemory/api/ directory, Python available
    Steps:
      1. cd openmemory/api/
      2. Run: DATABASE_URL=postgresql://test:test@localhost:5432/testdb python -c "from app.database import engine; print(type(engine))"
      3. Assert: exit code 0, output contains "Engine"
    Expected Result: No TypeError about check_same_thread
    Failure Indicators: TypeError, ImportError, or non-zero exit code
    Evidence: .sisyphus/evidence/task-1-pg-engine.txt

  Scenario: SQLite engine still works (backward compat)
    Tool: Bash
    Preconditions: openmemory/api/ directory
    Steps:
      1. cd openmemory/api/
      2. Run: DATABASE_URL=sqlite:///./test.db python -c "from app.database import engine; print(type(engine))"
      3. Assert: exit code 0, output contains "Engine"
    Expected Result: check_same_thread still applied for SQLite
    Failure Indicators: TypeError or non-zero exit code
    Evidence: .sisyphus/evidence/task-1-sqlite-engine.txt

  Scenario: /healthz endpoint exists
    Tool: Bash
    Preconditions: patched main.py with health router
    Steps:
      1. grep -r "healthz" openmemory/api/app/routers/health.py
      2. grep "health_router" openmemory/api/main.py
      3. Assert: both greps find matches
    Expected Result: health.py has /healthz route, main.py includes it
    Evidence: .sisyphus/evidence/task-1-healthz-grep.txt

  Scenario: CORS env var configurable
    Tool: Bash
    Preconditions: patched main.py
    Steps:
      1. grep "CORS_ALLOWED_ORIGINS" openmemory/api/main.py
      2. Assert: grep finds the env var read
    Expected Result: CORS origins read from environment
    Evidence: .sisyphus/evidence/task-1-cors-env.txt
  ```

  **Commit**: YES (Commit 1)
  - Message: `fix(openmemory): make database.py PostgreSQL-safe, add /healthz, configurable CORS`
  - Files: `api/app/database.py`, `api/app/routers/health.py`, `api/app/routers/__init__.py`, `api/main.py`
  - Pre-commit: `DATABASE_URL=postgresql://x:x@localhost/x python -c "from app.database import engine"`

- [ ] 2. Helm Chart Scaffold — Chart.yaml, _helpers.tpl, values.yaml

  **What to do**:
  - **Create `charts/openmemory/1.0.0/Chart.yaml`**:
    - `apiVersion: v2`, `name: openmemory`, `version: 1.0.0`, `appVersion: "1.0.0"`
    - `description: OpenMemory — self-hosted AI memory platform with MCP server`
    - No dependencies (no subcharts)
  - **Create `charts/openmemory/1.0.0/templates/_helpers.tpl`**:
    - Follow the didoc pattern for helper templates
    - `openmemory.fullname` — `{{ .Release.Name }}-{{ .Chart.Name }}` or override via `fullnameOverride`
    - `openmemory.labels.standard` — standard K8s labels (`app.kubernetes.io/name`, `app.kubernetes.io/instance`, `app.kubernetes.io/version`, `app.kubernetes.io/managed-by`)
    - `openmemory.labels.matchLabels` — subset for selectors (`app.kubernetes.io/name`, `app.kubernetes.io/instance`)
  - **Create `charts/openmemory/1.0.0/values.yaml`** with COMPLETE schema:
    ```yaml
    api:
      image: { repository: "", digest: "" }
      replicas: 1
      resources: { requests: { cpu: 200m, memory: 256Mi }, limits: { cpu: 500m, memory: 512Mi } }
      env: []  # additional env vars
      user: "openmemory"  # USER env var value (default user created on startup)
      migration:
        enabled: true  # run alembic upgrade head as init container
      probes:
        readiness: { path: /healthz, port: 8765, initialDelaySeconds: 10, periodSeconds: 10 }
        liveness: { tcpSocket: { port: 8765 }, initialDelaySeconds: 15, periodSeconds: 20 }
    ui:
      image: { repository: "", digest: "" }
      replicas: 1
      resources: { requests: { cpu: 100m, memory: 128Mi }, limits: { cpu: 250m, memory: 256Mi } }
      env: []
      probes:
        readiness: { path: /, port: 3000, initialDelaySeconds: 5, periodSeconds: 10 }
        liveness: { tcpSocket: { port: 3000 }, initialDelaySeconds: 10, periodSeconds: 20 }
    database:
      host: ""
      port: "5432"
      name: "openmemory"
      user: "openmemory"
      sslmode: "require"
    qdrant:
      enabled: true  # deploy Qdrant StatefulSet in-cluster
      image:
        repository: qdrant/qdrant
        tag: latest
      replicas: 1
      port: 6333
      resources: { requests: { cpu: 100m, memory: 256Mi }, limits: { cpu: 500m, memory: 1Gi } }
      persistence:
        enabled: true
        size: 10Gi
        storageClassName: ""  # use cluster default
      probes:
        readiness: { path: /readyz, port: 6333, initialDelaySeconds: 5, periodSeconds: 10 }
        liveness: { path: /livez, port: 6333, initialDelaySeconds: 10, periodSeconds: 20 }
    vectorStore:
      provider: "qdrant"  # qdrant for vector similarity search; Aurora for history/metadata
    llm:
      provider: "openai"
      model: "gpt-4o-mini"
    embedder:
      provider: "openai"
      model: "text-embedding-3-small"
    cors:
      allowedOrigins: ""  # comma-separated, auto-set to gateway hostname if empty
    gateway:
      create: false  # use shared gateway
      sharedGateway:
        name: envoy-gateway
        namespace: nip-envoy-gateway
        sectionName: https
      hostname: ""  # e.g., memory.id.netcetera.com
      oidc:
        enabled: true
        issuer: ""
        authorizationEndpoint: ""
        tokenEndpoint: ""
        clientId: ""
        clientSecretRef: ""
        scopes: [openid, email, profile]
        cookieNameAccessToken: "oidc-access-token-openmemory"
      albIngress:
        enabled: false
        namespace: nip-envoy-gateway
        serviceName: envoy-service
        servicePort: https-443
        annotations: {}
    externalSecrets: []
    ```

  **Must NOT do**:
  - Do NOT add subchart dependencies
  - Do NOT include template files yet (Wave 2 tasks)
  - Do NOT hardcode environment-specific values

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Helm chart design requires understanding values schema, K8s patterns, and didoc reference chart structure
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 4, 5, 6, 7 (all template tasks depend on values schema)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `charts/didoc/12.0.0/Chart.yaml` — Chart metadata pattern (apiVersion, name, version, description)
  - `charts/didoc/12.0.0/values.yaml` — Full values schema including gateway, oidc, externalSecrets, resources, image, env patterns. The openmemory values.yaml should mirror this structure for gateway/oidc/externalSecrets sections.
  - `charts/keycloak/24.4.2/values.yaml` — Large production override example showing externalDatabase pattern. Reference for the database section structure.

  **WHY Each Reference Matters**:
  - didoc Chart.yaml: exact metadata format expected by ArgoCD ApplicationSet
  - didoc values.yaml: the gateway/oidc/externalSecrets structure MUST match so templates can follow the same patterns
  - keycloak values.yaml: shows how to structure external database configuration

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Chart.yaml is valid
    Tool: Bash
    Preconditions: charts/openmemory/1.0.0/ directory exists
    Steps:
      1. Run: cat charts/openmemory/1.0.0/Chart.yaml | python -c "import sys,yaml; yaml.safe_load(sys.stdin); print('valid')"
      2. Assert: output is "valid", exit code 0
    Expected Result: Valid YAML with name=openmemory, version=1.0.0
    Evidence: .sisyphus/evidence/task-2-chart-yaml.txt

  Scenario: values.yaml contains all required sections
    Tool: Bash
    Preconditions: charts/openmemory/1.0.0/values.yaml exists
    Steps:
      1. grep -c "api:" charts/openmemory/1.0.0/values.yaml
      2. grep -c "ui:" charts/openmemory/1.0.0/values.yaml
      3. grep -c "database:" charts/openmemory/1.0.0/values.yaml
      4. grep -c "gateway:" charts/openmemory/1.0.0/values.yaml
      5. grep -c "externalSecrets:" charts/openmemory/1.0.0/values.yaml
      6. Assert: all greps return ≥1
    Expected Result: All top-level sections present
    Evidence: .sisyphus/evidence/task-2-values-sections.txt

  Scenario: _helpers.tpl defines required helpers
    Tool: Bash
    Preconditions: charts/openmemory/1.0.0/templates/_helpers.tpl exists
    Steps:
      1. grep "openmemory.fullname\|openmemory.labels.standard\|openmemory.labels.matchLabels" charts/openmemory/1.0.0/templates/_helpers.tpl
      2. Assert: all 3 helper names found
    Expected Result: All helper templates defined
    Evidence: .sisyphus/evidence/task-2-helpers.txt
  ```

  **Commit**: YES (groups with Commit 2)
  - Message: `feat(charts): add openmemory Helm chart v1.0.0`
  - Files: `charts/openmemory/1.0.0/Chart.yaml`, `charts/openmemory/1.0.0/values.yaml`, `charts/openmemory/1.0.0/templates/_helpers.tpl`

- [ ] 3. ArgoCD ApplicationSet for nip-ai-memory Namespace

  **What to do**:
  - **Create `argocd/nip-non-prod/applications/dev-silver-ai-memory.yaml`**:
    - Copy the structure from `argocd/nip-non-prod/applications/dev-silver.yaml`
    - Change `metadata.name` to `dev-silver-ai-memory`
    - Change `spec.generators[0].git.files[0].path` to `deployments/dev-silver/openmemory/*/app-config.yaml`
      - OR: use `deployments/dev-silver-ai-memory/*/app-config.yaml` if you prefer a separate deployment directory
      - Decision: use `deployments/dev-silver/openmemory/app-config.yaml` (single app, no wildcard needed — use direct path in generator)
    - Change `spec.template.metadata.name` to `"{{path.basename}}-dev-silver-ai-memory"`
    - Change `spec.template.spec.destination.namespace` to `nip-ai-memory`
    - Keep the same `project: dev`, `repoURL`, `targetRevision: develop`
    - Keep all `syncPolicy` options (automated, selfHeal, prune, CreateNamespace=true)
  - **Verify** the ArgoCD AppProject `dev` allows the `nip-ai-memory` namespace:
    - Check `argocd/nip-non-prod/projects/dev.yaml` — it should allow destinations including `nip-ai-memory`
    - If it only allows `nip-dev-silver`, document that `dev.yaml` needs updating (add `nip-ai-memory` to allowed destinations)

  **Must NOT do**:
  - Do NOT modify the existing `dev-silver.yaml` ApplicationSet
  - Do NOT modify the ArgoCD project file (just document if changes needed)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single YAML file creation following an exact existing pattern
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 8 (deployment config must match what ApplicationSet scans)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `argocd/nip-non-prod/applications/dev-silver.yaml` — EXACT template to copy. Shows ApplicationSet structure with git generator, Helm source, valueFiles reference, syncPolicy, and namespace targeting. The new file should be near-identical with changed name, path, and namespace.
  - `argocd/nip-non-prod/projects/dev.yaml` — ArgoCD AppProject that defines which namespaces the `dev` project can deploy to. Must include `nip-ai-memory` or the ApplicationSet will be rejected.

  **WHY Each Reference Matters**:
  - `dev-silver.yaml`: the exact template — copy structure, change 3 fields (name, path, namespace)
  - `dev.yaml`: determines if the new namespace is allowed — if not, the whole deployment will fail with ArgoCD permission error

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: ApplicationSet YAML is valid and targets nip-ai-memory
    Tool: Bash
    Preconditions: argocd/nip-non-prod/applications/dev-silver-ai-memory.yaml exists
    Steps:
      1. Run: python -c "import yaml; d=yaml.safe_load(open('argocd/nip-non-prod/applications/dev-silver-ai-memory.yaml')); print(d['spec']['template']['spec']['destination']['namespace'])"
      2. Assert: output is "nip-ai-memory"
    Expected Result: Namespace correctly set to nip-ai-memory
    Evidence: .sisyphus/evidence/task-3-appset-namespace.txt

  Scenario: Generator path points to openmemory deployment
    Tool: Bash
    Preconditions: dev-silver-ai-memory.yaml exists
    Steps:
      1. grep "deployments/dev-silver/openmemory" argocd/nip-non-prod/applications/dev-silver-ai-memory.yaml
      2. Assert: grep finds a match
    Expected Result: Generator scans the correct deployment path
    Evidence: .sisyphus/evidence/task-3-appset-path.txt

  Scenario: Existing dev-silver.yaml NOT modified
    Tool: Bash
    Preconditions: git working tree
    Steps:
      1. git diff argocd/nip-non-prod/applications/dev-silver.yaml
      2. Assert: empty diff (no changes)
    Expected Result: Original ApplicationSet untouched
    Evidence: .sisyphus/evidence/task-3-no-modify.txt
  ```

  **Commit**: YES (Commit 3)
  - Message: `feat(argocd): add ApplicationSet for nip-ai-memory namespace`
  - Files: `argocd/nip-non-prod/applications/dev-silver-ai-memory.yaml`

- [ ] 4. Workload Templates — API + UI Deployments, Qdrant StatefulSet, and Services

  **What to do**:
  - **Create `charts/openmemory/1.0.0/templates/api-deployment.yaml`**:
    - Deployment for the API service
    - Container: image from `{{ .Values.api.image.repository }}@{{ .Values.api.image.digest }}`
    - Port: `containerPort: 8765`
    - Command: `["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "4"]`
    - Env vars from ConfigMap (`envFrom`) + individual Secret refs for sensitive values
    - Key env vars to set explicitly: `USER={{ .Values.api.user }}`, `DATABASE_URL` (from Secret — PostgreSQL connection string replacing default SQLite `~/.mem0/history.db`), `QDRANT_HOST` and `QDRANT_PORT` (from ConfigMap — pointing to in-cluster Qdrant service), `OPENAI_API_KEY` (from Secret), `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDER_PROVIDER`, `EMBEDDER_MODEL` (from ConfigMap), `CORS_ALLOWED_ORIGINS` (from ConfigMap)
    - Readiness probe: `httpGet /healthz:8765`
    - Liveness probe: `tcpSocket:8765`
    - Init container (if `api.migration.enabled`): same image, command `["alembic", "upgrade", "head"]`, with same env vars (needs DATABASE_URL)
    - Resources from `{{ .Values.api.resources }}`
    - Labels: `{{ include "openmemory.labels.standard" . }}` + `app.kubernetes.io/component: api`
    - Selector labels: `{{ include "openmemory.labels.matchLabels" . }}` + `app.kubernetes.io/component: api`
  - **Create `charts/openmemory/1.0.0/templates/api-service.yaml`**:
    - ClusterIP Service
    - Port: `port: 8765, targetPort: 8765`
    - Selector: matchLabels + `component: api`
  - **Create `charts/openmemory/1.0.0/templates/ui-deployment.yaml`**:
    - Deployment for the UI service
    - Container: image from `{{ .Values.ui.image.repository }}@{{ .Values.ui.image.digest }}`
    - Port: `containerPort: 3000`
    - Env: `NEXT_PUBLIC_API_URL=https://{{ .Values.gateway.hostname }}`, `NEXT_PUBLIC_USER_ID={{ .Values.api.user }}`, `PORT=3000`, `HOSTNAME=0.0.0.0`
    - Readiness probe: `httpGet /:3000`
    - Liveness probe: `tcpSocket:3000`
    - Resources from `{{ .Values.ui.resources }}`
    - Labels: standard + `component: ui`
  - **Create `charts/openmemory/1.0.0/templates/ui-service.yaml`**:
    - ClusterIP Service
    - Port: `port: 3000, targetPort: 3000`
    - Selector: matchLabels + `component: ui`
  - **Create `charts/openmemory/1.0.0/templates/qdrant-statefulset.yaml`** (if `qdrant.enabled`):
    - StatefulSet for Qdrant vector database
    - Container: image from `{{ .Values.qdrant.image.repository }}:{{ .Values.qdrant.image.tag }}`
    - Port: `containerPort: 6333`
    - volumeMounts: `/qdrant/storage` → PVC
    - Readiness probe: `httpGet /readyz:6333`
    - Liveness probe: `httpGet /livez:6333`
    - Resources from `{{ .Values.qdrant.resources }}`
    - Labels: standard + `component: qdrant`
    - `volumeClaimTemplates` with `{{ .Values.qdrant.persistence.size }}` and optional `storageClassName`
  - **Create `charts/openmemory/1.0.0/templates/qdrant-service.yaml`** (if `qdrant.enabled`):
    - ClusterIP Service
    - Port: `port: 6333, targetPort: 6333`
    - Selector: matchLabels + `component: qdrant`

  **Must NOT do**:
  - Do NOT create Ingress resources (use HTTPRoute via EnvoyGateway)
  - Do NOT hardcode image tags or registry URLs
  - Do NOT expose Qdrant externally (ClusterIP only, accessed by API pod)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 6 template files (API deployment/service, UI deployment/service, Qdrant StatefulSet/service) with complex env var mapping, init container, probes, volumeClaimTemplates — needs Helm templating expertise
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: Tasks 8, 9 (deployment values and validation need workload templates)
  - **Blocked By**: Task 2 (needs values schema and _helpers.tpl)

  **References**:

  **Pattern References**:
  - `charts/didoc/12.0.0/values.yaml:1-14` — Image repository/digest and resources pattern. The openmemory API/UI deployments should use the same `image.repository` + `image.digest` approach (NOT tag-based).
  - `charts/keycloak/24.4.2/values.yaml` — Complex deployment with external DB env vars, probes, security context. Reference for production deployment patterns.
  - `openmemory/docker-compose.yml` — Qdrant service definition: image `qdrant/qdrant`, port 6333, volume `/mem0/storage`. Use as reference for the StatefulSet container spec.
  - `openmemory/api/Dockerfile` — Container port (8765), working dir, entrypoint. Must match the Deployment container spec.
  - `openmemory/ui/Dockerfile` — Container port (3000), `HOSTNAME=0.0.0.0`, standalone Next.js output. Must match UI Deployment spec.
  - `openmemory/ui/entrypoint.sh` — Runtime env substitution for `NEXT_PUBLIC_*` vars. The UI container uses this entrypoint, so env vars MUST be set on the pod (not just build-time).
  - `openmemory/api/app/database.py` — `DATABASE_URL` env var name and format expected by the API. This replaces the default SQLite `~/.mem0/history.db` with a PostgreSQL connection string to Aurora.
  - `openmemory/api/app/utils/memory.py` — `QDRANT_HOST` and `QDRANT_PORT` env var names for Qdrant vector store configuration. When these are set, the API uses Qdrant as the vector store backend.
  - `openmemory/api/app/config.py` — `USER_ID = os.getenv("USER", "default_user")` — MUST set `USER` env var explicitly.

  **WHY Each Reference Matters**:
  - Dockerfiles define container ports, working dirs, and entrypoints that the Deployment spec must match
  - docker-compose.yml shows the Qdrant container spec (image, port, volume path) that the StatefulSet must replicate
  - `database.py` defines the `DATABASE_URL` env var contract — Aurora PostgreSQL replaces the default SQLite history.db
  - `utils/memory.py` defines `QDRANT_HOST`/`QDRANT_PORT` env var names for vector store selection — getting these wrong means the API falls back to default Qdrant on localhost
  - `config.py` shows `USER` env var reads OS user — must override in pod spec
  - `entrypoint.sh` explains why `NEXT_PUBLIC_*` must be pod env vars (not build args)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: API Deployment renders with correct container spec
    Tool: Bash
    Preconditions: All chart files exist, helm installed
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set api.image.repository=test --set api.image.digest=sha256:abc123
      2. Extract the api Deployment from output
      3. Assert: containerPort is 8765, image is "test@sha256:abc123", readinessProbe.httpGet.path is "/healthz"
    Expected Result: API Deployment renders with correct ports, image, and probes
    Failure Indicators: Missing container spec fields or incorrect values
    Evidence: .sisyphus/evidence/task-4-api-deployment.txt

  Scenario: UI Deployment has NEXT_PUBLIC_API_URL set correctly
    Tool: Bash
    Preconditions: All chart files exist
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set gateway.hostname=memory.id.netcetera.com
      2. Extract ui Deployment env vars
      3. Assert: NEXT_PUBLIC_API_URL is "https://memory.id.netcetera.com"
    Expected Result: UI env var points to browser-reachable gateway URL
    Evidence: .sisyphus/evidence/task-4-ui-env.txt

  Scenario: Init container for Alembic migration exists
    Tool: Bash
    Preconditions: api-deployment.yaml exists
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set api.migration.enabled=true --set api.image.repository=test --set api.image.digest=sha256:abc
      2. grep -A5 "initContainers" from rendered output
      3. Assert: init container with "alembic" command found
    Expected Result: Init container runs alembic upgrade head before API starts
    Evidence: .sisyphus/evidence/task-4-init-migration.txt

  Scenario: Services expose correct ports
    Tool: Bash
    Preconditions: service templates exist
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/
      2. Assert: api Service has port 8765, ui Service has port 3000, qdrant Service has port 6333
    Expected Result: Services match container ports
    Evidence: .sisyphus/evidence/task-4-services.txt

  Scenario: Qdrant StatefulSet renders with PVC and probes
    Tool: Bash
    Preconditions: qdrant-statefulset.yaml exists
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set qdrant.enabled=true
      2. Extract StatefulSet from output
      3. Assert: container image is qdrant/qdrant, containerPort is 6333, volumeClaimTemplates present with 10Gi default, readinessProbe path is /readyz
    Expected Result: Qdrant StatefulSet with persistence and health checks
    Evidence: .sisyphus/evidence/task-4-qdrant-statefulset.txt
  ```

  **Commit**: YES (groups with Commit 2)
  - Message: `feat(charts): add openmemory Helm chart v1.0.0`
  - Files: `charts/openmemory/1.0.0/templates/api-deployment.yaml`, `api-service.yaml`, `ui-deployment.yaml`, `ui-service.yaml`, `qdrant-statefulset.yaml`, `qdrant-service.yaml`

- [ ] 5. Config Templates — ConfigMap and ExternalSecrets

  **What to do**:
  - **Create `charts/openmemory/1.0.0/templates/configmap.yaml`**:
    - ConfigMap with non-sensitive env vars:
      - `USER: {{ .Values.api.user }}`
      - `LLM_PROVIDER: {{ .Values.llm.provider }}`
      - `LLM_MODEL: {{ .Values.llm.model }}`
      - `EMBEDDER_PROVIDER: {{ .Values.embedder.provider }}`
      - `EMBEDDER_MODEL: {{ .Values.embedder.model }}`
      - `QDRANT_HOST: {{ include "openmemory.fullname" . }}-qdrant` (in-cluster Qdrant service name)
      - `QDRANT_PORT: {{ .Values.qdrant.port | default "6333" }}`
      - `CORS_ALLOWED_ORIGINS: {{ if .Values.cors.allowedOrigins }}{{ .Values.cors.allowedOrigins }}{{ else }}https://{{ .Values.gateway.hostname }}{{ end }}`
    - Labels: standard labels
  - **Create `charts/openmemory/1.0.0/templates/external-secrets.yaml`**:
    - Follow the EXACT pattern from `charts/didoc/12.0.0/templates/external-secrets.yaml`
    - Loop over `{{ .Values.externalSecrets }}` array
    - Each entry creates an ExternalSecret:
      - `secretStoreRef.name: aws-secrets-manager`, `kind: ClusterSecretStore`
      - `refreshInterval: 1h`
      - `target.name: {{ .targetSecretName }}`
      - `target.creationPolicy: Owner`, `deletionPolicy: Retain`
      - `target.template.data: {{ .dataTemplate }}`
      - `dataFrom.extract.key: {{ .awsSecretName }}`
    - This template handles ALL secrets: OIDC client secret, OpenAI API key, DB credentials

  **Must NOT do**:
  - Do NOT put sensitive values (passwords, API keys) in the ConfigMap
  - Do NOT hardcode AWS secret paths in the template (use values.yaml)
  - Do NOT deviate from the didoc ExternalSecret pattern

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Two straightforward template files, one following an exact existing pattern
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6, 7)
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Task 2 (needs values schema)

  **References**:

  **Pattern References**:
  - `charts/didoc/12.0.0/templates/external-secrets.yaml` — EXACT template to replicate. Shows the loop over `externalSecrets` array, ClusterSecretStore reference, dataFrom/dataTemplate pattern. Copy this structure verbatim.
  - `deployments/dev-silver/didoc-public/values.yaml:44-51` — Example of how externalSecrets are configured in deployment values. Shows `targetSecretName`, `awsSecretName`, and `dataTemplate` structure.

  **API/Type References**:
  - `openmemory/api/app/utils/memory.py` — Env var names for Qdrant: `QDRANT_HOST`, `QDRANT_PORT`. When these are set, OpenMemory uses Qdrant as the vector store backend. The ConfigMap must use these exact names.
  - `openmemory/api/main.py` — CORS middleware reads `CORS_ALLOWED_ORIGINS`

  **WHY Each Reference Matters**:
  - didoc ExternalSecret template: the EXACT pattern to copy — deviating risks incompatibility with the ClusterSecretStore
  - didoc-public values: shows real-world usage of the externalSecrets array structure
  - utils/memory.py: defines the env var contract the API expects for Qdrant vector store selection

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: ConfigMap contains all required env vars
    Tool: Bash
    Preconditions: configmap.yaml exists
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set api.user=openmemory
      2. Extract ConfigMap from output
      3. Assert: contains keys USER, LLM_PROVIDER, LLM_MODEL, EMBEDDER_PROVIDER, EMBEDDER_MODEL, QDRANT_HOST, QDRANT_PORT, CORS_ALLOWED_ORIGINS
    Expected Result: All non-sensitive env vars present with correct values
    Evidence: .sisyphus/evidence/task-5-configmap.txt

  Scenario: No sensitive values in ConfigMap
    Tool: Bash
    Preconditions: rendered ConfigMap
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ | grep -A50 "kind: ConfigMap"
      2. Assert: does NOT contain "OPENAI_API_KEY", "PASSWORD", "DATABASE_URL", "client-secret"
    Expected Result: No secrets leak into ConfigMap
    Evidence: .sisyphus/evidence/task-5-no-secrets-in-configmap.txt

  Scenario: ExternalSecret renders with correct pattern
    Tool: Bash
    Preconditions: external-secrets.yaml exists
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set-json 'externalSecrets=[{"targetSecretName":"test-secret","awsSecretName":"/nip/test","dataTemplate":{"key":"{{ .value }}"}}]'
      2. Assert: rendered ExternalSecret has secretStoreRef.name=aws-secrets-manager, kind=ClusterSecretStore
    Expected Result: ExternalSecret follows didoc pattern exactly
    Evidence: .sisyphus/evidence/task-5-external-secret.txt
  ```

  **Commit**: YES (groups with Commit 2)
  - Message: `feat(charts): add openmemory Helm chart v1.0.0`
  - Files: `charts/openmemory/1.0.0/templates/configmap.yaml`, `charts/openmemory/1.0.0/templates/external-secrets.yaml`

- [ ] 6. Gateway Templates — HTTPRoutes and SecurityPolicy

  **What to do**:
  - **Create `charts/openmemory/1.0.0/templates/httproute-protected.yaml`**:
    - OIDC-protected HTTPRoute for UI and API routes
    - `parentRefs` → shared gateway (`{{ .Values.gateway.sharedGateway.name }}` in `{{ .Values.gateway.sharedGateway.namespace }}`)
    - `hostnames: [{{ .Values.gateway.hostname }}]`
    - Rules:
      - Rule 1 (API): path prefix `/api/v1` → backendRef `api` service port 8765
      - Rule 2 (API docs): path prefix `/docs` OR `/redoc` OR `/openapi.json` → backendRef `api` service port 8765
      - Rule 3 (UI catch-all): path prefix `/` → backendRef `ui` service port 3000
    - Note: order matters — more specific paths first, catch-all last
  - **Create `charts/openmemory/1.0.0/templates/httproute-mcp.yaml`**:
    - UNPROTECTED HTTPRoute for MCP endpoints (machine clients can't do OIDC)
    - Same parentRefs as above (shared gateway)
    - Same hostname
    - Rules: path prefix `/mcp` → backendRef `api` service port 8765
    - NO SecurityPolicy targets this route
  - **Create `charts/openmemory/1.0.0/templates/securitypolicy.yaml`**:
    - Follow the EXACT pattern from `charts/didoc/12.0.0/templates/securitypolicy.yaml`
    - Only render if `{{ .Values.gateway.oidc.enabled }}`
    - `targetRef`: kind=HTTPRoute, name=the PROTECTED HTTPRoute name (not MCP route)
    - `oidc` section: provider (issuer, authorizationEndpoint, tokenEndpoint), clientID, clientSecret.name, redirectURL (`https://{{ hostname }}/oauth2/callback`), scopes, cookieNames, `forwardAccessToken: true`
    - `jwt` section: providers with Keycloak JWKS URI, claimToHeaders (preferred_username → X-Auth-Request-Preferred-Username, email → X-Auth-Request-Email)

  **Must NOT do**:
  - Do NOT create a SecurityPolicy targeting the MCP HTTPRoute
  - Do NOT create a dedicated Gateway resource (use shared)
  - Do NOT add ReferenceGrant (not needed with didoc Pattern A)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex EnvoyGateway routing with OIDC SecurityPolicy, requires understanding of path matching precedence and SecurityPolicy targeting
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 7)
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Task 2 (needs values schema for gateway section)

  **References**:

  **Pattern References**:
  - `charts/didoc/12.0.0/templates/securitypolicy.yaml` — EXACT SecurityPolicy pattern. Shows OIDC provider config, clientSecret reference, redirectURL construction, JWT claim-to-header mapping, cookie configuration. Replicate this structure for the openmemory protected route.
  - `charts/didoc/12.0.0/templates/gateway.yaml:36-63` — HTTPRoute with shared gateway parentRef pattern. Shows how to reference cross-namespace Gateway, hostname configuration, and backendRef to local Service.
  - `charts/didoc/12.0.0/templates/gateway.yaml:64-102` — Webhook HTTPRoute pattern (unprotected route alongside protected ones). This is the model for the MCP HTTPRoute — same gateway, same hostname, but NO SecurityPolicy.

  **External References**:
  - EnvoyGateway SecurityPolicy CRD: `gateway.envoyproxy.io/v1alpha1` kind SecurityPolicy — OIDC + JWT configuration
  - Gateway API HTTPRoute: `gateway.networking.k8s.io/v1` kind HTTPRoute — path matching, backendRef, parentRef

  **WHY Each Reference Matters**:
  - didoc SecurityPolicy: the exact OIDC+JWT pattern including claim-to-header mapping — critical for forwarding user identity to the API
  - didoc gateway.yaml (public route): shows how to attach an HTTPRoute to a shared gateway across namespaces
  - didoc gateway.yaml (webhook route): proves the pattern of having unprotected routes alongside OIDC-protected ones on the same hostname — exactly what we need for MCP

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Protected HTTPRoute covers UI and API paths
    Tool: Bash
    Preconditions: httproute-protected.yaml exists
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set gateway.hostname=memory.id.netcetera.com --set gateway.sharedGateway.name=envoy-gateway --set gateway.sharedGateway.namespace=nip-envoy-gateway
      2. Extract HTTPRoute named *-protected from output
      3. Assert: has rules for /api/v1, /docs, /redoc, / (catch-all)
      4. Assert: parentRef points to envoy-gateway in nip-envoy-gateway
      5. Assert: hostname is memory.id.netcetera.com
    Expected Result: Protected route covers all non-MCP paths
    Evidence: .sisyphus/evidence/task-6-httproute-protected.txt

  Scenario: MCP HTTPRoute is separate and unprotected
    Tool: Bash
    Preconditions: httproute-mcp.yaml exists
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set gateway.hostname=memory.id.netcetera.com
      2. Extract HTTPRoute named *-mcp from output
      3. Assert: has rule for /mcp path prefix
      4. Assert: backendRef is api service port 8765
    Expected Result: MCP route exists as a separate HTTPRoute
    Evidence: .sisyphus/evidence/task-6-httproute-mcp.txt

  Scenario: SecurityPolicy targets ONLY the protected HTTPRoute
    Tool: Bash
    Preconditions: securitypolicy.yaml exists, gateway.oidc.enabled=true
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set gateway.oidc.enabled=true --set gateway.oidc.issuer=https://test --set gateway.oidc.authorizationEndpoint=https://test/auth --set gateway.oidc.tokenEndpoint=https://test/token --set gateway.oidc.clientId=test --set gateway.oidc.clientSecretRef=test-secret --set gateway.hostname=memory.id.netcetera.com
      2. Extract SecurityPolicy from output
      3. Assert: targetRef.name contains "protected" (NOT "mcp")
      4. Assert: redirectURL is "https://memory.id.netcetera.com/oauth2/callback"
    Expected Result: OIDC only applies to protected route, not MCP
    Failure Indicators: targetRef references the MCP route name
    Evidence: .sisyphus/evidence/task-6-securitypolicy-target.txt

  Scenario: SecurityPolicy NOT rendered when oidc.enabled=false
    Tool: Bash
    Preconditions: securitypolicy.yaml has conditional
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set gateway.oidc.enabled=false
      2. grep "SecurityPolicy" from output
      3. Assert: no SecurityPolicy resource in output
    Expected Result: OIDC disabled = no SecurityPolicy
    Evidence: .sisyphus/evidence/task-6-oidc-disabled.txt
  ```

  **Commit**: YES (groups with Commit 2)
  - Message: `feat(charts): add openmemory Helm chart v1.0.0`
  - Files: `charts/openmemory/1.0.0/templates/httproute-protected.yaml`, `httproute-mcp.yaml`, `securitypolicy.yaml`

- [ ] 7. ALB Ingress Template for ExternalDNS

  **What to do**:
  - **Create `charts/openmemory/1.0.0/templates/alb-ingress.yaml`**:
    - Only render if `{{ .Values.gateway.albIngress.enabled }}`
    - Creates an Ingress resource in `{{ .Values.gateway.albIngress.namespace }}` (typically `nip-envoy-gateway`)
    - This Ingress is NOT for actual traffic routing — it exists solely for ExternalDNS to discover the hostname and create Route53 DNS records
    - Backend: `{{ .Values.gateway.albIngress.serviceName }}:{{ .Values.gateway.albIngress.servicePort }}`
    - Host: `{{ .Values.gateway.hostname }}`
    - Annotations from `{{ .Values.gateway.albIngress.annotations }}`
    - Standard labels

  **Must NOT do**:
  - Do NOT make this the primary routing mechanism (EnvoyGateway HTTPRoutes handle routing)
  - Do NOT add OIDC annotations to this Ingress (OIDC is handled by SecurityPolicy)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single template file, simple conditional Ingress
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6)
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Task 2

  **References**:

  **Pattern References**:
  - `charts/didoc/12.0.0/values.yaml:31-42` — ALB Ingress values schema showing the `albIngress.enabled`, `namespace`, `serviceName`, `servicePort`, `annotations` pattern
  - `charts/idaas-portal/1.0.0/templates/public-route.yaml` — Shows cross-namespace resource creation pattern. The ALB Ingress is created in `nip-envoy-gateway` namespace, not the app namespace.
  - `deployments/dev-silver/didoc-public/values.yaml:14-28` — Real ALB annotations used in production (group.name, load-balancer-name, scheme, target-type, ssl-redirect, wafv2-acl-arn)

  **WHY Each Reference Matters**:
  - didoc ALB Ingress values: the exact values schema to replicate for consistency
  - idaas-portal: proves cross-namespace resource creation is used in this repo
  - didoc-public values: shows real ALB annotations needed for ExternalDNS + WAF + SSL

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: ALB Ingress renders when enabled
    Tool: Bash
    Preconditions: alb-ingress.yaml exists
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set gateway.albIngress.enabled=true --set gateway.hostname=memory.id.netcetera.com --set gateway.albIngress.namespace=nip-envoy-gateway
      2. Extract Ingress from output
      3. Assert: host is memory.id.netcetera.com, metadata.namespace is nip-envoy-gateway
    Expected Result: Ingress created in gateway namespace for ExternalDNS
    Evidence: .sisyphus/evidence/task-7-alb-ingress.txt

  Scenario: ALB Ingress NOT rendered when disabled
    Tool: Bash
    Preconditions: alb-ingress.yaml has conditional
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ --set gateway.albIngress.enabled=false
      2. grep "kind: Ingress" from output
      3. Assert: no Ingress in output
    Expected Result: No Ingress when disabled
    Evidence: .sisyphus/evidence/task-7-no-ingress.txt
  ```

  **Commit**: YES (groups with Commit 2)
  - Message: `feat(charts): add openmemory Helm chart v1.0.0`
  - Files: `charts/openmemory/1.0.0/templates/alb-ingress.yaml`

- [ ] 8. Dev-Silver Deployment Values

  **What to do**:
  - **Create `deployments/dev-silver/openmemory/app-config.yaml`**:
    ```yaml
    chart:
      name: openmemory
      version: 1.0.0
    ```
  - **Create `deployments/dev-silver/openmemory/values.yaml`** with environment-specific overrides:
    ```yaml
    api:
      image:
        repository: 230970045646.dkr.ecr.eu-central-1.amazonaws.com/openmemory-api
        digest: ""  # to be filled after first image build
      replicas: 1
      user: "openmemory"
    ui:
      image:
        repository: 230970045646.dkr.ecr.eu-central-1.amazonaws.com/openmemory-ui
        digest: ""  # to be filled after first image build
      replicas: 1
    database:
      host: ""  # Aurora endpoint — to be filled after RDS provisioning
      port: "5432"
      name: "openmemory"
      user: "openmemory"
      sslmode: "require"
    qdrant:
      enabled: true
      image:
        repository: qdrant/qdrant
        tag: latest
      replicas: 1
      port: 6333
      resources:
        requests:
          cpu: 100m
          memory: 256Mi
        limits:
          cpu: 500m
          memory: 1Gi
      persistence:
        enabled: true
        size: 10Gi
    gateway:
      create: false
      sharedGateway:
        name: envoy-gateway
        namespace: nip-envoy-gateway
        sectionName: https
      hostname: "memory.id.netcetera.com"
      oidc:
        enabled: true
        issuer: ""  # https://prev-silver-mercury.../realms/vsdi_integration — verify via kubectl
        authorizationEndpoint: ""  # {issuer}/protocol/openid-connect/auth
        tokenEndpoint: ""  # {issuer}/protocol/openid-connect/token
        clientId: "openmemory"
        clientSecretRef: "openmemory-oidc-client-secret"
      albIngress:
        enabled: true
        namespace: nip-envoy-gateway
        serviceName: envoy-service
        servicePort: https-443
        annotations:
          alb.ingress.kubernetes.io/group.name: nip-dev-silver.general
          alb.ingress.kubernetes.io/load-balancer-name: nip-dev-silver-alb
          alb.ingress.kubernetes.io/scheme: internet-facing
          alb.ingress.kubernetes.io/target-type: ip
          alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}, {"HTTP":80}]'
          alb.ingress.kubernetes.io/ssl-redirect: "443"
    externalSecrets:
      - targetSecretName: openmemory-oidc-client-secret
        awsSecretName: /nip/keycloak/prev-silver-mercury/vsdi_integration/client-secret/openmemory
        dataTemplate:
          client-secret: "{{ .secret }}"
      - targetSecretName: openmemory-openai
        awsSecretName: /nip/openmemory/openai-api-key
        dataTemplate:
          apiKey: "{{ .apiKey }}"
      - targetSecretName: openmemory-database
        awsSecretName: /nip/openmemory/database
        dataTemplate:
          host: "{{ .host }}"
          port: "{{ .port }}"
          dbname: "{{ .dbname }}"
          username: "{{ .username }}"
          password: "{{ .password }}"
          DATABASE_URL: "postgresql://{{ .username }}:{{ .password }}@{{ .host }}:{{ .port }}/{{ .dbname }}?sslmode=require"
    ```
  - Add inline YAML comments documenting:
    - Which values need to be filled after prerequisites are done (marked with `# TODO: fill after ...`)
    - The OIDC issuer URL pattern and how to verify via kubectl
    - The ExternalSecret AWS paths and what keys they expect

  **Must NOT do**:
  - Do NOT fill in actual secret values
  - Do NOT hardcode the Aurora endpoint (it's a prerequisite)
  - Do NOT add values not defined in the chart's values.yaml schema

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Two YAML files with environment-specific values, following established patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 9)
  - **Blocks**: Task 9 (validation needs deployment values)
  - **Blocked By**: Tasks 3, 4, 5, 6, 7 (needs chart structure complete)

  **References**:

  **Pattern References**:
  - `deployments/dev-silver/didoc-public/app-config.yaml` — Exact format: `chart.name` + `chart.version`. Must match the chart directory name.
  - `deployments/dev-silver/didoc-public/values.yaml` — Full production deployment values example. Shows image with digest, ALB annotations, OIDC config, ExternalSecrets with dataTemplate, CiliumNetworkPolicy. Use this as the model for openmemory values.
  - `deployments/dev-silver/keycloak/values.yaml` — Shows externalDatabase configuration pattern for an RDS-backed deployment.

  **WHY Each Reference Matters**:
  - didoc-public app-config: ArgoCD ApplicationSet scans this exact format to discover and deploy apps
  - didoc-public values: the production-ready values pattern including all ALB, OIDC, and ExternalSecret configurations
  - keycloak values: shows how a real app references external RDS database credentials

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: app-config.yaml has correct chart reference
    Tool: Bash
    Preconditions: deployments/dev-silver/openmemory/app-config.yaml exists
    Steps:
      1. python -c "import yaml; d=yaml.safe_load(open('deployments/dev-silver/openmemory/app-config.yaml')); assert d['chart']['name']=='openmemory'; assert d['chart']['version']=='1.0.0'; print('OK')"
    Expected Result: Chart name=openmemory, version=1.0.0
    Evidence: .sisyphus/evidence/task-8-app-config.txt

  Scenario: values.yaml has all required sections
    Tool: Bash
    Preconditions: deployments/dev-silver/openmemory/values.yaml exists
    Steps:
      1. grep -c "gateway:" deployments/dev-silver/openmemory/values.yaml
      2. grep -c "externalSecrets:" deployments/dev-silver/openmemory/values.yaml
      3. grep -c "oidc:" deployments/dev-silver/openmemory/values.yaml
      4. grep "memory.id.netcetera.com" deployments/dev-silver/openmemory/values.yaml
      5. Assert: all greps return ≥1
    Expected Result: All sections present with correct hostname
    Evidence: .sisyphus/evidence/task-8-values-sections.txt

  Scenario: ExternalSecrets define all 3 required secrets
    Tool: Bash
    Preconditions: values.yaml exists
    Steps:
      1. grep -c "targetSecretName:" deployments/dev-silver/openmemory/values.yaml
      2. Assert: count is 3 (oidc, openai, database)
    Expected Result: Three ExternalSecrets configured
    Evidence: .sisyphus/evidence/task-8-external-secrets.txt
  ```

  **Commit**: YES (Commit 4)
  - Message: `feat(deployments): add openmemory dev-silver deployment config`
  - Files: `deployments/dev-silver/openmemory/app-config.yaml`, `deployments/dev-silver/openmemory/values.yaml`

- [ ] 9. Full Chart Validation — Helm Lint + Template Rendering

  **What to do**:
  - **Run `helm lint`**:
    - `helm lint charts/openmemory/1.0.0/` — basic chart validation
    - Fix any warnings or errors
  - **Run `helm template` with dev-silver values**:
    - `helm template openmemory charts/openmemory/1.0.0/ -f deployments/dev-silver/openmemory/values.yaml`
    - Verify all resources render correctly
  - **Validate rendered resources**:
    - Count resources: expect 2 Deployments, 1 StatefulSet, 3 Services, 1 ConfigMap, 3 ExternalSecrets, 2 HTTPRoutes, 1 SecurityPolicy, 1 Ingress (ALB)
    - Verify API Deployment has init container (alembic migration)
    - Verify UI Deployment has `NEXT_PUBLIC_API_URL=https://memory.id.netcetera.com`
    - Verify Qdrant StatefulSet has PVC with volumeClaimTemplates
    - Verify API env vars include `QDRANT_HOST` and `QDRANT_PORT` pointing to in-cluster Qdrant service
    - Verify API env vars include `DATABASE_URL` from Secret (PostgreSQL connection string for history/metadata)
    - Verify SecurityPolicy targets the protected HTTPRoute name only
    - Verify MCP HTTPRoute has NO SecurityPolicy targeting it
    - Verify ExternalSecrets reference `aws-secrets-manager` ClusterSecretStore
    - Verify no sensitive values appear in ConfigMap
  - **Cross-reference env vars**:
    - API pod: `DATABASE_URL` (from Secret — Aurora PostgreSQL for history/metadata), `OPENAI_API_KEY` (from Secret), `QDRANT_HOST`/`QDRANT_PORT` (from ConfigMap — in-cluster Qdrant), all others from ConfigMap
    - UI pod: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_USER_ID`, `PORT`, `HOSTNAME`
  - **Fix any issues found** — iterate until clean

  **Must NOT do**:
  - Do NOT deploy to the actual cluster (dry-run only)
  - Do NOT modify values beyond fixing template bugs

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Comprehensive validation requiring inspection of rendered YAML, cross-referencing multiple resources, and potentially fixing template issues
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 8 — but depends on Task 8 for values file)
  - **Blocks**: Final Verification (F1-F4)
  - **Blocked By**: Tasks 1, 4, 5, 6, 7, 8 (needs all chart files + deployment values)

  **References**:

  **Pattern References**:
  - All chart template files created in Tasks 2-7
  - `deployments/dev-silver/openmemory/values.yaml` from Task 8
  - `openmemory/api/app/utils/memory.py` — verify Qdrant env vars (`QDRANT_HOST`, `QDRANT_PORT`) match ConfigMap keys
  - `openmemory/api/app/database.py` — verify DATABASE_URL format matches what the API expects
  - `openmemory/ui/entrypoint.sh` — verify NEXT_PUBLIC_* vars are set on the UI pod

  **WHY Each Reference Matters**:
  - Template files: this task validates all templates work together as a coherent chart
  - Deployment values: real-world values to test template rendering
  - Source code files: verify the env vars in templates match what the application actually reads

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: helm lint passes
    Tool: Bash
    Preconditions: complete chart at charts/openmemory/1.0.0/
    Steps:
      1. helm lint charts/openmemory/1.0.0/
      2. Assert: exit code 0, output contains "0 chart(s) failed"
    Expected Result: No lint errors
    Evidence: .sisyphus/evidence/task-9-helm-lint.txt

  Scenario: helm template renders all expected resources
    Tool: Bash
    Preconditions: chart + deployment values exist
    Steps:
      1. helm template openmemory charts/openmemory/1.0.0/ -f deployments/dev-silver/openmemory/values.yaml > /tmp/rendered.yaml
      2. grep -c "kind: Deployment" /tmp/rendered.yaml → expect 2
      3. grep -c "kind: StatefulSet" /tmp/rendered.yaml → expect 1
      4. grep -c "kind: Service" /tmp/rendered.yaml → expect 3
      5. grep -c "kind: ConfigMap" /tmp/rendered.yaml → expect 1
      6. grep -c "kind: ExternalSecret" /tmp/rendered.yaml → expect 3
      7. grep -c "kind: HTTPRoute" /tmp/rendered.yaml → expect 2
      8. grep -c "kind: SecurityPolicy" /tmp/rendered.yaml → expect 1
      9. grep -c "kind: Ingress" /tmp/rendered.yaml → expect 1
    Expected Result: Exact resource counts match (2 Deployments + 1 StatefulSet + 3 Services + ...)
    Failure Indicators: Wrong count for any resource type
    Evidence: .sisyphus/evidence/task-9-resource-counts.txt

  Scenario: SecurityPolicy does NOT target MCP route
    Tool: Bash
    Preconditions: rendered.yaml exists
    Steps:
      1. Extract SecurityPolicy targetRef.name from /tmp/rendered.yaml
      2. Assert: name contains "protected", NOT "mcp"
    Expected Result: OIDC only on protected routes
    Evidence: .sisyphus/evidence/task-9-security-target.txt

  Scenario: Sensitive values NOT in ConfigMap
    Tool: Bash
    Preconditions: rendered.yaml exists
    Steps:
      1. Extract ConfigMap data section
      2. Assert: does NOT contain strings "OPENAI_API_KEY", "PASSWORD", "DATABASE_URL", "client-secret"
    Expected Result: All secrets in ExternalSecrets, not ConfigMap
    Evidence: .sisyphus/evidence/task-9-no-secret-leak.txt
  ```

  **Commit**: NO (validation task — fixes committed as amendments to Commit 2)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
>
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, check rendered manifests). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Review all chart templates for: valid YAML, proper Helm templating, consistent label patterns, correct indentation. Review code patches for: Python syntax, no regressions. Run `helm lint` and `helm template`. Check for common Helm anti-patterns (hardcoded values, missing defaults, template errors).
  Output: `Lint [PASS/FAIL] | Template [PASS/FAIL] | Templates [N clean/N issues] | VERDICT`

- [ ] F3. **Real QA** — `unspecified-high`
  Run `helm template openmemory charts/openmemory/1.0.0/ -f deployments/dev-silver/openmemory/values.yaml` and validate every rendered resource: correct apiVersion, metadata, spec fields, env var references, port numbers, volume mounts, probes. Verify SecurityPolicy targets correct HTTPRoute name. Verify ExternalSecret references match ClusterSecretStore pattern.
  Output: `Resources [N/N valid] | Env Vars [N/N correct] | Routing [N/N correct] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual files created. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect unaccounted changes. Flag any file outside the expected paths.
  Output: `Tasks [N/N compliant] | Scope [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Commit | Message | Files | Pre-commit Check |
|--------|---------|-------|-----------------|
| 1 | `fix(openmemory): make database.py PostgreSQL-safe, add /healthz, configurable CORS` | `api/app/database.py`, `api/app/routers/health.py`, `api/main.py` | `python -c "from app.database import engine"` |
| 2 | `feat(charts): add openmemory Helm chart v1.0.0` | `charts/openmemory/1.0.0/*` | `helm lint charts/openmemory/1.0.0/` |
| 3 | `feat(argocd): add ApplicationSet for nip-ai-memory namespace` | `argocd/nip-non-prod/applications/dev-silver-ai-memory.yaml` | YAML validation |
| 4 | `feat(deployments): add openmemory dev-silver deployment config` | `deployments/dev-silver/openmemory/*` | `helm template` with values |

---

## Success Criteria

### Verification Commands
```bash
# Chart linting
helm lint charts/openmemory/1.0.0/
# Expected: 0 errors

# Template rendering with dev-silver values
helm template openmemory charts/openmemory/1.0.0/ -f deployments/dev-silver/openmemory/values.yaml
# Expected: Valid YAML with 2 Deployments, 2 Services, 1 ConfigMap, 2+ ExternalSecrets, 2 HTTPRoutes, 1 SecurityPolicy

# Code patch validation (from openmemory/api/ directory)
DATABASE_URL=postgresql://test:test@localhost:5432/test python -c "from app.database import engine; print('OK')"
# Expected: OK (no check_same_thread error)
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] Chart renders without errors
- [ ] Code patches don't break SQLite mode
- [ ] SecurityPolicy targets protected HTTPRoute only
- [ ] MCP HTTPRoute has no SecurityPolicy
- [ ] All sensitive values come from ExternalSecrets, not ConfigMap

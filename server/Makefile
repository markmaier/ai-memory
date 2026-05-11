.PHONY: up down clean logs seed wait-api wait-dashboard bootstrap health build run_local reset-admin-password prune-logs \
        ecr-login build-api build-dashboard build-mcp build-all push-api push-dashboard push-mcp push-all deploy-api deploy-dashboard deploy-mcp deploy-all \
        ecr-cleanup

OUTPUT ?= text
API_URL ?= http://localhost:8888
DASHBOARD_URL ?= http://localhost:3000

# --- ECR image build settings ---
ECR_REGISTRY ?= 230970045646.dkr.ecr.eu-central-1.amazonaws.com
ECR_REPO     ?= $(ECR_REGISTRY)/nca-497-5/ai-memory
AWS_REGION   ?= eu-central-1
TAG_API      ?= api
TAG_DASHBOARD ?= dashboard
TAG_MCP      ?= mcp

# Temporary Docker config so ECR credentials never touch ~/.docker/config.json
ECR_DOCKER_CONFIG := /tmp/mem0-ecr-docker-config
DOCKER_CFG        = DOCKER_CONFIG=$(ECR_DOCKER_CONFIG)
BUILDX_BUILDER   ?= mem0-builder

up:
	@for port in 3000 8888; do \
		if lsof -iTCP:$$port -sTCP:LISTEN >/dev/null 2>&1; then \
			echo "error: port $$port is already in use."; \
			echo "find the owning process with: lsof -iTCP:$$port -sTCP:LISTEN"; \
			exit 1; \
		fi; \
	done
	docker compose up -d --build
	@$(MAKE) --no-print-directory wait-api
	@$(MAKE) --no-print-directory wait-dashboard
	@echo ""
	@echo "Stack is ready."
	@echo "  Dashboard:  $(DASHBOARD_URL)  <- open this to run the setup wizard"
	@echo "  API:        $(API_URL)"

down:
	docker compose down

clean:
	docker compose down -v

logs:
	docker compose logs -f

seed:
	@API_URL="$(API_URL)" DASHBOARD_URL="$(DASHBOARD_URL)" EMAIL="$(EMAIL)" PASSWORD="$(PASSWORD)" NAME="$(NAME)" OUTPUT="$(OUTPUT)" ./scripts/seed.sh

wait-api:
	@echo "Waiting for API..."
	@until curl -fsS "$(API_URL)/auth/setup-status" >/dev/null 2>&1; do sleep 2; done

wait-dashboard:
	@echo "Waiting for dashboard..."
	@until curl -fsS "$(DASHBOARD_URL)/api/health" >/dev/null 2>&1; do sleep 2; done

bootstrap: up wait-api wait-dashboard seed

health:
	@echo "API:       $$(curl -s -o /dev/null -w '%{http_code}' "$(API_URL)/docs")"
	@echo "Dashboard: $$(curl -s -o /dev/null -w '%{http_code}' "$(DASHBOARD_URL)/api/health")"
	@echo "Postgres:  $$(docker compose exec -T postgres pg_isready -q && echo 'ok' || echo 'down')"

reset-admin-password:
	@test -n "$(EMAIL)" || (echo "usage: make reset-admin-password EMAIL=<email> PASSWORD=<password>" && exit 2)
	@test -n "$(PASSWORD)" || (echo "usage: make reset-admin-password EMAIL=<email> PASSWORD=<password>" && exit 2)
	@docker compose exec -T -e EMAIL="$(EMAIL)" -e PASSWORD="$(PASSWORD)" -e PYTHONPATH=/app mem0 python scripts/reset_admin_password.py

prune-logs:
	@docker compose exec -T -e REQUEST_LOG_RETENTION_DAYS="$(REQUEST_LOG_RETENTION_DAYS)" -e PYTHONPATH=/app mem0 python scripts/prune_request_logs.py

build:
	docker build -t mem0-api-server .

run_local:
	docker run -p 8000:8000 -v $(shell pwd):/app mem0-api-server --env-file .env

# --- ECR image build & push (buildx, cross-platform) ---
PLATFORM ?= linux/arm64

ecr-login:
	@mkdir -p $(ECR_DOCKER_CONFIG)
	@ln -sfn $(HOME)/.docker/cli-plugins $(ECR_DOCKER_CONFIG)/cli-plugins
	@ln -sfn $(HOME)/.docker/buildx $(ECR_DOCKER_CONFIG)/buildx
	@TOKEN=$$(aws ecr get-login-password --region $(AWS_REGION)) && \
		AUTH=$$(printf 'AWS:%s' "$$TOKEN" | base64 | tr -d '\n') && \
		printf '{"credsStore":"","auths":{"%s":{"auth":"%s"}}}\n' "$(ECR_REGISTRY)" "$$AUTH" \
			> $(ECR_DOCKER_CONFIG)/config.json && \
		echo "Logged in to $(ECR_REGISTRY) (credentials in $(ECR_DOCKER_CONFIG))"

ecr-cleanup:
	@rm -rf $(ECR_DOCKER_CONFIG)
	@echo "Cleaned up temporary Docker credentials."

build-api:
	$(DOCKER_CFG) docker buildx build --builder $(BUILDX_BUILDER) --platform $(PLATFORM) \
		-f Dockerfile.eks -t $(ECR_REPO):$(TAG_API) .

build-dashboard:
	$(DOCKER_CFG) docker buildx build --builder $(BUILDX_BUILDER) --platform $(PLATFORM) \
		-f dashboard/Dockerfile.eks -t $(ECR_REPO):$(TAG_DASHBOARD) dashboard/

build-mcp:
	$(DOCKER_CFG) docker buildx build --builder $(BUILDX_BUILDER) --platform $(PLATFORM) \
		-f ../mcp/Dockerfile -t $(ECR_REPO):$(TAG_MCP) ../mcp/

build-all: build-api build-dashboard build-mcp

push-api:
	$(DOCKER_CFG) docker push $(ECR_REPO):$(TAG_API)

push-dashboard:
	$(DOCKER_CFG) docker push $(ECR_REPO):$(TAG_DASHBOARD)

push-mcp:
	$(DOCKER_CFG) docker push $(ECR_REPO):$(TAG_MCP)

push-all: push-api push-dashboard push-mcp

deploy-api: ecr-login
	$(DOCKER_CFG) docker buildx build --builder $(BUILDX_BUILDER) --platform $(PLATFORM) \
		-f Dockerfile.eks -t $(ECR_REPO):$(TAG_API) --push .

deploy-dashboard: ecr-login
	$(DOCKER_CFG) docker buildx build --builder $(BUILDX_BUILDER) --platform $(PLATFORM) \
		-f dashboard/Dockerfile.eks -t $(ECR_REPO):$(TAG_DASHBOARD) --push dashboard/

deploy-mcp: ecr-login
	$(DOCKER_CFG) docker buildx build --builder $(BUILDX_BUILDER) --platform $(PLATFORM) \
		-f ../mcp/Dockerfile -t $(ECR_REPO):$(TAG_MCP) --push ../mcp/

deploy-all: ecr-login
	@$(MAKE) --no-print-directory deploy-api
	@$(MAKE) --no-print-directory deploy-dashboard
	@$(MAKE) --no-print-directory deploy-mcp
	@$(MAKE) --no-print-directory ecr-cleanup

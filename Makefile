# ═══════════════════════════════════════════════════════════════════════
#  MindVault — Makefile
#  Usage: make <target>
#  Run 'make help' to see all available commands.
# ═══════════════════════════════════════════════════════════════════════

.PHONY: help setup dev test test-smoke lint format typecheck \
        build push clean db-init \
        docker-dev docker-prod docker-test \
        k8s-apply k8s-rollout k8s-status k8s-logs k8s-delete

# ── Config ────────────────────────────────────────────────────────────
PYTHON      = python
PIP         = pip
PYTEST      = pytest
IMAGE_NAME  = mindvault
IMAGE_TAG   = latest
REGISTRY    = ghcr.io/YOUR_ORG
K8S_NS      = mindvault

# ── Help ─────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  MindVault — Available Commands"
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  Local Development"
	@echo "    make setup          Create venv, install deps, copy .env"
	@echo "    make dev            Start server with hot-reload"
	@echo "    make db-init        Initialise SQLite database"
	@echo ""
	@echo "  Testing"
	@echo "    make test           Run unit tests"
	@echo "    make test-smoke     Run smoke test (mocked APIs)"
	@echo "    make test-cov       Run tests with coverage report"
	@echo ""
	@echo "  Code Quality"
	@echo "    make lint           Run ruff linter"
	@echo "    make format         Run black formatter"
	@echo "    make typecheck      Run mypy"
	@echo ""
	@echo "  Docker"
	@echo "    make docker-dev     Run dev stack (hot-reload)"
	@echo "    make docker-prod    Run production stack"
	@echo "    make docker-test    Run test suite in Docker"
	@echo "    make build          Build production Docker image"
	@echo "    make push           Push image to registry"
	@echo ""
	@echo "  Kubernetes"
	@echo "    make k8s-apply      Apply all K8s manifests"
	@echo "    make k8s-rollout    Watch rolling deploy status"
	@echo "    make k8s-status     Show pod/service status"
	@echo "    make k8s-logs       Tail application logs"
	@echo "    make k8s-delete     Delete all K8s resources"
	@echo ""
	@echo "    make clean          Remove build artifacts + caches"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────
setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@if [ ! -f config/.env ]; then \
		cp config/.env.example config/.env; \
		echo "✅  config/.env created — fill in your API keys"; \
	fi
	mkdir -p data logs
	@echo "✅  Setup complete. Activate: source .venv/bin/activate"

# ── Local dev ────────────────────────────────────────────────────────
db-init:
	$(PYTHON) scripts/init_db.py

dev: db-init
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# ── Testing ───────────────────────────────────────────────────────────
test:
	$(PYTEST) tests/unit/ -v

test-smoke:
	$(PYTHON) scripts/smoke_test.py

test-cov:
	$(PYTEST) tests/unit/ -v \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=60
	@echo "Coverage report: htmlcov/index.html"

# ── Code quality ──────────────────────────────────────────────────────
lint:
	ruff check app/ tests/ scripts/

format:
	black app/ tests/ scripts/
	ruff check --fix app/ tests/ scripts/

typecheck:
	mypy app/

check: lint typecheck test
	@echo "✅  All checks passed"

# ── Docker: local ────────────────────────────────────────────────────
docker-dev:
	docker compose -f docker-compose.dev.yml up --build

docker-prod:
	docker compose up --build -d
	@echo "✅  Production stack running at http://localhost:8000"

docker-test:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
	docker compose -f docker-compose.test.yml down

docker-down:
	docker compose down
	docker compose -f docker-compose.dev.yml down

# ── Docker: build + push ─────────────────────────────────────────────
build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "✅  Image built: $(IMAGE_NAME):$(IMAGE_TAG)"

push: build
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)

# ── Kubernetes ───────────────────────────────────────────────────────
k8s-apply:
	kubectl apply -f deploy/k8s/namespace.yaml
	kubectl apply -f deploy/k8s/configmap.yaml
	kubectl apply -f deploy/k8s/secret.yaml
	kubectl apply -f deploy/k8s/service.yaml
	kubectl apply -f deploy/k8s/deployment.yaml
	@echo "✅  K8s manifests applied"

k8s-rollout:
	kubectl rollout status deployment/mindvault -n $(K8S_NS) --timeout=300s

k8s-status:
	kubectl get pods,svc,ingress,hpa -n $(K8S_NS)

k8s-logs:
	kubectl logs -f -l app=mindvault -n $(K8S_NS) --tail=100

k8s-delete:
	kubectl delete namespace $(K8S_NS)

# ── Cleanup ───────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf dist build *.egg-info
	@echo "✅  Cleaned"

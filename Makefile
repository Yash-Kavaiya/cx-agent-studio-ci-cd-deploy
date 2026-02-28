.PHONY: help install install-dev lint format test validate deploy-staging deploy-production clean

PYTHON := python3
PIP := pip

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	$(PIP) install -r requirements-dev.txt

lint: ## Run linter
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format: ## Format code
	ruff format src/ tests/

test: ## Run tests with coverage
	pytest tests/ --cov=src --cov-report=term-missing -v

validate: ## Validate all configurations
	$(PYTHON) -m src.cli validate-configs
	$(PYTHON) -m src.cli validate-agent-template

export-agent: ## Export agent (requires GCP_PROJECT_ID and CES_APP_ID)
	$(PYTHON) -m src.cli export-agent \
		--project-id=$${GCP_PROJECT_ID} \
		--app-id=$${CES_APP_ID} \
		--output-dir=agents/exported

deploy-staging: ## Deploy to staging
	DEPLOY_ENV=staging bash scripts/deploy.sh

deploy-production: ## Deploy to production
	DEPLOY_ENV=production bash scripts/deploy.sh

setup-gcp: ## Setup GCP project for CI/CD
	bash scripts/setup_gcp.sh

docker-build: ## Build Docker image
	docker build -t cx-agent-studio-cicd .

docker-run: ## Run CLI in Docker
	docker compose run --rm cx-agent-cicd $(CMD)

clean: ## Clean up generated files
	rm -rf agents/exported agents/backup
	rm -rf __pycache__ src/__pycache__ tests/__pycache__
	rm -rf .pytest_cache .coverage coverage.xml test-results.xml
	rm -rf dist build *.egg-info

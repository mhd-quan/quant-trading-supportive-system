# Crypto Research Platform Makefile

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# Setup
.PHONY: install
install: ## Install dependencies
	uv pip install -e ".[dev]"
	pre-commit install

.PHONY: init-db
init-db: ## Initialize DuckDB and create schemas
	python scripts/init_database.py

# Development
.PHONY: format
format: ## Format code with black and ruff
	black src/ tests/ scripts/
	ruff check --fix src/ tests/ scripts/

.PHONY: lint
lint: ## Lint code with ruff and mypy
	ruff check src/ tests/ scripts/
	mypy src/

.PHONY: test
test: ## Run unit tests
	pytest tests/unit -v

.PHONY: test-integration
test-integration: ## Run integration tests (requires .env)
	pytest tests/integration -v

.PHONY: test-all
test-all: ## Run all tests with coverage
	pytest tests/ --cov=src --cov-report=term-missing --cov-report=html

.PHONY: security-audit
security-audit: ## Run security checks
	bandit -r src/
	safety check
	pip-audit

# Data Management
.PHONY: backfill-btc
backfill-btc: ## Backfill BTC/USDT data for 30 days
	python scripts/backfill.py --exchange binance --symbol BTC/USDT --timeframe 1h --days 30

.PHONY: validate-data
validate-data: ## Validate data integrity
	python scripts/validate_data.py

.PHONY: compact-parquet
compact-parquet: ## Compact Parquet files
	python scripts/compact_parquet.py

# Running Services
.PHONY: ui
ui: ## Start Streamlit UI
	streamlit run src/ui/app.py

.PHONY: stream
stream: ## Start live streaming
	python scripts/live.py --config configs/streaming.yaml

.PHONY: scheduler
scheduler: ## Start Prefect scheduler
	prefect server start

# Docker
.PHONY: docker-build
docker-build: ## Build Docker image
	docker build -t crypto-research:latest .

.PHONY: docker-run
docker-run: ## Run Docker container
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/.env:/app/.env:ro \
		-p 8501:8501 \
		crypto-research:latest

# Cleanup
.PHONY: clean
clean: ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/

.PHONY: clean-data
clean-data: ## Clean data files (CAUTION: Deletes all data)
	@echo "WARNING: This will delete all data files."
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf data/lake/*
	rm -f data/crypto.duckdb

# Documentation
.PHONY: docs
docs: ## Generate API documentation
	pdoc --html --output-dir docs/api src

.PHONY: serve-docs
serve-docs: ## Serve documentation locally
	python -m http.server 8080 --directory docs/

# Deployment
.PHONY: deploy-check
deploy-check: ## Pre-deployment checks
	@echo "Running deployment checks..."
	@make lint
	@make test-all
	@make security-audit
	@echo "✓ All checks passed"

.PHONY: backup
backup: ## Backup database and configs
	@mkdir -p backups/$(shell date +%Y%m%d)
	cp data/crypto.duckdb backups/$(shell date +%Y%m%d)/
	cp -r configs/ backups/$(shell date +%Y%m%d)/
	tar -czf backups/backup-$(shell date +%Y%m%d-%H%M%S).tar.gz \
		backups/$(shell date +%Y%m%d)/
	@echo "Backup created: backups/backup-$(shell date +%Y%m%d-%H%M%S).tar.gz"

# Development Shortcuts
.PHONY: dev
dev: ## Start development environment
	@make format
	@make lint
	@make test
	@make ui

.PHONY: quick
quick: ## Quick format and test
	@black src/ tests/ --check
	@ruff check src/ tests/
	@pytest tests/unit -x

# CI/CD Commands
.PHONY: ci
ci: ## Run CI pipeline
	@make install
	@make lint
	@make test-all
	@make security-audit

# Default target
.DEFAULT_GOAL := help

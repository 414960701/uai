PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_UAI := $(VENV)/bin/uai-forge

.DEFAULT_GOAL := help

.PHONY: help install install-backend install-frontend dev-backend dev-frontend \
	doctor test test-backend test-frontend lint typecheck build compose-config \
	compose-up compose-down compose-logs docker-build container-smoke clean

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "; printf "UAI Forge commands:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel

install: install-backend install-frontend ## Install all development dependencies

install-backend: $(VENV_PYTHON) ## Install the Python runtime and test dependencies
	$(VENV_PYTHON) -m pip install -e 'backend[dev]'

install-frontend: ## Install the locked frontend dependencies
	npm ci

dev-backend: ## Run the control API at http://127.0.0.1:8000
	$(VENV_UAI) serve --host 127.0.0.1 --port 8000

dev-frontend: ## Run the control center at http://localhost:3000
	npm run dev

doctor: ## Check storage initialization and plugin discovery
	$(VENV_UAI) doctor

test: test-backend test-frontend ## Run every automated test

test-backend: ## Run backend tests
	$(VENV_PYTHON) -m pytest backend/tests -q

test-frontend: ## Build and run frontend rendering tests
	npm test

lint: ## Lint the frontend
	npm run lint

typecheck: ## Type-check the frontend
	npm run typecheck

build: ## Build the frontend production bundle
	npm run build

compose-config: ## Validate the Compose model
	docker compose config --quiet

compose-up: ## Build and start the local container stack
	docker compose up --build -d

compose-down: ## Stop containers while retaining SQLite data
	docker compose down

compose-logs: ## Follow local container logs
	docker compose logs --follow

docker-build: ## Build both production container images
	docker compose build

container-smoke: ## Build, start, health-check, and verify fresh database/provider state
	./scripts/container-smoke.sh

clean: ## Remove generated local build output (keeps SQLite data)
	rm -rf dist .vinext

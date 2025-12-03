# Makefile for Brain Protocol
# Provides convenient shortcuts for common operations

.PHONY: help test e2e e2e-up e2e-down e2e-logs e2e-shell clean

# Default target
help:
	@echo "Brain Protocol - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Unit Tests:"
	@echo "  make test        Run pytest unit tests"
	@echo ""
	@echo "E2E Tests (Docker):"
	@echo "  make e2e         Run full e2e test suite"
	@echo "  make e2e-up      Start e2e environment (background)"
	@echo "  make e2e-down    Stop and clean e2e environment"
	@echo "  make e2e-logs    View e2e container logs"
	@echo "  make e2e-shell   Open shell in test-runner container"
	@echo ""
	@echo "Interactive Agent Access:"
	@echo "  make claude      Shell into Claude agent"
	@echo "  make gpt         Shell into GPT agent"
	@echo "  make gemini      Shell into Gemini agent"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       Remove build artifacts and caches"
	@echo ""

# =============================================================================
# Unit Tests
# =============================================================================

test:
	python -m pytest tests/ -v

test-verbose:
	python -m pytest tests/ -v --tb=long

# =============================================================================
# E2E Tests
# =============================================================================

COMPOSE_FILE := docker-compose.e2e.yml
DC := docker compose -f $(COMPOSE_FILE)

# Run full e2e test suite
e2e: e2e-up
	@echo "🧪 Running E2E tests..."
	$(DC) --profile test run --rm test-runner
	@echo "✅ E2E tests complete"

# Start e2e environment
e2e-up:
	@echo "🚀 Starting E2E environment..."
	$(DC) up -d --build
	@echo "⏳ Waiting for agents to initialize..."
	@sleep 5
	@echo "✅ E2E environment ready"
	@echo ""
	@echo "Agents running:"
	@docker ps --filter "name=brain-agent" --format "  {{.Names}}: {{.Status}}"

# Stop e2e environment
e2e-down:
	@echo "🛑 Stopping E2E environment..."
	$(DC) down -v
	@echo "✅ E2E environment stopped"

# View logs
e2e-logs:
	$(DC) logs -f

# Shell into test runner
e2e-shell:
	$(DC) exec test-runner /bin/bash

# =============================================================================
# Interactive Agent Access
# =============================================================================

claude:
	docker exec -it brain-agent-claude /entrypoint.sh shell

gpt:
	docker exec -it brain-agent-gpt /entrypoint.sh shell

gemini:
	docker exec -it brain-agent-gemini /entrypoint.sh shell

# Agent status
agent-status:
	@echo "📊 Agent Status:"
	@echo ""
	@echo "Claude:"
	@docker exec brain-agent-claude /entrypoint.sh status 2>/dev/null || echo "  (not running)"
	@echo ""
	@echo "GPT:"
	@docker exec brain-agent-gpt /entrypoint.sh status 2>/dev/null || echo "  (not running)"
	@echo ""
	@echo "Gemini:"
	@docker exec brain-agent-gemini /entrypoint.sh status 2>/dev/null || echo "  (not running)"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

clean-all: clean e2e-down
	@echo "🧹 Deep cleaning..."
	docker volume prune -f
	@echo "✅ Deep clean complete"


# Bookmark AI Analyzer - Makefile
# Provides convenient commands for development, testing, and deployment

.PHONY: help install install-dev test test-unit test-integration test-coverage clean build run docker-build docker-run lint format setup docs

# Default Python and Docker settings
PYTHON := python3
PIP := pip3
PYTEST := pytest
DOCKER := docker
DOCKER_COMPOSE := docker-compose

# Project settings
PROJECT_NAME := bookmark-ai-analyzer
DOCKER_IMAGE := $(PROJECT_NAME):latest
VENV_DIR := venv

# Help target - shows available commands
help:
	@echo "🔖 Bookmark AI Analyzer - Available Commands"
	@echo "=============================================="
	@echo ""
	@echo "📦 Setup & Installation:"
	@echo "  make setup              - Complete project setup (recommended for first time)"
	@echo "  make install            - Install production dependencies"
	@echo "  make install-dev        - Install development dependencies"
	@echo "  make venv              - Create virtual environment"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test              - Run all tests"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests only"
	@echo "  make test-coverage     - Run tests with coverage report"
	@echo "  make test-fast         - Run tests excluding slow ones"
	@echo ""
	@echo "🔍 Code Quality:"
	@echo "  make lint              - Run linting (flake8, pylint)"
	@echo "  make format            - Format code (black, isort)"
	@echo "  make check             - Run all quality checks"
	@echo "  make security          - Run security analysis (bandit)"
	@echo ""
	@echo "🏃 Running:"
	@echo "  make run               - Run bookmark analysis with sample data"
	@echo "  make run-help          - Show analysis script help"
	@echo "  make analyze FILE=     - Analyze specific bookmark file"
	@echo ""
	@echo "🐳 Docker:"
	@echo "  make docker-build      - Build Docker image"
	@echo "  make docker-run        - Run in Docker container"
	@echo "  make docker-up         - Start all services with docker-compose"
	@echo "  make docker-down       - Stop all services"
	@echo "  make docker-logs       - Show container logs"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  make docs              - Generate documentation"
	@echo "  make docs-serve        - Serve documentation locally"
	@echo ""
	@echo "🧹 Cleanup:"
	@echo "  make clean             - Clean build artifacts"
	@echo "  make clean-cache       - Clean cache directories"
	@echo "  make clean-all         - Clean everything including venv"

# Setup target for first-time users
setup: venv install-dev
	@echo "✅ Project setup complete!"
	@echo "   Next steps:"
	@echo "   1. Copy .env.example to .env and configure your API keys"
	@echo "   2. Run 'make test' to verify everything works"
	@echo "   3. Run 'make run-help' to see usage options"

# Virtual environment management
venv:
	@echo "🔧 Creating virtual environment..."
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "✅ Virtual environment created."
	@echo "   Activate with: source $(VENV_DIR)/bin/activate"

# Installation targets
install:
	@echo "📦 Installing production dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: install
	@echo "📦 Installing development dependencies..."
	$(PIP) install -r requirements-dev.txt

# Testing targets
test:
	@echo "🧪 Running all tests..."
	$(PYTEST) tests/ -v --tb=short

test-unit:
	@echo "🧪 Running unit tests..."
	$(PYTEST) tests/unit/ -v -m unit

test-integration:
	@echo "🧪 Running integration tests..."
	$(PYTEST) tests/integration/ -v -m integration

test-coverage:
	@echo "🧪 Running tests with coverage..."
	$(PYTEST) tests/ --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml
	@echo "📊 Coverage report generated in htmlcov/"

test-fast:
	@echo "🚀 Running fast tests (excluding slow ones)..."
	$(PYTEST) tests/ -v -m "not slow"

# Code quality targets
lint:
	@echo "🔍 Running linting..."
	@echo "  → flake8..."
	-flake8 src/ tests/ --max-line-length=100 --exclude=__pycache__
	@echo "  → pylint..."
	-pylint src/ --disable=missing-docstring,too-few-public-methods

format:
	@echo "🎨 Formatting code..."
	@echo "  → black..."
	black src/ tests/ --line-length=100
	@echo "  → isort..."
	isort src/ tests/ --profile black

check: lint test-fast
	@echo "✅ All quality checks passed!"

security:
	@echo "🔒 Running security analysis..."
	bandit -r src/ -f json -o security-report.json || true
	bandit -r src/

# Running targets
run:
	@echo "🚀 Running bookmark analysis with sample data..."
	$(PYTHON) scripts/run_analysis.py --sample --output results/

run-help:
	@echo "📖 Showing analysis script help..."
	$(PYTHON) scripts/run_analysis.py --help

analyze:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Please specify FILE=path/to/bookmarks.json"; \
		exit 1; \
	fi
	@echo "🔍 Analyzing $(FILE)..."
	$(PYTHON) scripts/run_analysis.py --input $(FILE) --output results/ --checkpoint

# Docker targets
docker-build:
	@echo "🐳 Building Docker image..."
	$(DOCKER) build -t $(DOCKER_IMAGE) .

docker-run: docker-build
	@echo "🐳 Running in Docker container..."
	$(DOCKER) run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/logs:/app/logs \
		-v $(PWD)/.env:/app/.env:ro \
		$(DOCKER_IMAGE)

docker-up:
	@echo "🐳 Starting all services with docker-compose..."
	$(DOCKER_COMPOSE) up -d
	@echo "✅ Services started. Check logs with 'make docker-logs'"

docker-down:
	@echo "🐳 Stopping all services..."
	$(DOCKER_COMPOSE) down

docker-logs:
	@echo "📋 Showing container logs..."
	$(DOCKER_COMPOSE) logs -f

# Documentation targets
docs:
	@echo "📚 Generating documentation..."
	@if command -v sphinx-build > /dev/null; then \
		sphinx-build -b html docs/ docs/_build/html; \
		echo "✅ Documentation generated in docs/_build/html/"; \
	else \
		echo "❌ Sphinx not installed. Install with: pip install sphinx"; \
	fi

docs-serve:
	@echo "📚 Serving documentation locally..."
	@if [ -d "docs/_build/html" ]; then \
		$(PYTHON) -m http.server 8080 -d docs/_build/html; \
	else \
		echo "❌ Documentation not built. Run 'make docs' first."; \
	fi

# Cleanup targets
clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ 2>/dev/null || true
	@echo "✅ Build artifacts cleaned."

clean-cache:
	@echo "🧹 Cleaning cache directories..."
	rm -rf data/cache/* logs/* data/checkpoints/* 2>/dev/null || true
	@echo "✅ Cache directories cleaned."

clean-all: clean clean-cache
	@echo "🧹 Cleaning everything including virtual environment..."
	rm -rf $(VENV_DIR)/ 2>/dev/null || true
	@echo "✅ Everything cleaned."

# Development helpers
dev-setup: setup
	@echo "🔧 Setting up development environment..."
	pre-commit install 2>/dev/null || echo "⚠️  pre-commit not available"
	@echo "✅ Development environment ready!"

check-env:
	@echo "🔍 Checking environment configuration..."
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Copy .env.example to .env and configure."; \
		exit 1; \
	fi
	@echo "✅ Environment configuration found."

# Database management
db-init:
	@echo "🗄️  Initializing database..."
	$(PYTHON) -c "from src.utils.db_manager import initialize_db; initialize_db()" 2>/dev/null || \
	echo "⚠️  Database initialization not implemented yet."

# Sample data generation
generate-sample:
	@echo "📝 Generating sample bookmark data..."
	$(PYTHON) -c "
import json
from datetime import datetime
sample_data = [
    {
        'id': f'sample_{i}',
        'url': f'https://example.com/article/{i}',
        'title': f'Sample Article {i}',
        'content': f'This is sample content for article {i}.' * 10,
        'author': f'Author{i}',
        'created_at': datetime.now().isoformat()
    }
    for i in range(10)
]
with open('data/raw/sample_bookmarks.json', 'w') as f:
    json.dump(sample_data, f, indent=2)
print('✅ Sample data generated in data/raw/sample_bookmarks.json')
"

# Performance testing
benchmark:
	@echo "🏁 Running performance benchmarks..."
	$(PYTEST) tests/ -m benchmark -v --benchmark-only 2>/dev/null || \
	echo "⚠️  Benchmark tests not implemented yet."

# Version information
version:
	@echo "📋 Version Information:"
	@echo "  Python: $$(python3 --version)"
	@echo "  Docker: $$(docker --version 2>/dev/null || echo 'Not installed')"
	@echo "  Docker Compose: $$(docker-compose --version 2>/dev/null || echo 'Not installed')"
	@echo "  Project: $(PROJECT_NAME)"

# Status check
status:
	@echo "📊 Project Status:"
	@echo "  Virtual env: $$([ -d $(VENV_DIR) ] && echo '✅ Created' || echo '❌ Not found')"
	@echo "  Dependencies: $$([ -f $(VENV_DIR)/pyvenv.cfg ] && echo '✅ Installed' || echo '❌ Run make install-dev')"
	@echo "  Environment: $$([ -f .env ] && echo '✅ Configured' || echo '❌ Copy .env.example to .env')"
	@echo "  Docker image: $$(docker images -q $(DOCKER_IMAGE) >/dev/null 2>&1 && echo '✅ Built' || echo '❌ Run make docker-build')"

# Default target
.DEFAULT_GOAL := help
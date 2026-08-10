# Makefile for Universal Crawler
# Usage: make <target>

.PHONY: help install test lint format typecheck security clean build release

# Default target
help:
	@echo "Universal Crawler - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install package in development mode with dev dependencies"
	@echo "  make install-docs  Install documentation dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          Run ruff linter"
	@echo "  make format        Format code with black"
	@echo "  make typecheck     Run mypy type checker"
	@echo "  make security      Run bandit security linter"
	@echo "  make check         Run all checks (lint, format, typecheck, security)"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run all tests with coverage"
	@echo "  make test-unit     Run unit tests only"
	@echo "  make test-watch    Run tests in watch mode"
	@echo ""
	@echo "Build & Release:"
	@echo "  make build         Build wheel and sdist"
	@echo "  make clean         Clean build artifacts"
	@echo ""
	@echo "Pre-commit:"
	@echo "  make pre-commit-install  Install pre-commit hooks"
	@echo "  make pre-commit-run      Run pre-commit on all files"
	@echo ""
	@echo "Docs:"
	@echo "  make docs-serve  Serve documentation locally"
	@echo "  make docs-build  Build documentation"

# Install package in development mode
install:
	pip install -e ".[dev]"
	playwright install chromium

install-docs:
	pip install -e ".[docs]"

# Code Quality
lint:
	ruff check .

format:
	black .

typecheck:
	mypy .

security:
	bandit -r crawler extractors utils database main.py

check: lint format typecheck security

# Testing
test:
	pytest tests/ -v --cov=crawler --cov=extractors --cov=utils --cov=database --cov-report=term-missing

test-unit:
	pytest tests/ -v -m "not integration"

test-watch:
	pytest-watch tests/ -v

# Build
build: clean
	python -m build
	twine check dist/*

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage coverage/ htmlcov/ .mypy_cache/ .ruff_cache/

# Pre-commit
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files

# Documentation
docs-serve:
	mkdocs serve

docs-build:
	mkdocs build --strict

# Release helpers
version-patch:
	@echo "Bump version: use 'cz bump --changelog' or edit pyproject.toml + CHANGELOG.md manually"

version-minor:
	@echo "Bump version: use 'cz bump --changelog --increment MINOR'"

version-major:
	@echo "Bump version: use 'cz bump --changelog --increment MAJOR'"

# Run crawler (convenience)
run:
	python main.py --extract emails,phones

run-custom:
	@read -p "Custom prompt: " prompt; python main.py --custom-prompt "$$prompt"

# Docker (if Dockerfile exists)
docker-build:
	docker build -t universal-crawler:latest .

docker-run:
	docker run --rm -v $(PWD)/output:/app/output -v $(PWD)/logs:/app/logs universal-crawler:latest
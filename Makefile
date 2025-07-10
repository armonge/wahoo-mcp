.PHONY: install install-dev test test-cov lint format check ci run auth test-auth clean

install:
	uv sync

install-dev:
	uv sync --all-extras

test:
	uv run pytest -v

test-cov:
	uv run pytest -vvv --cov=src --cov-report=xml --cov-report=term --junitxml=junit.xml -o junit_family=legacy

lint:
	uv run ruff check .

format:
	uv run ruff format .

check: lint format test
	@echo "All checks passed!"

ci: install-dev check
	@echo "CI checks completed!"

run:
	uv run python -m src.server

auth:
	uv run python src/auth.py

test-auth:
	@echo "Testing Wahoo API credentials..."
	@uv run python test_auth.py

clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

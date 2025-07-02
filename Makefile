.PHONY: install install-dev test run auth test-auth clean

install:
	uv venv
	uv pip install -e .

install-dev:
	uv venv
	uv pip install -e ".[dev]"

test:
	uv run pytest

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

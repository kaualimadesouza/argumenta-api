.PHONY: install lint format typecheck imports test run check

install: ; uv sync
lint: ; uv run ruff check .
format: ; uv run ruff format .
typecheck: ; uv run mypy
imports: ; uv run lint-imports
test: ; uv run pytest
run: ; uv run uvicorn argumenta.entrypoints.rest_application:app --reload
check: lint typecheck imports test

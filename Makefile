.PHONY: install lint format typecheck imports test run check db migrate migration downgrade seed purge

install: ; uv sync
lint: ; uv run ruff check .
format: ; uv run ruff format .
typecheck: ; uv run mypy
imports: ; uv run lint-imports
test: ; uv run pytest
run: ; uv run uvicorn argumenta.entrypoints.rest_application:app --reload
check: ; uv run pre-commit run --all-files && uv run pytest
db: ; docker compose up -d db
migrate: ; uv run alembic upgrade head
migration: ; uv run alembic revision --autogenerate -m "$(m)"
downgrade: ; uv run alembic downgrade -1
seed: ; uv run python -m argumenta.entrypoints.seed_content
purge: ; uv run python -m argumenta.entrypoints.purge_accounts

---
name: db-migrations
description: Create and apply Alembic migrations for the Argumenta Postgres schema, following the DER conventions (universal soft delete, partial uniques, audit timestamps). Use when changing SQLAlchemy models, creating or reviewing migrations, or touching the database schema in any way.
---

# Database migrations

Source of truth: [docs/DER.md](../../../docs/DER.md). The schema is never edited by
hand; models change first, Alembic generates the migration, the DER is updated in
the same PR. Alembic lands with issue #4; until then this skill documents the target.

## Schema conventions (enforced on every table)

- PK `uuid` with `gen_random_uuid()` (`pgcrypto`); e-mail uses `citext`.
- `created_at`, `updated_at`, `deleted_at` on ALL tables. `updated_at` is set by the
  application via SQLAlchemy `onupdate`; `deleted_at` is the universal soft delete:
  no product route ever hard-deletes, only the LGPD purge does.
- Every UNIQUE constraint is a partial unique index `WHERE deleted_at IS NULL`, so a
  soft-deleted row never blocks re-creation. Autogenerate does NOT produce these:
  declare them as `Index(..., unique=True, postgresql_where=text("deleted_at IS NULL"))`.
- All timestamps are `timestamptz`. Enums are native Postgres enums (14 of them, see DER).
- The only JSONB is `telemetry_events.payload`. Everything else is typed columns;
  models are typed SQLAlchemy classes, never dict bags.
- Tables with composite PKs (`chapter_progress`, `daily_activity`, `drafts`):
  reactivation is an UPDATE clearing `deleted_at`, never an INSERT.

## Workflow

```bash
docker compose up -d db                       # local Postgres 16
uv run alembic revision --autogenerate -m "add <thing>"
# review the generated file: partial uniques, enums and server defaults by hand
uv run alembic upgrade head
uv run alembic downgrade base && uv run alembic upgrade head   # must round-trip
uv run pytest                                  # CI has a migration smoke test
```

Checklist before committing a migration:

- [ ] Round-trips (`downgrade base` then `upgrade head` on a clean database)
- [ ] Partial uniques present (`WHERE deleted_at IS NULL`, plus `is_active`/`is_current` ones)
- [ ] docs/DER.md updated and version bumped in the same PR
- [ ] Migration message is short and imperative, in English

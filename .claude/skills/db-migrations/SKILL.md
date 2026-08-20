---
name: db-migrations
description: Create and apply Alembic migrations for the Argumenta Postgres schema, following the DER conventions (universal soft delete, partial uniques, audit timestamps). Use when changing SQLAlchemy models, creating or reviewing migrations, or touching the database schema in any way.
---

# Database migrations

Source of truth: [docs/DER.md](../../../docs/DER.md). The schema is never edited by
hand; models change first, Alembic generates the migration, the DER is updated in
the same PR. Models live in `src/argumenta/adapters/db/models/` (accounts, content,
gameplay, habit), shared mixins in `adapters/db/base.py`, enums in
`adapters/db/enums.py`. Alembic reads the URL from `Settings`
(`ARGUMENTA_DATABASE_URL`), never from `alembic.ini`.

## Schema conventions (enforced on every table)

- PK `uuid` with `gen_random_uuid()` (core since PG13); e-mail uses `citext`
  (extension created in the initial migration).
- Enum columns MUST use `db_enum(PyEnum, "der_name")` from `base.py`: plain
  `Enum(...)` stores the Python member NAMES (uppercase) instead of the DER values.
- New models take the mixins `UuidPkMixin` + `AuditMixin` (composite-PK tables skip
  `UuidPkMixin` and declare their PK columns).
- `created_at`, `updated_at`, `deleted_at` on ALL tables. `updated_at` is set by the
  application via SQLAlchemy `onupdate`; `deleted_at` is the universal soft delete:
  no product route ever hard-deletes, only the LGPD purge does.
- Every UNIQUE is a partial unique index `WHERE deleted_at IS NULL`, so a
  soft-deleted row never blocks re-creation. Never use `UniqueConstraint`:
  declare `Index("uq_...", ..., unique=True, postgresql_where=text("deleted_at IS NULL"))`.
- All timestamps are `timestamptz`. Enums are native Postgres enums (14 of them, see DER).
- The only JSONB is `telemetry_events.payload`. Everything else is typed columns;
  models are typed SQLAlchemy classes, never dict bags.
- Tables with composite PKs (`chapter_progress`, `daily_activity`, `drafts`):
  reactivation is an UPDATE clearing `deleted_at`, never an INSERT.

These conventions are locked by `tests/test_schema_conventions.py`; a model that
violates them fails the suite before it ever reaches a migration.

## Workflow

```bash
make db                          # local Postgres 16 via docker compose
make migration m="add <thing>"   # alembic revision --autogenerate
# review the generated file: enum values lowercase, partial uniques, server defaults;
# a migration that creates enum types must also DROP TYPE them in downgrade()
make migrate                     # alembic upgrade head
uv run alembic downgrade base && uv run alembic upgrade head   # must round-trip
uv run alembic check             # no drift between models and migrations
make check                       # full pre-commit + pytest; CI repeats the roundtrip
```

Checklist before committing a migration:

- [ ] Round-trips (`downgrade base` then `upgrade head` on a clean database)
- [ ] `alembic check` reports no new upgrade operations
- [ ] Partial uniques present (`WHERE deleted_at IS NULL`, plus `is_active`/`is_current` ones)
- [ ] Enum values in the migration are the DER lowercase values, not member names
- [ ] docs/DER.md updated and version bumped in the same PR
- [ ] Migration message is short and imperative, in English

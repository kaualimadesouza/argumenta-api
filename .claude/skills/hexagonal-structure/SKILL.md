---
name: hexagonal-structure
description: Place new code in the correct hexagonal layer (domain, application, adapters, presentation, entrypoints) respecting the repo's import contracts and typing rules. Use when adding features, endpoints, use cases, repositories, models, or deciding where a new module belongs.
---

# Hexagonal structure

Structure mirrors [python-hexagonal-framework](https://github.com/mauricio-dalpont/python-hexagonal-framework).
Import contracts are law, enforced by import-linter in CI (`uv run lint-imports`).

## Layers

| Layer | What lives here | May import |
|---|---|---|
| `argumenta/domain` | Entities, value objects, pure domain services | stdlib, pydantic |
| `argumenta/application` | Use cases, commands, queries (CQRS), ports (Protocols) | domain |
| `argumenta/adapters` | SQLAlchemy repositories, Claude client, push, IO | application, domain |
| `argumenta/presentation/fastapi` | Routes (resources) and API schemas | application, domain |
| `argumenta/entrypoints` | App assembly (`rest_application.py`), DI wiring | everything |

Forbidden and CI-enforced: `domain` and `application` importing FastAPI, SQLAlchemy
or any outer layer; `domain` importing `application`.

## Adding a feature (inside-out)

1. **Domain**: entity/value object with the business rule, pure and typed.
2. **Application**: use case taking a port (a `Protocol`) as dependency; the port
   describes what it needs (e.g. `SubmissionRepository`), not how.
3. **Adapter**: implement the port (`adapters/repositories/<agg>/repository.py`
   with its `models.py` beside it).
4. **Presentation**: a folder per feature with `resources.py` (router) and
   `schemas.py` (request/response pydantic models); never leak ORM models.
5. **Entrypoint**: wire the adapter into the use case and include the router in
   `entrypoints/rest_application.py`.

## Typing rules

- Typed objects over dict bags: pydantic models or dataclasses for any function
  input/output shape. A dict is fine only as a short-lived local.
- mypy runs strict; annotate everything, including tests.
- Verify the whole gate locally with `make check`.

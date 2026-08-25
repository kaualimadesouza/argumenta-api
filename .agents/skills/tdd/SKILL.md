---
name: tdd
description: Test-driven development workflow for the Argumenta API - write unit and integration tests before any implementation, red first, then green, then refactor. Use when starting any card, implementing any feature or fix, or whenever code is about to be written.
---

# TDD (owner decision: tests come first, always)

No production code before a failing test that demands it. This is the order of
work for every card, feature and bugfix in this repo.

## The cycle

1. **Derive the tests before touching src/**
   - Integration tests come from the card's acceptance criteria, one test per
     criterion, hitting the real HTTP surface with `TestClient` against the
     local Postgres. Name them after the behavior
     (`test_fourth_submission_of_the_day_is_blocked`), never after internals.
   - Unit tests come from the domain rules (pure functions and dataclasses in
     `domain/`): fast, no DB, no fakes needed.
   - Contract tests for adapter boundaries (pydantic parsing, span validation).
2. **Red**: run the new tests and watch them fail for the RIGHT reason (missing
   endpoint / wrong behavior, not an import typo).
3. **Green**: implement the minimum that satisfies them, layer by layer
   (domain rule -> use case -> adapter -> route).
4. **Refactor** with the suite as the safety net; the thermo-nuclear review
   runs before the PR anyway.

Bugfixes follow the same law: first a failing regression test that reproduces
the bug, then the fix, and the test stays forever.

## Repo test infrastructure (reuse, do not reinvent)

- `tests/conftest.py`: `db_engine` (migrates to head once), `clean_database`
  (autouse TRUNCATE after each test), `app`/`client` (TestClient with
  dependency overrides), `google_gateway` and `rate_limiter` doubles.
- **Fakes via `app.dependency_overrides`**, keyed by the dependency function
  (e.g. `get_evaluation_engine`), never by monkeypatching internals. Doubles
  implement the application port Protocol (see `ScriptedEngine` in
  `tests/test_submissions.py`).
- The LLM is NEVER called in tests; the calibration suite (issue #12) owns
  real-model evaluation.
- Convention tests (`test_schema_conventions.py`) lock the DER rules; extend
  them when adding schema-wide conventions.
- `make db` for local Postgres; `git add -A && make check` before every push.

## Rules that keep the suite honest

- Test through the public surface: endpoints, use cases, pure domain
  functions. Never assert private attributes or call repository internals to
  set up state you could create through the API (direct `Session` writes are
  fine for SEEDING data, not for asserting behavior the API should expose).
- A test that fails after a refactor is information: fix the code or the
  contract, never weaken the assertion to make it pass.
- Each acceptance criterion of the card maps to at least one test the PR
  description can point to.
- Determinism: no sleeps, no wall-clock assumptions beyond "today"; time-based
  logic gets injected clocks or seeded rows (see `DailyActivity` streak tests).

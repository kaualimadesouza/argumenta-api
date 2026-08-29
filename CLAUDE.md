# argumenta-api

FastAPI backend of Argumenta: argumentative writing training for vestibular prep
(FUVEST/ENEM). Hexagonal architecture, Postgres, Claude API as the correction
engine. Product decisions live in [docs/PRD.md](docs/PRD.md); the database model
lives in [docs/DER.md](docs/DER.md) and is the source of truth for the schema.

## Skills: check these BEFORE acting

Repo skills live in `.claude/skills/`. If the task matches a row, invoke the skill
first; do not improvise the workflow from memory.

| If the task involves... | Invoke |
|---|---|
| Schema, SQLAlchemy models, Alembic, anything database | `db-migrations` |
| Any direct AWS action (CLI/console): IAM, ECR, S3, SSM, Lambda, Terraform backend | `aws` |
| Deploying, GitHub Actions deploy workflows, VPS, GHCR, rollback | `deploy` |
| Starting/finishing an issue, opening a PR, the kanban board | `card-workflow` |
| Adding features, endpoints, use cases, repositories, new modules | `hexagonal-structure` |
| Writing ANY code (tests come first) | `tdd` |
| Writing ANY Portuguese a student reads (story content, labels, copy) | `portuguese-copy` |
| Reviewing a PR/diff before merge (mandatory for EVERY PR) | `thermo-nuclear-code-quality-review` |

Almost every coding session touches at least `card-workflow` (process) and
`hexagonal-structure` (where code goes). Load both when implementing a card.

## Non-negotiables

- **No assistant attribution anywhere**: no `Co-Authored-By`, no "Generated with"
  footers, in commits, PRs, issues or comments. Owner decision, permanent.
- **GitHub account**: `kaualimadesouza` only. Run `gh auth status` before gh/git
  network operations; `gh auth switch --user kaualimadesouza` if the work account
  is active (other sessions flip it back).
- One card = one PR to main, titled as a conventional commit
  (`feat:`/`fix:`/`chore:`/`docs:`/`ci:`), body with `Closes #<n>`.
- Code, identifiers, comments, commit messages and PR descriptions in English.
  Issues and product docs are in Portuguese.
- **Correct pt-BR in every string a student reads** (owner decision, details in
  the `portuguese-copy` skill): full accentuation, crase and hyphenation in story
  content, personas, objectives, hints, lens labels and any Portuguese prose. A
  product that grades spelling cannot ship `"Voce e presidente do gremio"`.
  Slugs, enum values and identifiers stay unaccented ASCII on purpose.
- **Objects and ORM, never dicts** (owner decision): every function input/output
  shape is a dataclass or pydantic model; persistence goes through the SQLAlchemy
  ORM (no raw SQL rows, no dict payloads between layers). Returning a tuple of
  loose values is the same smell: give it a named type. The only acceptable dict
  is a homogeneous lookup map (e.g. `dict[uuid.UUID, ChapterStatus]`) or a
  short-lived local; a dict-as-record crossing a function boundary is a bug.
- `make check` (pre-commit pipeline + pytest) must pass before every push; CI runs
  exactly the same thing. Run `git add -A` first: pre-commit only sees tracked files.
- **TDD, always** (owner decision, details in the `tdd` skill): write the tests
  BEFORE the implementation.
  For each card: unit tests for the domain rules and integration tests derived
  from the acceptance criteria come first; watch them fail (red), implement
  until green, then refactor with the suite as the safety net. A bug found
  later gets a failing regression test before the fix. Tests assert behavior
  through the public surface (endpoints, use cases, domain functions), never
  implementation details.
- **Every PR gets a thermo-nuclear review before merge**: run the
  `thermo-nuclear-code-quality-review` skill over the branch diff, apply or
  answer every structural finding, and only then merge. Owner decision.

## Commands

```bash
uv sync            # install (Python 3.12 pinned)
docker compose up  # Postgres 16 + API on :8000
make run           # API only, with reload
make check         # ruff + mypy strict + import contracts + bandit + secrets + xenon + pytest
```

## Layout (import contracts enforced in CI)

`src/argumenta/{domain, application, adapters, presentation/fastapi, entrypoints}`:
`domain`/`application` never import FastAPI, SQLAlchemy or outer layers. Details
and the feature recipe are in the `hexagonal-structure` skill.

## Related

Kanban: GitHub Project "Argumenta MVP" (owner kaualimadesouza, number 2), shared
with [argumenta-web](https://github.com/kaualimadesouza/argumenta-web) and
[argumenta-mobile](https://github.com/kaualimadesouza/argumenta-mobile).

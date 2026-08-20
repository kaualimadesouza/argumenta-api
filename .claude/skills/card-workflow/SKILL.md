---
name: card-workflow
description: Execute an Argumenta card end to end - branch, conventional-commit PR to main, CI green, and status moves on the Argumenta MVP kanban. Use when starting or finishing any issue/card, opening a PR, or updating the project board.
---

# Card workflow

One card = one PR to main. The kanban is GitHub Project **"Argumenta MVP"**
(number 2, owner `kaualimadesouza`), shared by argumenta-api, argumenta-web and
argumenta-mobile.

## Hard rules

- **gh account**: everything runs as `kaualimadesouza`. Check with `gh auth status`;
  if `kaualima1as` (work account) is active, run
  `gh auth switch --user kaualimadesouza` first. Other sessions flip it back, so
  re-check after any auth error.
- **No assistant attribution anywhere**: no `Co-Authored-By`, no "Generated with"
  footers, in commits, PRs, issues or comments. This is a standing owner decision.
- **Conventional commits** (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`): Release
  Please builds versions and changelog from them.
- Commits, code, identifiers and PR descriptions in English.

## Cycle

1. Move the card to **In Progress** (snippet below).
2. Branch from main: `feat/<slug>` (or `fix/`, `chore/`).
3. **Tests first**: follow the `tdd` skill (unit tests from domain rules,
   integration tests from the acceptance criteria, red before green).
4. Implement; run `git add -A` BEFORE `make check`: `pre-commit run --all-files`
   only sees git-tracked files, so an untracked new file silently skips every
   hook locally and then fails in CI (this bit three PRs in a row).
5. PR to main titled as a conventional commit, body with `Closes #<n>`.
   Before opening (or at latest before merging), run the
   `thermo-nuclear-code-quality-review` skill over the branch diff and apply
   or explicitly answer every structural finding. No PR merges unreviewed.
6. CI green; after merge, move the card to **Done** (merge auto-closes the issue).

## Board operations

Stable IDs for project 2:

| Thing | ID |
|---|---|
| Project | `PVT_kwHOBGuoa84Bg8eM` |
| Status field | `PVTSSF_lAHOBGuoa84Bg8eMzhf6F0E` |
| Status: Todo / In Progress / Done | `f75ad846` / `47fc9ee4` / `98236657` |
| Story Points field | `PVTF_lAHOBGuoa84Bg8eMzhf6F3c` |

```bash
# find the board item id for an issue
gh project item-list 2 --owner kaualimadesouza --format json --limit 100 \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(next(i['id'] for i in d['items'] if (i.get('content') or {}).get('url')=='$ISSUE_URL'))"

# move it (swap the option id for the target column)
gh project item-edit --id "$ITEM_ID" --project-id PVT_kwHOBGuoa84Bg8eM \
  --field-id PVTSSF_lAHOBGuoa84Bg8eMzhf6F0E --single-select-option-id 47fc9ee4
```

New issues follow the house format: `## O que construir`, `## Criterios de aceite`,
`## Bloqueado por`, `## Tipo` (AFK/HITL), `## Story Points`; add them to the board
with Status Todo and their points.

---
name: deploy
description: Deploy the API to the VPS over SSH with blue/green containers from GHCR, using the asq-data workflow model. Use when setting up or running a deploy, editing GitHub Actions deploy workflows, configuring VPS secrets, or debugging a failed deploy or rollback.
---

# Deploy (SSH to VPS, blue/green)

The deploy model is copied from the asq-data repo and lands with issue #3. Local
model source (read these before editing anything):

- `/home/kaua/app/asq-data/.github/workflows/_deploy-to-vps-ssh.yml` (reusable workflow)
- `/home/kaua/app/asq-data/.github/workflows/deploy-backtest.yml` (caller example)
- `/home/kaua/app/asq-data/.github/scripts/deploy-vps.sh` (blue/green + rollback)
- `/home/kaua/app/asq-data/.github/config/services.json` (service config)

## Architecture

`deploy-api.yml` (caller: `workflow_dispatch` with choice dev/prod + push on main)
runs CI, resolves environment and version, builds the Docker image, pushes to
`ghcr.io/kaualimadesouza/argumenta-api`, then calls `_deploy-to-vps-ssh.yml`, which
ships `deploy-vps.sh` to the VPS via scp. The script starts the new container next
to the old one, hits `GET /health`, switches traffic on success and rolls back
automatically on failure.

Two deliberate adaptations from the asq-data original:

- Registry is GHCR with `GITHUB_TOKEN` (no ECR, no AWS credentials).
- The app env-file comes from the `SERVICE_ENV` Environment secret
  (no Secrets Manager).

## Environment secrets (per GitHub Environment: dev, prod)

`VPS_HOST`, `VPS_DEPLOY_USER`, `VPS_SSH_PRIVATE_KEY`, `VPS_SSH_KNOWN_HOSTS`,
`SERVICE_ENV` (the full .env content).

## Operating it

```bash
gh workflow run deploy-api.yml -f environment=dev   # manual deploy
gh run watch                                        # follow it
curl -fsS https://<host>/health                     # verify
```

## Migrations run on every deploy (founder decision, 2026-08-20)

The deploy MUST run `alembic upgrade head` before switching traffic to the new
container: after pulling the new image and before the healthcheck/switch, the
script runs the migration from the new image
(`docker run --rm --env-file <env> <image> alembic upgrade head`). A failed
migration aborts the deploy and keeps the old container serving. Consequence for
schema work: every migration must be forward-compatible with the container still
running (expand/contract; never drop or rename a column the live version reads).

Rollback: the script rolls back on failed healthcheck by itself; for a manual
rollback re-run the workflow pinned to the previous image tag. Migrations are NOT
rolled back automatically (the old code must tolerate the new schema, see above);
a manual `alembic downgrade` is the escape hatch. Never edit containers on the
VPS by hand; the script owns their lifecycle.

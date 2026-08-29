---
name: deploy
description: Deploy the API to AWS Lambda (container image) behind API Gateway, infra as Terraform in infrastructure/, driven by a 4-stage GitHub Actions pipeline (CI, Build and Push, Deploy, Notify). Use when setting up or running a deploy, editing the deploy workflow or Terraform, configuring deploy secrets/variables, or debugging a failed deploy.
---

# Deploy (AWS Lambda, container image, Terraform)

Replaced an earlier SAM/CloudFormation version (2026-08-29) and, before that, a
planned SSH-to-VPS blue/green model that was never actually built for this repo.
Always check `.github/workflows/deploy.yml` and `infrastructure/` directly before
trusting a description of the pipeline, this file included.

**Load the `aws` skill before touching any AWS resource by hand** (CLI or
console): it has the account id, the required profile, and the incident that
made that rule non-negotiable.

## Pipeline (`.github/workflows/deploy.yml`)

Triggers: push to `main` deploys **dev**; merging the release-please Release PR
deploys **prod**, but NOT via the `release: published` trigger: release-please
creates the release with `GITHUB_TOKEN`, whose events never start workflows, so
`release-please.yml` chains this workflow directly (`workflow_call` with
`environment: prod` when `releases_created` is true). The `release` trigger
stays only for releases published by hand. `workflow_dispatch` with an
`environment` input (`dev` | `prod`) picks explicitly. Four jobs, each gated on the previous:

1. **ci** — reuses `ci.yml` (lint, mypy strict, import contracts, bandit, tests).
2. **build-and-push** — logs into ECR, `docker buildx build --platform linux/amd64 --provenance=false --push`, tags the image with `github.sha`, outputs the full image URI.
3. **deploy** — runs `alembic upgrade head` against `ARGUMENTA_DATABASE_URL_DIRECT`, then `terraform init`/`apply` in `infrastructure/`, passing the built image URI and every secret as `TF_VAR_*` env vars (never as `-var` CLI args, never echoed).
4. **notify** — `if: always()`, needs all three prior jobs, posts a Telegram message naming which stage failed (or success).

## Infra (`infrastructure/`, Terraform)

- `backend.tf` — S3 backend with native locking (`use_lockfile = true`, needs Terraform ≥1.10); bucket/key/region are passed via `-backend-config` at `terraform init` time (partial config), never hardcoded, so the same files serve every stage.
- `variables.tf` / `main.tf` — the Lambda function (`package_type = "Image"`, `image_uri` from the build job), its IAM execution role (`AWSLambdaBasicExecutionRole`), an HTTP API Gateway with one route (`ANY /{proxy+}`, matches the SAM behavior it replaced), and the `aws_lambda_permission` letting API Gateway invoke it.
- `outputs.tf` — `api_endpoint`.
- `ecr-lifecycle-policy.json` — keeps only the last 10 images; applied by hand (see bootstrap below), not by Terraform.

`Dockerfile` (repo root, not in `infrastructure/`: it's app packaging, the build context needs it at root) builds the Lambda container image: multi-stage from `ghcr.io/astral-sh/uv` + `public.ecr.aws/lambda/python:3.12`, `uv export --frozen --no-dev --no-emit-project --no-hashes` (add `--extra <name>` here whenever an optional LLM vendor extra is enabled, e.g. `--extra google` for Gemini) into `requirements.txt`, then `pip install`. Copies `src/argumenta` (not `src/`) into `${LAMBDA_TASK_ROOT}/argumenta` — hatchling's `packages = ["src/argumenta"]` maps it to the top-level `argumenta` package, so the handler is `argumenta.entrypoints.rest_application.handler`, never `src.argumenta...` (that exact mismatch was a real bug, caught testing the image locally, before the very first real deploy).

## One-time bootstrap (manual, outside Terraform, on purpose)

Two things must exist before the first deploy, and are deliberately NOT managed
by Terraform so they survive `terraform destroy`: the ECR repository and the S3
state bucket. Exact commands are in the README's Deploy section (they change
rarely enough not to duplicate here) — includes applying
`ecr-lifecycle-policy.json`, applying `ecr-lambda-pull-policy.json` (the Lambda
service principal pulls the image itself; without it `CreateFunction` is an
AccessDeniedException) and registering the bucket name as the `TF_STATE_BUCKET`
GitHub variable.

## Secrets and variables (GitHub, repo-level)

Secrets (sensitive): `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (the
`argumenta-api-deployer` IAM user, never the account admin — see `aws` skill),
`ARGUMENTA_DATABASE_URL` (pooled) / `ARGUMENTA_DATABASE_URL_DIRECT` (direct, for
migrations only — see `neon-postgres` skill for why), `ARGUMENTA_JWT_SECRET`,
`ARGUMENTA_ANTHROPIC_API_KEY`, `ARGUMENTA_GOOGLE_API_KEY` (Gemini, not the same
thing as the OAuth pair below), `ARGUMENTA_GOOGLE_CLIENT_ID`/`_SECRET` (Google
login OAuth), `TELEGRAM_BOT_TOKEN`/`_CHAT_ID`.

Variables (not sensitive, `gh variable set`): `TF_STATE_BUCKET`,
`ARGUMENTA_LLM_VENDOR` (`anthropic` | `openai` | `google`),
`ARGUMENTA_EVALUATION_MODEL`, `ARGUMENTA_REACTION_MODEL`. Changing which vendor
answers is a variable change plus the matching API key secret, no code change
and no new image build — but the evaluation/reaction model names must be valid
for whichever vendor is selected (e.g. `claude-sonnet-5` for anthropic,
`gemini-3-pro` for google), or `Settings()` construction fails at cold start.

## Operating it

```bash
gh workflow run deploy.yml -f environment=dev   # manual deploy (dev/prod)
gh run watch
```
Also runs automatically on every push to `main`.

## Migrations

Same founder rule as always: migrations must be forward-compatible with the
code still running when they land (expand/contract; never drop or rename a
column the live version reads). What changed is *where* this is enforced:
`alembic upgrade head` now runs as its own deploy step, against the direct
(non-pooled) Neon URL, strictly before `terraform apply` touches the Lambda.

## Rollback — no automatic mechanism, unlike the old VPS model this replaced

There is no health-checked traffic switch and no automatic rollback here: once
`terraform apply` updates the function, every new invocation runs the new
image immediately. If a bad deploy ships, the recourse is either a `git revert`
+ push (a normal new deploy, with a new commit SHA and a new image), or by
hand: `terraform apply -var="image_uri=<previous-sha-uri>"` from
`infrastructure/`, using an image still in ECR (the lifecycle policy only
keeps the last 10, so this window isn't unlimited). Migrations are never
rolled back automatically either; `alembic downgrade` is the manual escape
hatch, same as before.

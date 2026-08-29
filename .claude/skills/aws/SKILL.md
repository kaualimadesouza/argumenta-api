---
name: aws
description: Use before ANY direct AWS action for argumenta-api (CLI or console: IAM, ECR, S3, SSM, Lambda, or anything touching the Terraform backend). Confirms which AWS account and profile to use.
---

# AWS account for argumenta-api

**The only correct AWS account for this project is `743917687224` ("kaua.productions"), the owner's personal account, IAM user `KauaAdmin`.**

The machine's `default` AWS CLI profile points to the owner's WORK account instead
(`799618983511`, IAM user `kaua.lima`). On 2026-08-29 this caused a real incident:
infra for this personal project (an ECR repository, an S3 Terraform state bucket,
an IAM deployer user with an access key already pushed to GitHub secrets, and SSM
parameters holding real Neon database credentials) was created in the **work**
account, because `aws sts get-caller-identity` returned successfully and that was
taken as "credentials are configured" without checking *which* account answered.
Everything was found and torn down the same day, but the access key was live and
exposed as a GitHub secret in the meantime.

## Hard rule

Before creating or modifying any AWS resource for this project, run:

```bash
aws sts get-caller-identity --profile argumenta-ai
```

and confirm the `Account` field reads exactly `743917687224`. If it doesn't (wrong
profile, profile not configured yet, expired session), stop and ask the owner
instead of falling back to `default` or any other profile on this machine.

**Never** use `--profile default`, and never omit `--profile` (an omitted
`--profile` silently resolves to `default`, which is the work account).

## One-time profile setup (run by the owner via `!`)

Credentials come from `KauaAdmin_accessKeys.csv`; reading that file directly is
blocked for the assistant, so the owner runs this themselves:

```bash
aws configure --profile argumenta-ai
# AWS Access Key ID / Secret Access Key: from KauaAdmin_accessKeys.csv
# Default region: us-east-1
```

## What lives in this account for argumenta-api

- ECR repository `argumenta-api` (lifecycle policy in
  `infrastructure/ecr-lifecycle-policy.json`; repository policy letting
  `lambda.amazonaws.com` pull images, in `infrastructure/ecr-lambda-pull-policy.json`,
  without which `CreateFunction` fails with AccessDeniedException)
- S3 bucket `argumenta-api-tfstate-743917687224` (Terraform remote state)
- IAM user `argumenta-api-deployer` + policy `argumenta-api-deployer-policy`
  (scoped to `argumenta-api-*` resources; used only by the GitHub Actions
  deploy pipeline, never the owner's own day-to-day credentials)

(Update this list if any of these are renamed, recreated, or removed.)

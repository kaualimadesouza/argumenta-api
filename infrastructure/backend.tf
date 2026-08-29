terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # bucket, key and region are supplied via -backend-config at `terraform init`
  # time (see .github/workflows/deploy.yml) so the same file works for every
  # stage without hardcoding a stage-specific state key here.
  backend "s3" {
    use_lockfile = true
  }
}

provider "aws" {}

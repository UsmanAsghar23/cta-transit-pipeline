terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Credentials come from the environment (e.g. AWS_PROFILE=admin), not from code.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "cta-transit-pipeline"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  bucket_arn = aws_s3_bucket.lake.arn

  # Until Snowflake gives us its IAM user, trust our own account root as a harmless placeholder.
  snowflake_principal = coalesce(
    var.snowflake_iam_user_arn,
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  )
}

# ---------------------------------------------------------------------------
# S3 data lake
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "lake" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket = aws_s3_bucket.lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Raw positions are reloadable history, not something worth paying to keep forever.
# GTFS files under gtfs/ are overwritten weekly, so they aren't covered by this rule.
resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id

  rule {
    id     = "expire-raw-vehicles"
    status = "Enabled"

    filter {
      prefix = "vehicles/"
    }

    expiration {
      days = var.vehicle_retention_days
    }
  }
}

# ---------------------------------------------------------------------------
# IAM user for Airflow (writes raw files, reads GTFS back)
# ---------------------------------------------------------------------------

resource "aws_iam_user" "airflow" {
  name = "cta-airflow"
}

data "aws_iam_policy_document" "airflow" {
  statement {
    sid       = "ReadWriteObjects"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${local.bucket_arn}/*"]
  }

  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket"]
    resources = [local.bucket_arn]
  }
}

resource "aws_iam_user_policy" "airflow" {
  name   = "cta-airflow-s3"
  user   = aws_iam_user.airflow.name
  policy = data.aws_iam_policy_document.airflow.json
}

# Local Airflow in Docker can't use SSO, so it needs a long-lived key scoped to this one bucket.
resource "aws_iam_access_key" "airflow" {
  user = aws_iam_user.airflow.name
}

# ---------------------------------------------------------------------------
# IAM role that Snowflake assumes to read the bucket (storage integration)
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "snowflake_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [local.snowflake_principal]
    }

    # The external ID stops other Snowflake customers from using this role
    # even though Snowflake's IAM user is shared across accounts.
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.snowflake_external_id]
    }
  }
}

resource "aws_iam_role" "snowflake" {
  name               = "cta-snowflake-s3"
  assume_role_policy = data.aws_iam_policy_document.snowflake_trust.json
}

data "aws_iam_policy_document" "snowflake_read" {
  statement {
    sid       = "ReadObjects"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${local.bucket_arn}/*"]
  }

  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [local.bucket_arn]
  }
}

resource "aws_iam_role_policy" "snowflake_read" {
  name   = "cta-snowflake-s3-read"
  role   = aws_iam_role.snowflake.id
  policy = data.aws_iam_policy_document.snowflake_read.json
}

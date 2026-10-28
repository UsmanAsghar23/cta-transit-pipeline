output "bucket_name" {
  value = aws_s3_bucket.lake.bucket
}

output "aws_region" {
  value = var.aws_region
}

output "snowflake_role_arn" {
  description = "Use as STORAGE_AWS_ROLE_ARN in snowflake/setup.sql."
  value       = aws_iam_role.snowflake.arn
}

output "airflow_access_key_id" {
  value = aws_iam_access_key.airflow.id
}

output "airflow_secret_access_key" {
  description = "Read with: terraform output -raw airflow_secret_access_key"
  value       = aws_iam_access_key.airflow.secret
  sensitive   = true
}


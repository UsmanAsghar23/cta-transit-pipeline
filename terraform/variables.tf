variable "aws_region" {
  description = "Region for the bucket. Keep it close to your Snowflake account's region to avoid cross-region transfer costs."
  type        = string
  default     = "us-east-2"
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name for the data lake."
  type        = string
}

variable "vehicle_retention_days" {
  description = "Days to keep raw vehicle files before S3 deletes them."
  type        = number
  default     = 90
}

# The next two values only exist after Snowflake's storage integration is created
# (Phase 4, DESC INTEGRATION). Until then they're null and the trust policy falls
# back to this AWS account, so the first apply succeeds without Snowflake.
variable "snowflake_iam_user_arn" {
  description = "STORAGE_AWS_IAM_USER_ARN from DESC INTEGRATION CTA_S3_INT."
  type        = string
  default     = null
}

variable "snowflake_external_id" {
  description = "STORAGE_AWS_EXTERNAL_ID from DESC INTEGRATION CTA_S3_INT."
  type        = string
  default     = "placeholder-external-id"
}

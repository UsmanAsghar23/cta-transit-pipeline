-- =============================================================================
-- CTA Transit Pipeline: one-time Snowflake setup
--
-- Run as ACCOUNTADMIN in a Snowsight worksheet, one section at a time.
-- Replace these placeholders first:
--   <SNOWFLAKE_ROLE_ARN>  terraform output snowflake_role_arn
--   <BUCKET_NAME>         terraform output bucket_name
--   <CTA_SVC_PUBLIC_KEY>  public key body (see README, "Key-pair auth")
-- =============================================================================

USE ROLE ACCOUNTADMIN;


-- -----------------------------------------------------------------------------
-- 1. Warehouse, database, and role
-- -----------------------------------------------------------------------------

-- XS + 60s auto-suspend: the hourly load runs for seconds, so we only pay for
-- about a minute of compute per hour.
CREATE WAREHOUSE IF NOT EXISTS CTA_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE ROLE IF NOT EXISTS CTA_ROLE;
GRANT USAGE, OPERATE ON WAREHOUSE CTA_WH TO ROLE CTA_ROLE;

CREATE DATABASE IF NOT EXISTS CTA;
-- Owning the database gives CTA_ROLE full rights on everything it creates inside,
-- including schemas dbt creates on the fly (e.g. CI).
GRANT OWNERSHIP ON DATABASE CTA TO ROLE CTA_ROLE COPY CURRENT GRANTS;

-- Let SYSADMIN (and you) see and manage the project's objects.
GRANT ROLE CTA_ROLE TO ROLE SYSADMIN;
-- Quoted so usernames containing dots or lowercase (e.g. first.last) still resolve.
SET my_user = '"' || CURRENT_USER() || '"';
GRANT ROLE CTA_ROLE TO USER IDENTIFIER($my_user);


-- -----------------------------------------------------------------------------
-- 2. Service user with key-pair authentication
-- -----------------------------------------------------------------------------

-- TYPE = SERVICE users can't log in with a password, which is where Snowflake
-- is heading for all non-human logins.
CREATE USER IF NOT EXISTS CTA_SVC
  TYPE = SERVICE
  DEFAULT_ROLE = CTA_ROLE
  DEFAULT_WAREHOUSE = CTA_WH
  DEFAULT_NAMESPACE = CTA.RAW
  RSA_PUBLIC_KEY = '<CTA_SVC_PUBLIC_KEY>'
  COMMENT = 'Airflow loads and dbt runs';

GRANT ROLE CTA_ROLE TO USER CTA_SVC;


-- -----------------------------------------------------------------------------
-- 3. Storage integration (Snowflake -> S3 via the Terraform IAM role)
-- -----------------------------------------------------------------------------

-- IF NOT EXISTS matters: CREATE OR REPLACE would generate a new external ID
-- and silently break the IAM trust policy.
CREATE STORAGE INTEGRATION IF NOT EXISTS CTA_S3_INT
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '<SNOWFLAKE_ROLE_ARN>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<BUCKET_NAME>/');

GRANT USAGE ON INTEGRATION CTA_S3_INT TO ROLE CTA_ROLE;

DESC INTEGRATION CTA_S3_INT;

-- >>> PAUSE HERE <<<
-- Copy two values from the DESC output into terraform/terraform.tfvars:
--   STORAGE_AWS_IAM_USER_ARN -> snowflake_iam_user_arn
--   STORAGE_AWS_EXTERNAL_ID  -> snowflake_external_id
-- Then run `terraform apply` and continue with section 4.


-- -----------------------------------------------------------------------------
-- 4. Schemas, file formats, and the external stage (owned by CTA_ROLE)
-- -----------------------------------------------------------------------------

USE ROLE CTA_ROLE;
USE WAREHOUSE CTA_WH;
USE DATABASE CTA;

CREATE SCHEMA IF NOT EXISTS RAW;
CREATE SCHEMA IF NOT EXISTS ANALYTICS;
USE SCHEMA RAW;

-- Matches what Airflow writes: gzipped, one JSON object per line.
CREATE FILE FORMAT IF NOT EXISTS JSON_GZ
  TYPE = JSON
  COMPRESSION = GZIP;

-- PARSE_HEADER lets COPY match GTFS columns by name, so CTA adding or
-- reordering columns doesn't break the load.
CREATE FILE FORMAT IF NOT EXISTS GTFS_CSV
  TYPE = CSV
  PARSE_HEADER = TRUE
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
  COMPRESSION = AUTO;

CREATE STAGE IF NOT EXISTS CTA_LAKE
  URL = 's3://<BUCKET_NAME>/'
  STORAGE_INTEGRATION = CTA_S3_INT;

-- Should list files once terraform apply has updated the trust policy.
-- An "Access Denied" or "not authorized" here means the tfvars values or apply step was missed.
LIST @CTA_LAKE/vehicles/ PATTERN = '.*source=train.*';


-- -----------------------------------------------------------------------------
-- 5. Raw position tables (one VARIANT per API record)
-- -----------------------------------------------------------------------------

-- Keep the raw JSON untouched; dbt does all parsing, so a parsing bug never
-- requires re-ingesting from S3.
CREATE TABLE IF NOT EXISTS BUS_POSITIONS_RAW (
  record      VARIANT,
  source_file STRING,
  loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS TRAIN_POSITIONS_RAW (
  record      VARIANT,
  source_file STRING,
  loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);


-- -----------------------------------------------------------------------------
-- 6. GTFS schedule tables (all STRING on purpose)
-- -----------------------------------------------------------------------------

-- GTFS times like 25:30:00 (trips running past midnight) aren't valid TIMEs,
-- and IDs with leading zeros would be mangled as numbers. dbt casts deliberately.

CREATE TABLE IF NOT EXISTS GTFS_ROUTES (
  agency_id        STRING,
  route_id         STRING,
  route_short_name STRING,
  route_long_name  STRING,
  route_type       STRING,
  route_url        STRING,
  route_color      STRING,
  route_text_color STRING
);

CREATE TABLE IF NOT EXISTS GTFS_STOPS (
  stop_id             STRING,
  stop_code           STRING,
  stop_name           STRING,
  stop_desc           STRING,
  stop_lat            STRING,
  stop_lon            STRING,
  location_type       STRING,
  parent_station      STRING,
  wheelchair_boarding STRING
);

-- schd_trip_id is CTA's scheduling-system trip number, the intended link to
-- live vehicles for the v2 on-time model.
CREATE TABLE IF NOT EXISTS GTFS_TRIPS (
  route_id              STRING,
  service_id            STRING,
  trip_id               STRING,
  direction_id          STRING,
  block_id              STRING,
  shape_id              STRING,
  direction             STRING,
  wheelchair_accessible STRING,
  schd_trip_id          STRING
);

CREATE TABLE IF NOT EXISTS GTFS_STOP_TIMES (
  trip_id             STRING,
  arrival_time        STRING,
  departure_time      STRING,
  stop_id             STRING,
  stop_sequence       STRING,
  stop_headsign       STRING,
  pickup_type         STRING,
  shape_dist_traveled STRING
);

CREATE TABLE IF NOT EXISTS GTFS_CALENDAR (
  service_id STRING,
  monday     STRING,
  tuesday    STRING,
  wednesday  STRING,
  thursday   STRING,
  friday     STRING,
  saturday   STRING,
  sunday     STRING,
  start_date STRING,
  end_date   STRING
);


-- -----------------------------------------------------------------------------
-- 7. Smoke test: one manual load (Airflow does this hourly from now on)
-- -----------------------------------------------------------------------------

COPY INTO TRAIN_POSITIONS_RAW (record, source_file)
  FROM (SELECT $1, METADATA$FILENAME FROM @CTA_LAKE/vehicles/source=train/)
  FILE_FORMAT = (FORMAT_NAME = 'JSON_GZ');

SELECT COUNT(*) AS row_count, COUNT(DISTINCT source_file) AS file_count FROM TRAIN_POSITIONS_RAW;

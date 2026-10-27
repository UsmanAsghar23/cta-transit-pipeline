# Chicago Transit Reliability Pipeline

Collects live CTA bus and train positions every 3 minutes, lands them in an S3 data lake, loads them into Snowflake, and uses dbt to compute on-time performance by route and hour.

> Work in progress — built in phases. Full docs arrive in Phase 6.

## Phase 1: API client

1. Get API keys:
   - **Bus Tracker:** create an account at [ctabustracker.com](https://www.ctabustracker.com), sign in, open *My Account*, and follow the *Developer API* link.
   - **Train Tracker:** apply via the [Train Tracker developer page](https://www.transitchicago.com/developers/traintracker/).
2. Set up a Python 3.11 environment (dbt doesn't support 3.14 yet, so we standardize on 3.11):
   ```bash
   brew install python@3.11
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
3. `cp .env.example .env` and paste in both keys.
4. `python scripts/try_api.py`

## Phase 2: AWS infrastructure (Terraform)

Creates the S3 data lake, a scoped IAM user for Airflow, and the IAM role Snowflake will assume.

```bash
brew install hashicorp/tap/terraform awscli
aws sso login --profile admin
export AWS_PROFILE=admin

cd terraform
cp terraform.tfvars.example terraform.tfvars   # set a globally unique bucket_name
terraform init
terraform apply

terraform output                                  # bucket, role ARN, access key ID
terraform output -raw airflow_secret_access_key   # secret key (shown once here, keep it out of git)
```

State is kept locally (`terraform.tfstate`, gitignored). It contains the Airflow secret key, so don't commit or share it.

## Phase 3: Airflow ingestion into S3

Airflow runs locally in Docker via the [Astro CLI](https://www.astronomer.io/docs/astro/cli/overview) (Astro Runtime 3.x, Airflow 3).

```bash
brew install astro
cd airflow
cp .env.example .env    # fill in keys, bucket, and the AWS connection JSON
astro dev start         # UI at http://localhost:8080
astro dev pytest        # DAG integrity + unit tests
```

| DAG | Schedule | What it does |
| --- | --- | --- |
| `cta_ingest` | every 3 min | Fetches all buses and trains, writes `vehicles/source=<bus\|train>/date=YYYY-MM-DD/hour=HH/<source>_<ts>.json.gz` |
| `cta_freshness` | every 15 min | Fails (and alerts Slack, if `SLACK_WEBHOOK_URL` is set) when a source's newest file is older than 15 min |

Data only collects while your laptop and Docker are running; sleep shows up as gaps.

### API budget

Bus Tracker allows 100,000 calls/day per key (CTA raised it from 50,000 in April 2024). With ~130 routes batched 10 per call, one poll is ~14 calls; every 3 minutes that's 480 polls × ~15 calls ≈ 7,200 calls/day. Train Tracker needs one call per poll for all 8 lines (480/day).

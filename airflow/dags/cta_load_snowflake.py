"""
## cta_load_snowflake

Hourly, `COPY INTO` the raw position tables from S3 for the run's UTC hour and
the hour before it (see `sql/copy_positions.sql`).

**Why this is safe to re-run:** Snowflake keeps load metadata per file for 64
days and skips files it has already loaded. Overlapping windows, retries, and
backfills therefore only pick up files that are new.

Backfill a range of hours:

    astro dev run backfill create --dag-id cta_load_snowflake \\
        --from-date 2026-10-27T00:00:00 --to-date 2026-10-28T00:00:00
"""

from datetime import timedelta

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.sdk import dag
from pendulum import datetime as pendulum_datetime

SOURCES = {"bus": "BUS_POSITIONS_RAW", "train": "TRAIN_POSITIONS_RAW"}


@dag(
    # Five minutes past the hour, so the previous hour's last snapshot has landed.
    schedule="5 * * * *",
    start_date=pendulum_datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "cta",
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["cta", "snowflake"],
    doc_md=__doc__,
)
def cta_load_snowflake():
    for source, table in SOURCES.items():
        SQLExecuteQueryOperator(
            task_id=f"copy_{source}",
            conn_id="snowflake_default",
            sql="sql/copy_positions.sql",
            params={"source": source, "table": table},
            split_statements=True,
        )


cta_load_snowflake()

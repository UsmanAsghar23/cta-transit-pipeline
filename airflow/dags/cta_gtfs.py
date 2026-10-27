"""
## cta_gtfs

Weekly: download CTA's GTFS schedule, upload the five tables we use to
`s3://<bucket>/gtfs/latest/`, then truncate and reload them in Snowflake.
CTA republishes the feed every week or two, so weekly keeps us current.
"""

import gzip
import os
import shutil
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path

import requests
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.sdk import dag, task
from pendulum import datetime as pendulum_datetime

GTFS_URL = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"

# GTFS file name (without .txt) -> Snowflake table
GTFS_TABLES = {
    "routes": "GTFS_ROUTES",
    "stops": "GTFS_STOPS",
    "trips": "GTFS_TRIPS",
    "stop_times": "GTFS_STOP_TIMES",
    "calendar": "GTFS_CALENDAR",
}


@dag(
    schedule="@weekly",
    start_date=pendulum_datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "cta",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["cta", "gtfs", "snowflake"],
    doc_md=__doc__,
)
def cta_gtfs():
    @task(execution_timeout=timedelta(minutes=30))
    def upload_gtfs_to_s3():
        bucket = os.environ["CTA_S3_BUCKET"]
        s3 = S3Hook(aws_conn_id="aws_default")

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "gtfs.zip"
            # Stream to disk: the zip is ~70 MB and stop_times.txt alone is ~370 MB unzipped.
            with requests.get(GTFS_URL, stream=True, timeout=120) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        f.write(chunk)

            with zipfile.ZipFile(zip_path) as archive:
                for name in GTFS_TABLES:
                    # Gzip before upload (~10x smaller); Snowflake decompresses automatically.
                    gz_path = Path(tmp) / f"{name}.txt.gz"
                    with archive.open(f"{name}.txt") as src, gzip.open(gz_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    s3.load_file(
                        str(gz_path),
                        key=f"gtfs/latest/{name}.txt.gz",
                        bucket_name=bucket,
                        replace=True,
                    )
                    print(f"Uploaded {name}.txt.gz")

    load_tables = SQLExecuteQueryOperator(
        task_id="load_gtfs_tables",
        conn_id="snowflake_default",
        sql="sql/load_gtfs.sql",
        params={"tables": GTFS_TABLES},
        split_statements=True,
    )

    upload_gtfs_to_s3() >> load_tables


cta_gtfs()

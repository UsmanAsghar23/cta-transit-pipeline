"""
## cta_freshness

Every 15 minutes, check that each source has written a file to S3 recently.
Because `cta_ingest` writes a file even when no vehicles are running, a stale
partition means the pipeline is broken, not that it's 3am.
"""

import os
from datetime import datetime, timedelta, timezone

from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.sdk import dag, task
from pendulum import datetime as pendulum_datetime

from include.alerts import notify_failure

MAX_AGE = timedelta(minutes=15)


def _hour_prefix(source, when):
    return f"vehicles/source={source}/date={when:%Y-%m-%d}/hour={when:%H}/"


@dag(
    schedule="*/15 * * * *",
    start_date=pendulum_datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "cta",
        "retries": 2,
        "retry_delay": timedelta(seconds=30),
        # Task-level so it fires once, after retries are exhausted.
        "on_failure_callback": notify_failure,
    },
    tags=["cta", "monitoring"],
    doc_md=__doc__,
)
def cta_freshness():
    @task
    def check_source(source):
        s3 = S3Hook(aws_conn_id="aws_default").get_conn()
        bucket = os.environ["CTA_S3_BUCKET"]
        now = datetime.now(timezone.utc)

        # Just after the top of the hour the current partition is still empty,
        # so the previous hour is checked too.
        newest = None
        for when in (now, now - timedelta(hours=1)):
            response = s3.list_objects_v2(Bucket=bucket, Prefix=_hour_prefix(source, when))
            for obj in response.get("Contents", []):
                if newest is None or obj["LastModified"] > newest:
                    newest = obj["LastModified"]

        if newest is None:
            raise RuntimeError(f"No {source} files in the last two hour partitions")

        age = now - newest
        if age > MAX_AGE:
            raise RuntimeError(f"Newest {source} file is {age} old (limit {MAX_AGE})")
        print(f"{source}: newest file is {age} old")

    for source in ("bus", "train"):
        check_source.override(task_id=f"check_{source}")(source)


cta_freshness()

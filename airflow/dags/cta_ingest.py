"""
## cta_ingest

Every 3 minutes, snapshot every CTA bus and train position into S3:
`s3://<bucket>/vehicles/source=<bus|train>/date=YYYY-MM-DD/hour=HH/<source>_<timestamp>.json.gz`

Each record gets an `ingested_at` UTC timestamp so we know when *we* saw it,
separate from the vehicle's own report time.
"""

import os
from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, task
from pendulum import datetime as pendulum_datetime

from include.cta_client import get_bus_routes, get_bus_vehicles, get_train_positions
from include.s3_writer import write_snapshot


def _snapshot(source, records):
    snapshot_time = datetime.now(timezone.utc)
    ingested_at = snapshot_time.isoformat(timespec="seconds")
    stamped = [{**record, "ingested_at": ingested_at} for record in records]
    key = write_snapshot(os.environ["CTA_S3_BUCKET"], source, stamped, snapshot_time)
    print(f"Wrote {len(stamped)} {source} records to {key}")
    return key


@dag(
    schedule="*/3 * * * *",
    start_date=pendulum_datetime(2026, 10, 1, tz="UTC"),
    # Live positions can't be fetched for the past, so there's nothing to catch up on.
    catchup=False,
    # A slow run shouldn't overlap the next one and double our API usage.
    max_active_runs=1,
    default_args={
        "owner": "cta",
        "retries": 2,
        "retry_delay": timedelta(seconds=30),
        "execution_timeout": timedelta(minutes=2),
    },
    tags=["cta", "ingest"],
    doc_md=__doc__,
)
def cta_ingest():
    @task
    def ingest_bus():
        key = os.environ["CTA_BUS_API_KEY"]
        # Routes change rarely, but one extra call per run is cheap and avoids a stale list.
        routes = get_bus_routes(key)
        return _snapshot("bus", get_bus_vehicles(key, routes))

    @task
    def ingest_train():
        return _snapshot("train", get_train_positions(os.environ["CTA_TRAIN_API_KEY"]))

    ingest_bus()
    ingest_train()


cta_ingest()

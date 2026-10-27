"""Writes snapshots of API records to the S3 data lake as gzipped NDJSON."""

import gzip
import json

from airflow.providers.amazon.aws.hooks.s3 import S3Hook


def build_key(source, snapshot_time):
    """Hive-style UTC partitions, so Snowflake can COPY one hour at a time.

    UTC avoids the duplicate/missing hour that Chicago local time has at DST changes.
    """
    return (
        f"vehicles/source={source}/"
        f"date={snapshot_time:%Y-%m-%d}/hour={snapshot_time:%H}/"
        f"{source}_{snapshot_time:%Y%m%dT%H%M%SZ}.json.gz"
    )


def to_ndjson_gz(records):
    # One JSON object per line lets Snowflake load each record as its own VARIANT row.
    lines = "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records)
    return gzip.compress(lines.encode("utf-8"))


def write_snapshot(bucket, source, records, snapshot_time, aws_conn_id="aws_default"):
    """Upload one snapshot file and return its S3 key.

    An empty list still produces a (valid, empty) file, so the freshness check
    measures whether the pipeline ran, not whether buses happened to be running.
    """
    key = build_key(source, snapshot_time)
    S3Hook(aws_conn_id=aws_conn_id).load_bytes(
        to_ndjson_gz(records), key=key, bucket_name=bucket, replace=True
    )
    return key

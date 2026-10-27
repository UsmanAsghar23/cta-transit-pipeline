import gzip
import json
from datetime import datetime, timezone

from include.s3_writer import build_key, to_ndjson_gz


def test_build_key_uses_utc_partitions():
    ts = datetime(2026, 3, 8, 7, 5, 9, tzinfo=timezone.utc)
    assert build_key("bus", ts) == (
        "vehicles/source=bus/date=2026-03-08/hour=07/bus_20260308T070509Z.json.gz"
    )


def test_ndjson_round_trip():
    records = [{"vid": "1"}, {"vid": "2"}]
    lines = gzip.decompress(to_ndjson_gz(records)).decode().splitlines()
    assert [json.loads(line) for line in lines] == records


def test_empty_snapshot_is_still_a_valid_file():
    assert gzip.decompress(to_ndjson_gz([])) == b""

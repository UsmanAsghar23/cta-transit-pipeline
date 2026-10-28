"""Export the on-time mart to CSV so results survive the end of the Snowflake trial.

Run from the repo root:  python scripts/export_mart.py
Writes results/fct_delay_by_route_hour.csv, results/recent_positions.csv, and results/summary.csv.
"""

import csv
import os
import sys
from pathlib import Path

import snowflake.connector
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"

QUERIES = {
    "fct_delay_by_route_hour": """
        select *
        from CTA.ANALYTICS.FCT_DELAY_BY_ROUTE_HOUR
        order by hour_start, mode, route_id
    """,
    # The most recent hour of positions, for the network map in make_charts.py.
    "recent_positions": """
        select 'bus' as mode, route_id, round(latitude, 4) as latitude,
               round(longitude, 4) as longitude, is_delayed
        from CTA.ANALYTICS.STG_BUS_POSITIONS
        where recorded_at >= (select dateadd(hour, -1, max(recorded_at)) from CTA.ANALYTICS.STG_BUS_POSITIONS)
          and latitude is not null
        union all
        select 'train', line, round(latitude, 4), round(longitude, 4), is_delayed
        from CTA.ANALYTICS.STG_TRAIN_POSITIONS
        where recorded_at >= (select dateadd(hour, -1, max(recorded_at)) from CTA.ANALYTICS.STG_TRAIN_POSITIONS)
          and latitude is not null
    """,
    # Headline numbers for the README and resume.
    "summary": """
        select
            source,
            count(*)                                   as total_rows,
            count(distinct source_file)                as files_loaded,
            min(loaded_at)                             as first_loaded_at,
            max(loaded_at)                             as last_loaded_at,
            round(count(*) / greatest(datediff(hour, min(loaded_at), max(loaded_at)) / 24, 1))
                                                       as avg_rows_per_day
        from (
            select 'bus' as source, source_file, loaded_at from CTA.RAW.BUS_POSITIONS_RAW
            union all
            select 'train', source_file, loaded_at from CTA.RAW.TRAIN_POSITIONS_RAW
        )
        group by source
        order by source
    """,
}


def require_env(name):
    value = os.getenv(name)
    if not value:
        sys.exit(f"Missing {name}. See .env.example.")
    return value


def main():
    load_dotenv(REPO_ROOT / ".env")
    conn = snowflake.connector.connect(
        account=require_env("SNOWFLAKE_ACCOUNT"),
        user=require_env("SNOWFLAKE_USER"),
        authenticator="SNOWFLAKE_JWT",
        private_key_file=require_env("SNOWFLAKE_PRIVATE_KEY_PATH"),
        role=os.getenv("SNOWFLAKE_ROLE", "CTA_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "CTA_WH"),
    )
    RESULTS_DIR.mkdir(exist_ok=True)

    try:
        cursor = conn.cursor()
        for name, sql in QUERIES.items():
            cursor.execute(sql)
            path = RESULTS_DIR / f"{name}.csv"
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([col[0].lower() for col in cursor.description])
                rows = cursor.fetchall()
                writer.writerows(rows)
            print(f"Wrote {len(rows)} rows to {path.relative_to(REPO_ROOT)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""Smoke test: fetch live CTA data and print counts plus one sample per source.

Run from the repo root:  python scripts/try_api.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
# The client lives in airflow/include so the DAGs and this script share one copy.
sys.path.insert(0, str(REPO_ROOT / "airflow" / "include"))

from cta_client import get_bus_routes, get_bus_vehicles, get_train_positions  # noqa: E402


def require_env(name):
    value = os.getenv(name)
    if not value:
        sys.exit(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return value


def main():
    load_dotenv(REPO_ROOT / ".env")
    bus_key = require_env("CTA_BUS_API_KEY")
    train_key = require_env("CTA_TRAIN_API_KEY")

    routes = get_bus_routes(bus_key)
    print(f"Bus routes: {len(routes)}")

    buses = get_bus_vehicles(bus_key, routes)
    print(f"Buses in service: {len(buses)}")
    if buses:
        print(json.dumps(buses[0], indent=2))

    trains = get_train_positions(train_key)
    print(f"\nTrains in service: {len(trains)}")
    if trains:
        print(json.dumps(trains[0], indent=2))


if __name__ == "__main__":
    main()

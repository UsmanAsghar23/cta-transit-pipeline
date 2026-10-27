"""Thin client for the CTA Bus Tracker (v3) and Train Tracker APIs.

Returns plain dicts exactly as the APIs send them, so the raw layer in S3
keeps every field and parsing decisions live in dbt, where they're testable.
"""

import requests

BUS_BASE_URL = "https://www.ctabustracker.com/bustime/api/v3"
TRAIN_POSITIONS_URL = "https://lapi.transitchicago.com/api/1.0/ttpositions.aspx"

# getvehicles rejects more than 10 route designators per call.
BUS_ROUTES_PER_CALL = 10

# Train Tracker route codes. ttpositions accepts up to 8 per call, so one call covers all lines.
TRAIN_LINES = ["red", "blue", "brn", "g", "org", "p", "pink", "y"]

TIMEOUT_SECONDS = 20

# Bus errors that mean the whole run is broken, not just one quiet route.
FATAL_BUS_ERRORS = ("invalid api access key", "transaction limit")

# Train errCd values: 101 = invalid key, 102 = daily limit exceeded.
FATAL_TRAIN_ERROR_CODES = {"101", "102"}


class CTAApiError(Exception):
    """Raised when the API reports a problem that retrying the route won't fix."""


def _bus_request(endpoint, params):
    response = requests.get(
        f"{BUS_BASE_URL}/{endpoint}",
        params={**params, "format": "json"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json().get("bustime-response", {})

    # v3 returns per-route errors alongside data in the same 200 response,
    # e.g. "No data found for parameter" for a route with no buses overnight.
    for error in body.get("error", []):
        message = error.get("msg", "")
        if any(fatal in message.lower() for fatal in FATAL_BUS_ERRORS):
            raise CTAApiError(f"Bus Tracker {endpoint}: {message}")
    return body


def get_bus_routes(key):
    """Return all route designators currently in the Bus Tracker system."""
    body = _bus_request("getroutes", {"key": key})
    return [route["rt"] for route in body.get("routes", [])]


def get_bus_vehicles(key, routes):
    """Return the latest position of every bus on the given routes."""
    vehicles = []
    for start in range(0, len(routes), BUS_ROUTES_PER_CALL):
        batch = routes[start : start + BUS_ROUTES_PER_CALL]
        body = _bus_request(
            "getvehicles",
            # tmres=s gives second-level timestamps; the default is minutes only.
            {"key": key, "rt": ",".join(batch), "tmres": "s"},
        )
        vehicles.extend(body.get("vehicle", []))
    return vehicles


def get_train_positions(key):
    """Return every in-service 'L' train, each tagged with its line."""
    response = requests.get(
        TRAIN_POSITIONS_URL,
        params={"key": key, "rt": ",".join(TRAIN_LINES), "outputType": "JSON"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json().get("ctatt", {})

    error_code = str(body.get("errCd", "0"))
    if error_code in FATAL_TRAIN_ERROR_CODES:
        raise CTAApiError(f"Train Tracker error {error_code}: {body.get('errNm')}")
    if error_code != "0":
        raise CTAApiError(f"Unexpected Train Tracker error {error_code}: {body.get('errNm')}")

    trains = []
    for route in _as_list(body.get("route")):
        line = route.get("@name")
        # The JSON is converted from XML, so a line with one train comes back as a
        # dict instead of a list, and a line with no trains has no "train" key at all.
        for train in _as_list(route.get("train")):
            trains.append({**train, "line": line})
    return trains


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    return value

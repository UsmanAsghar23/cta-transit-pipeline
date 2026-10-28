"""Build README charts from the CSVs written by export_mart.py.

Run from the repo root:  python scripts/make_charts.py
Writes PNGs to results/charts/.
"""

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files; no display needed
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"
CHARTS_DIR = RESULTS_DIR / "charts"

# Routes need enough pings for their on-time ratio to mean something.
MIN_ROUTE_PINGS = 100

MODE_COLORS = {"bus": "#1f77b4", "train": "#c60c30"}
# API line code -> (display name, official color from GTFS routes.txt)
TRAIN_LINES = {
    "red": ("Red", "#C60C30"), "blue": ("Blue", "#00A1DE"), "brn": ("Brown", "#62361B"),
    "g": ("Green", "#009B3A"), "org": ("Orange", "#F9461C"), "p": ("Purple", "#522398"),
    "pink": ("Pink", "#E27EA6"), "y": ("Yellow", "#F9E300"),
}


def read_csv(name):
    with open(RESULTS_DIR / f"{name}.csv", newline="") as f:
        return list(csv.DictReader(f))


def on_time_pct(pings, delayed):
    # Weighted by pings, so a quiet route-hour doesn't count as much as a busy one.
    return 100 * (1 - delayed / pings) if pings else None


def chart_on_time_by_hour(mart):
    totals = defaultdict(lambda: [0, 0])  # (mode, hour) -> [pings, delayed]
    for row in mart:
        key = (row["mode"], int(row["hour_of_day"]))
        totals[key][0] += int(row["position_pings"])
        totals[key][1] += int(row["delayed_pings"])

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for mode, color in MODE_COLORS.items():
        hours = sorted(h for m, h in totals if m == mode)
        values = [on_time_pct(*totals[(mode, h)]) for h in hours]
        ax.plot(hours, values, marker="o", color=color, label=mode.capitalize())

    ax.set_title("On-time share of position pings by hour (Chicago time)")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("% of pings not flagged delayed")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(-0.5, 23.5)
    ax.grid(alpha=0.3)
    ax.legend()
    return save(fig, "on_time_by_hour.png")


def chart_worst_routes(mart, top_n=10):
    totals = defaultdict(lambda: [0, 0])
    names = {}
    for row in mart:
        key = (row["mode"], row["route_id"])
        totals[key][0] += int(row["position_pings"])
        totals[key][1] += int(row["delayed_pings"])
        names[key] = (row["route_name"] or "").strip()

    ranked = sorted(
        ((on_time_pct(*v), k) for k, v in totals.items() if v[0] >= MIN_ROUTE_PINGS),
    )[:top_n]

    labels = [f"{mode} {route}  {names[(mode, route)][:28]}" for _, (mode, route) in ranked]
    values = [pct for pct, _ in ranked]
    colors = [MODE_COLORS[mode] for _, (mode, _) in ranked]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(labels[::-1], values[::-1], color=colors[::-1])
    ax.set_title(f"Least on-time routes (min {MIN_ROUTE_PINGS} pings)")
    ax.set_xlabel("% of pings not flagged delayed")
    ax.set_xlim(min(values) - 5 if values else 0, 100)
    for i, v in enumerate(values[::-1]):
        ax.text(v + 0.2, i, f"{v:.1f}%", va="center", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    return save(fig, "worst_routes.png")


def chart_network_map(positions):
    fig, ax = plt.subplots(figsize=(7, 9))

    buses = [p for p in positions if p["mode"] == "bus"]
    ax.scatter(
        [float(p["longitude"]) for p in buses],
        [float(p["latitude"]) for p in buses],
        s=1, color="#9aa5b1", alpha=0.5, label="Bus position",
    )

    for line, (name, color) in TRAIN_LINES.items():
        pts = [p for p in positions if p["mode"] == "train" and p["route_id"].lower() == line]
        if pts:
            ax.scatter(
                [float(p["longitude"]) for p in pts],
                [float(p["latitude"]) for p in pts],
                s=6, color=color, label=f"{name} Line",
            )

    delayed = [p for p in positions if p["is_delayed"].lower() == "true"]
    ax.scatter(
        [float(p["longitude"]) for p in delayed],
        [float(p["latitude"]) for p in delayed],
        s=14, facecolors="none", edgecolors="black", linewidths=0.6, label="Flagged delayed",
    )

    # Correct for longitude degrees being shorter than latitude degrees at Chicago's latitude.
    ax.set_aspect(1 / math.cos(math.radians(41.88)))
    ax.set_title("One hour of CTA vehicle positions")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc="lower left", fontsize=7, markerscale=2, frameon=True)
    return save(fig, "network_map.png")


def save(fig, filename):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return path


def main():
    mart = read_csv("fct_delay_by_route_hour")
    chart_on_time_by_hour(mart)
    chart_worst_routes(mart)
    chart_network_map(read_csv("recent_positions"))


if __name__ == "__main__":
    main()

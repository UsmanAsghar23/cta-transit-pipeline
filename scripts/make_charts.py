"""Build README charts from the CSVs written by export_mart.py.

Run from the repo root:  python scripts/make_charts.py
Writes PNGs to results/charts/.
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files; no display needed
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"
CHARTS_DIR = RESULTS_DIR / "charts"

# Routes need enough pings for their on-time ratio to mean something.
MIN_ROUTE_PINGS = 100

MODE_PALETTE = {"Bus": "#2E86AB", "Train": "#C60C30"}
# API line code -> (display name, official color from GTFS routes.txt)
TRAIN_LINES = {
    "red": ("Red", "#C60C30"), "blue": ("Blue", "#00A1DE"), "brn": ("Brown", "#8B5A2B"),
    "g": ("Green", "#009B3A"), "org": ("Orange", "#F9461C"), "p": ("Purple", "#8E5CD9"),
    "pink": ("Pink", "#E27EA6"), "y": ("Yellow", "#F9E300"),
}
# Brown and Purple are lightened slightly from the official colors so they show on a dark map.


def weighted_on_time(df, by):
    """On-time % weighted by pings, so a quiet route-hour counts less than a busy one."""
    grouped = df.groupby(by, as_index=False)[["position_pings", "delayed_pings"]].sum()
    grouped["on_time_pct"] = 100 * (1 - grouped["delayed_pings"] / grouped["position_pings"])
    return grouped


def chart_on_time_by_hour(mart):
    hourly = weighted_on_time(mart, ["mode", "hour_of_day"])
    hourly["mode"] = hourly["mode"].str.capitalize()

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(
        data=hourly, x="hour_of_day", y="on_time_pct", hue="mode", palette=MODE_PALETTE,
        marker="o", markersize=8, linewidth=2.5, ax=ax,
    )
    # Fit the axis to the hours collected so far; it grows to the full day as data accumulates.
    first, last = hourly["hour_of_day"].min(), hourly["hour_of_day"].max()
    step = 1 if last - first <= 12 else 2
    ax.set(xlabel="Hour of day (Chicago time)", ylabel="Pings not flagged delayed",
           xlim=(first - 0.5, last + 0.5), xticks=range(first, last + 1, step))
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=1))
    ax.legend(title=None, frameon=False)
    title(ax, "On-time performance by hour", "Share of position pings CTA did not flag as delayed")
    return save(fig, "on_time_by_hour.png")


def chart_worst_routes(mart, top_n=10):
    routes = weighted_on_time(mart, ["mode", "route_id"])
    names = mart.groupby(["mode", "route_id"])["route_name"].first().fillna("").str.strip()
    routes = routes.merge(names.reset_index(), on=["mode", "route_id"])
    routes = routes[routes["position_pings"] >= MIN_ROUTE_PINGS].nsmallest(top_n, "on_time_pct")
    routes["label"] = (
        routes["mode"].str.capitalize() + " " + routes["route_id"] + "  ·  " + routes["route_name"].str[:26]
    )

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(
        data=routes, y="label", x="on_time_pct", hue="on_time_pct",
        palette="flare_r", legend=False, ax=ax,
    )
    for bar, pct in zip(ax.patches, routes["on_time_pct"]):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2, f"{pct:.1f}%",
                va="center", fontsize=10, color="#333")
    ax.set(xlabel="Pings not flagged delayed", ylabel=None,
           xlim=(math.floor(routes["on_time_pct"].min()) - 2, 100.5))
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
    sns.despine(left=True)
    title(ax, f"Least on-time routes", f"Routes with at least {MIN_ROUTE_PINGS} position pings")
    return save(fig, "worst_routes.png")


def chart_network_map(positions):
    background = "#0E1117"
    with plt.style.context("dark_background"):
        fig, ax = plt.subplots(figsize=(8, 10), facecolor=background)
        ax.set_facecolor(background)

        buses = positions[positions["mode"] == "bus"]
        ax.scatter(buses["longitude"], buses["latitude"], s=2.5, color="#9FB3D1",
                   alpha=0.6, linewidths=0, label="Bus")

        trains = positions[positions["mode"] == "train"]
        for code, (name, color) in TRAIN_LINES.items():
            pts = trains[trains["route_id"].str.lower() == code]
            if not pts.empty:
                ax.scatter(pts["longitude"], pts["latitude"], s=9, color=color,
                           linewidths=0, label=f"{name} Line")

        delayed = positions[positions["is_delayed"].astype(str).str.lower() == "true"]
        ax.scatter(delayed["longitude"], delayed["latitude"], s=40, facecolors="none",
                   edgecolors="#FFD166", linewidths=1, label="Flagged delayed")

        # Longitude degrees are shorter than latitude degrees at Chicago's latitude.
        ax.set_aspect(1 / math.cos(math.radians(41.88)))
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        legend = ax.legend(loc="lower left", fontsize=9, markerscale=2.5, frameon=False,
                           labelcolor="#DDDDDD")
        for handle in legend.legend_handles:
            handle.set_alpha(1)
        title(ax, "One hour of the CTA network",
              f"{len(buses):,} bus and {len(trains):,} train position reports", color="#EEEEEE")
        return save(fig, "network_map.png", facecolor=background)


def title(ax, main, sub, color="#222222"):
    # Bold title with a grey subtitle tucked underneath it.
    ax.set_title(main, loc="left", fontsize=15, fontweight="bold", color=color, pad=26)
    ax.annotate(sub, xy=(0, 1), xycoords="axes fraction", xytext=(0, 8),
                textcoords="offset points", fontsize=10.5, color="#888888", va="bottom")


def save(fig, filename, **kwargs):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight", **kwargs)
    plt.close(fig)
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return path


def main():
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)
    mart = pd.read_csv(RESULTS_DIR / "fct_delay_by_route_hour.csv", dtype={"route_id": str})
    positions = pd.read_csv(RESULTS_DIR / "recent_positions.csv", dtype={"route_id": str})

    chart_on_time_by_hour(mart)
    chart_worst_routes(mart)
    chart_network_map(positions)


if __name__ == "__main__":
    main()

"""
FR-8: Interactive Hotspot Map
FR-9: Charts and Summary Statistics

Inputs here are plain Python lists of dicts (Mongo aggregation/query
results), converted to Pandas for plotting -- replacing the Spark
DataFrame -> toPandas() conversion from the earlier version with a
direct pd.DataFrame(list_of_dicts) call.
"""

import os

import folium
import matplotlib
matplotlib.use("Agg")  # headless; no display server required
import matplotlib.pyplot as plt
import pandas as pd

import config
from src.spatial_grid import cell_polygon_coordinates


def build_hotspot_map(hotspots: list, cell_size: float, output_path: str) -> None:
    """FR-8: color-coded grid cells for the top-N hotspots, with popups."""
    if not hotspots:
        print("No hotspot cells to map -- skipping map generation.")
        return

    pdf = pd.DataFrame(hotspots)
    center_lat = pdf.apply(lambda r: (r["cell_y"] + 0.5) * cell_size, axis=1).mean()
    center_lon = pdf.apply(lambda r: (r["cell_x"] + 0.5) * cell_size, axis=1).mean()
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=12)  # default OpenStreetMap tiles, no API key needed

    max_count = pdf["incident_count"].max()
    half = cell_size / 2.0

    for row in hotspots:
        cell_center_lat = (row["cell_y"] + 0.5) * cell_size
        cell_center_lon = (row["cell_x"] + 0.5) * cell_size
        intensity = row["incident_count"] / max_count if max_count else 0
        color = _intensity_to_color(intensity)
        bounds = [
            [cell_center_lat - half, cell_center_lon - half],
            [cell_center_lat + half, cell_center_lon + half],
        ]
        popup_html = (
            f"<b>Cell ({row['cell_x']}, {row['cell_y']})</b><br>"
            f"Incidents: {row['incident_count']}<br>"
            f"Distinct categories: {row.get('distinct_categories', 'n/a')}<br>"
            f"Range: {row.get('earliest_incident', 'n/a')} to {row.get('latest_incident', 'n/a')}"
        )
        folium.Rectangle(
            bounds=bounds, color=color, fill=True, fill_color=color, fill_opacity=0.6,
            tooltip=f"{row['incident_count']} incidents",
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(fmap)

    _add_legend(fmap, max_count)
    _out_dir = os.path.dirname(output_path) or "."
    os.makedirs(_out_dir, exist_ok=True)
    fmap.save(output_path)
    print(f"FR-8: Interactive map saved -> {output_path}")


def _intensity_to_color(intensity: float) -> str:
    if intensity > 0.75:
        return "#800026"
    if intensity > 0.5:
        return "#BD0026"
    if intensity > 0.25:
        return "#FC4E2A"
    return "#FEB24C"


def _add_legend(fmap: folium.Map, max_count: int) -> None:
    legend_html = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background-color: white; padding: 10px; border: 2px solid grey;
                border-radius: 5px; font-size: 13px;">
        <b>Incident count</b><br>
        <i style="background:#FEB24C;width:12px;height:12px;display:inline-block;"></i> Low<br>
        <i style="background:#FC4E2A;width:12px;height:12px;display:inline-block;"></i> Medium<br>
        <i style="background:#BD0026;width:12px;height:12px;display:inline-block;"></i> High<br>
        <i style="background:#800026;width:12px;height:12px;display:inline-block;"></i> Highest (max {max_count})<br>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))


def plot_top_hotspots_bar(hotspots: list, output_path: str) -> None:
    pdf = pd.DataFrame(hotspots)
    pdf["cell_label"] = pdf.apply(lambda r: f"({r.cell_x},{r.cell_y})", axis=1)
    plt.figure(figsize=(10, 6))
    plt.bar(pdf["cell_label"], pdf["incident_count"], color="#BD0026")
    plt.xlabel("Grid cell")
    plt.ylabel("Incident count")
    plt.title("Top grid cells by crime count")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"FR-9: Chart saved -> {output_path}")


def plot_category_bar(category_counts: list, output_path: str, top_n: int = 15) -> None:
    pdf = pd.DataFrame(category_counts).head(top_n)
    plt.figure(figsize=(10, 6))
    plt.barh(pdf["category"][::-1], pdf["incident_count"][::-1], color="#2c7fb8")
    plt.xlabel("Incident count")
    plt.title(f"Crime counts by category (top {top_n})")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"FR-9: Chart saved -> {output_path}")


def plot_monthly_line(monthly_counts: list, output_path: str) -> None:
    pdf = pd.DataFrame(monthly_counts)
    if pdf.empty:
        print("No monthly data -- skipping monthly chart.")
        return
    plt.figure(figsize=(10, 6))
    plt.plot(pdf["year_month"], pdf["incident_count"], marker="o", color="#2c7fb8")
    plt.xlabel("Year-Month")
    plt.ylabel("Incident count")
    plt.title("Monthly crime counts")
    plt.xticks(rotation=60, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"FR-9: Chart saved -> {output_path}")


def plot_hourly_bar(hourly_counts: list, output_path: str) -> None:
    pdf = pd.DataFrame(hourly_counts)
    if pdf.empty:
        print("No valid hourly data -- skipping hourly chart.")
        return
    plt.figure(figsize=(10, 6))
    plt.bar(pdf["hour"], pdf["incident_count"], color="#41b6c4")
    plt.xlabel("Hour of day")
    plt.ylabel("Incident count")
    plt.title("Hourly crime distribution")
    plt.xticks(range(0, 24))
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"FR-9: Chart saved -> {output_path}")

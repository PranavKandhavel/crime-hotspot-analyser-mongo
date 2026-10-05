"""
Crime Hotspot Detection and Spatial-Temporal Analysis -- MongoDB Atlas port.

Run with:
    python main.py

See README.md for Atlas setup, dataset download, and what changed from
the earlier Spark version.
"""

import os
import time

import pandas as pd

import config
from src import db as dbmod
from src.data_loader import load_crime_data
from src.data_cleaning import clean_data
from src.spatial_grid import assign_grid_cells, build_grid_cell_documents, cell_polygon_coordinates
from src.ingest import ensure_indexes, load_crimes, load_grid_cells
from src.hotspot_analysis import aggregate_by_grid, write_counts_to_grid_cells, rank_hotspots
from src.temporal_analysis import (
    category_summary, hotspot_category_breakdown,
    monthly_counts, hourly_counts, day_night_comparison,
)
from src.visualization import (
    build_hotspot_map, plot_top_hotspots_bar, plot_category_bar,
    plot_monthly_line, plot_hourly_bar,
)
from src import spatial_queries as sq


def _export_csv(records: list, path: str) -> None:
    pd.DataFrame(records).to_csv(path, index=False)
    print(f"FR-10: Export saved -> {path}")


def main() -> None:
    start_time = time.time()
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.CHARTS_DIR, exist_ok=True)

    db = dbmod.get_db()

    try:
        # --- FR-1: Load -------------------------------------------------------
        raw_df = load_crime_data(config.INPUT_CSV_PATH)

        # --- FR-2: Clean --------------------------------------------------------
        cleaned_df, clean_stats = clean_data(
            raw_df, config.COLUMNS, config.DATE_FORMAT,
            config.LAT_MIN, config.LAT_MAX, config.LON_MIN, config.LON_MAX,
        )

        # --- FR-3: Spatial grid -------------------------------------------------
        gridded_df = assign_grid_cells(cleaned_df, config.GRID_CELL_SIZE_DEGREES)
        grid_cell_docs = build_grid_cell_documents(gridded_df, config.GRID_CELL_SIZE_DEGREES)

        # --- Load into Atlas ------------------------------------------------------
        ensure_indexes(db)
        inserted_crimes = load_crimes(db, gridded_df, config.INSERT_BATCH_SIZE)
        load_grid_cells(db, grid_cell_docs)

        # --- FR-4: Aggregation + FR-5: Hotspot ranking --------------------------
        grid_counts = aggregate_by_grid(db)
        write_counts_to_grid_cells(db, grid_counts)
        hotspots = rank_hotspots(grid_counts, config.TOP_N_HOTSPOTS)

        # --- Acceptance check: row-count conservation ---------------------------
        # Every retained crime document must land in exactly one grid cell, and
        # the grid-cell counts must sum back to the total document count -- this
        # catches silent row loss/duplication introduced anywhere upstream.
        total_crime_docs = db[config.COLLECTION_CRIMES].count_documents({})
        sum_of_grid_counts = sum(c["incident_count"] for c in grid_counts)
        assert sum_of_grid_counts == total_crime_docs, (
            f"Row-count conservation check FAILED: crimes={total_crime_docs} "
            f"vs sum(grid counts)={sum_of_grid_counts}"
        )

        # --- FR-6: Category analysis ----------------------------------------------
        cat_summary = category_summary(db)
        hotspot_cats = hotspot_category_breakdown(db, hotspots)

        # --- FR-7: Temporal analysis -----------------------------------------------
        monthly = monthly_counts(db)
        hourly = hourly_counts(db)
        day_night = day_night_comparison(db)

        # --- FR-8: Map + FR-9: Charts ------------------------------------------------
        build_hotspot_map(hotspots, config.GRID_CELL_SIZE_DEGREES,
                           os.path.join(config.OUTPUT_DIR, "hotspot_map.html"))
        plot_top_hotspots_bar(hotspots, os.path.join(config.CHARTS_DIR, "top_hotspots_bar.png"))
        plot_category_bar(cat_summary, os.path.join(config.CHARTS_DIR, "category_bar.png"))
        plot_monthly_line(monthly, os.path.join(config.CHARTS_DIR, "monthly_line.png"))
        plot_hourly_bar(hourly, os.path.join(config.CHARTS_DIR, "hourly_bar.png"))

        # --- FR-10: Exports -----------------------------------------------------------
        _export_csv(grid_counts, os.path.join(config.OUTPUT_DIR, "grid_crime_counts.csv"))
        _export_csv(hotspots, os.path.join(config.OUTPUT_DIR, "top_hotspots.csv"))
        _export_csv(cat_summary, os.path.join(config.OUTPUT_DIR, "crime_category_summary.csv"))
        _export_csv(hotspot_cats, os.path.join(config.OUTPUT_DIR, "hotspot_category_breakdown.csv"))
        _export_csv(monthly, os.path.join(config.OUTPUT_DIR, "monthly_crime_summary.csv"))
        _export_csv(hourly, os.path.join(config.OUTPUT_DIR, "hourly_crime_summary.csv"))
        _export_csv(day_night, os.path.join(config.OUTPUT_DIR, "day_night_summary.csv"))

        # --- Spatial query catalog demo ------------------------------------------------
        # Exercises every operation from the requirements list against the real
        # loaded data. Centered on the #1 hotspot so results are non-empty.
        _run_spatial_query_demo(db, hotspots, grid_cell_docs)

        elapsed = time.time() - start_time
        num_occupied_cells = len(grid_counts)

        print("=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Input record count:          {clean_stats['input_count']}")
        print(f"Valid (cleaned) record count: {clean_stats['cleaned_count']}")
        print(f"Removed record count:        {clean_stats['total_removed']}")
        print(f"Documents loaded into Atlas: {inserted_crimes}")
        print(f"Grid cells with incidents:   {num_occupied_cells}")
        print(f"Hotspot cells exported:      {config.TOP_N_HOTSPOTS}")
        print(f"Row-count conservation check: PASSED "
              f"({total_crime_docs} in Atlas == {sum_of_grid_counts} summed across cells)")
        print(f"Elapsed time:                {elapsed:.1f}s")
        print(f"Output directory:            {os.path.abspath(config.OUTPUT_DIR)}")
        print("Outputs:")
        for fname in sorted(os.listdir(config.OUTPUT_DIR)):
            if os.path.isfile(os.path.join(config.OUTPUT_DIR, fname)):
                print(f"  - {os.path.join(config.OUTPUT_DIR, fname)}")
        for fname in sorted(os.listdir(config.CHARTS_DIR)):
            print(f"  - {os.path.join(config.CHARTS_DIR, fname)}")

    finally:
        dbmod.close()


def _run_spatial_query_demo(db, hotspots: list, grid_cell_docs: list) -> None:
    print("=" * 60)
    print("SPATIAL QUERY CATALOG DEMO")
    print("=" * 60)

    if not hotspots:
        print("No hotspots available -- skipping spatial query demo.")
        return

    top = hotspots[0]
    center = [
        (top["cell_x"] + 0.5) * config.GRID_CELL_SIZE_DEGREES,
        (top["cell_y"] + 0.5) * config.GRID_CELL_SIZE_DEGREES,
    ]
    top_polygon = {"type": "Polygon", "coordinates": cell_polygon_coordinates(
        top["cell_x"], top["cell_y"], config.GRID_CELL_SIZE_DEGREES)}

    knn = sq.query_knn(db, center, config.KNN_DEFAULT_K)
    print(f"KNN search: {len(knn)} nearest crimes to top-hotspot center")

    knn_join = sq.query_knn_join(db, config.KNN_JOIN_K, config.KNN_JOIN_SAMPLE_SIZE)
    print(f"KNN join: ran for {len(knn_join)} source points, "
          f"{config.KNN_JOIN_K} neighbors each")

    contained = sq.query_containment(db, top_polygon)
    print(f"Containment: {len(contained)} crimes inside top-hotspot polygon")

    half_box = config.GRID_CELL_SIZE_DEGREES * 2
    range_box = sq.query_spatial_range_box_euclidean(
        db, [center[0] - half_box, center[1] - half_box], [center[0] + half_box, center[1] + half_box])
    print(f"Spatial range search (Euclidean box): {len(range_box)} crimes")

    buffer_result = sq.query_proximity_buffer(
        db, center, config.PROXIMITY_INNER_RADIUS_M, config.PROXIMITY_OUTER_RADIUS_M)
    print(f"Proximity buffer: {len(buffer_result['within_inner'])} within inner radius, "
          f"{len(buffer_result['buffer_ring'])} in the buffer ring")

    adjacent = sq.query_adjacency(db, top["cell_x"], top["cell_y"])
    print(f"Adjacency: {len(adjacent)} grid cells touch the top-hotspot cell")

    agg = sq.query_spatial_aggregation(db, top_polygon)
    print(f"Spatial aggregation: {len(agg)} categories within top-hotspot polygon")

    join_cells = grid_cell_docs[:min(5, len(grid_cell_docs))]
    joined = sq.spatial_join_points_to_polygons(db, join_cells)
    print(f"Spatial join: ran geometric point-in-polygon join over {len(join_cells)} cells")

    intersecting = sq.overlay_intersects(db, top_polygon)
    print(f"Overlay - Intersects: {len(intersecting)} grid cells intersect the top-hotspot polygon")

    if len(hotspots) >= 2:
        second_polygon = {"type": "Polygon", "coordinates": cell_polygon_coordinates(
            hotspots[1]["cell_x"], hotspots[1]["cell_y"], config.GRID_CELL_SIZE_DEGREES)}
        merged = sq.overlay_union([top_polygon, second_polygon])
        print(f"Overlay - Union: merged top-2 hotspot cells -> geometry type {merged['type']}")
        symdiff = sq.overlay_symmetric_difference(top_polygon, second_polygon)
        print(f"Overlay - Symmetric difference computed between top-2 hotspot cells")
        identity = sq.overlay_identity(top_polygon, second_polygon)
        print(f"Overlay - Identity: overlap_with_b present = {identity['overlap_with_b'] is not None}, "
              f"a_only present = {identity['a_only'] is not None}")

    nearest_with_dist = sq.query_nearest_with_geodetic_distance(db, center, 5)
    if nearest_with_dist:
        print(f"Distance measurement (geodetic): nearest crime is "
              f"{nearest_with_dist[0]['distance_m']:.1f}m away")
    if len(knn) >= 2:
        eu = sq.distance_euclidean(knn[0]["location"]["coordinates"], knn[1]["location"]["coordinates"])
        print(f"Distance measurement (Euclidean, degrees): {eu:.6f} between two nearest points")

    print()


if __name__ == "__main__":
    main()

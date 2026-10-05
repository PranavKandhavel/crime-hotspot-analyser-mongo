# Crime Hotspot Detection and Spatial-Temporal Analysis (MongoDB Atlas port)

Same project goal as before -- identify high-count crime grid cells,
analyze by category and time, visualize on a map -- but re-architected
onto **MongoDB Atlas** instead of Apache Spark, with a full spatial query
catalog (overlay, proximity, adjacency, KNN, containment, joins, etc.)
built against real geospatial indexes.

**Still descriptive, not predictive.** Ranked cells are "high-count
cells," not statistically validated clusters -- see Limitations.

---

## 0. What you MUST change before this runs

If you only read one section, read this one.

| What | Where | Why |
|---|---|---|
| Your Atlas connection string | `.env` (copy from `.env.example`) | Nothing connects without this |
| Dataset file | `data/crime_data.csv` | Not included -- see Section 3 |
| Column names (only if NOT using Chicago data) | `config.py` -> `COLUMNS` | Must match your CSV's actual headers |
| Date format (only if NOT using Chicago data) | `config.py` -> `DATE_FORMAT` | Must match your CSV's date string pattern |

Everything else (grid size, hotspot count, day/night hours, query radii)
is already set to sensible defaults in `config.py` and doesn't need
touching to get a first run working.

---

## 1. What changed from the Spark version, and why

| Concern | Old (Spark) | New (MongoDB Atlas) |
|---|---|---|
| Compute engine | PySpark, local cluster | None -- Atlas does the heavy lifting; Python is just a client |
| Requires Java | Yes | **No** -- this was the whole Java-version headache before; it's gone |
| Data loading | `spark.read.csv()` | `pandas.read_csv()` |
| "Distributed groupBy" | Spark `groupBy().agg()` | MongoDB aggregation pipeline `$group` |
| Grid-cell storage | In-memory Spark DataFrame | Two real Atlas collections: `crimes` (points) and `grid_cells` (polygons) |
| Spatial queries | None (grid was just an attribute, `cell_x`/`cell_y` equality) | Real geospatial operators: `$near`, `$geoWithin`, `$geoIntersects`, `$geoNear`, 2dsphere + 2d indexes |
| Technical-depth demo | `.explain()` physical plan | Aggregation `explain` + the full spatial query catalog (Section 6) |

The data pipeline shape is the same (load -> clean -> grid -> aggregate
-> analyze -> visualize -> export), and the FR-1 through FR-10 structure
from the original PRD is preserved and labeled in the code and output. What
changed is the engine underneath, plus a new layer of real spatial queries
that wasn't in the original scope.

---

## 2. MongoDB Atlas setup (walk through once)

1. **Create an account** at [cloud.mongodb.com](https://cloud.mongodb.com) -- "Try Free," no credit card needed.
2. **Create an Organization and Project** (any names, e.g. "CrimeHotspotAnalyzer").
3. **Deploy a free M0 cluster**: Create -> Build a Database -> select **M0 (Free)** tier -> pick a provider/region close to you -> Create. Takes 1-3 minutes.
4. **Create a database user**: Database Access (sidebar) -> Add New Database User -> username/password. Save these. Avoid `@ / :` in the password, or URL-encode them if you must use one.
5. **Allow your IP**: Network Access (sidebar) -> Add IP Address -> "Allow Access from Anywhere" (0.0.0.0/0) is fine for this project; not something you'd do in production.
6. **Get your connection string**: your cluster -> Connect -> Drivers -> Python. You'll get something like:
   ```
   mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
7. **Set it locally**:
   ```bash
   cp .env.example .env
   # edit .env, paste your real URI into MONGO_URI
   ```
   `.env` is in `.gitignore` -- never commit your real credentials.

You do NOT need to manually create the database or collections, or the
indexes -- `main.py` does that on every run (`src/ingest.py`
`ensure_indexes()`).

---

## 3. Setup and install

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

No Java required this time.

---

## 4. Get a dataset

Same recommendation as before -- the Chicago data still works, no changes
needed to use it.

1. https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-present/ijzp-q8t2
2. **Filter first** -- the full dataset is multi-million rows. Use the
   page's Filter tool to restrict to a date range (e.g. one year), then
   **Export -> CSV**. Or pull a bounded slice via the API:
   ```
   https://data.cityofchicago.org/resource/ijzp-q8t2.csv?$limit=50000&$where=date>'2023-01-01'
   ```
3. Save as `data/crime_data.csv`.

Alternatives: a pre-filtered 2018-2019 Chicago extract
(https://zenodo.org/records/3902623), LA (`data.lacity.org`), or SF
(`datasf.org`) -- if you use one of these, update `COLUMNS` and
`DATE_FORMAT` in `config.py` to match its actual column names/date format.

---

## 5. Run

```bash
python main.py
```

This will, in order: load and clean the CSV, assign grid cells, create
Atlas indexes, load both collections, aggregate hotspots, run category/
temporal analysis, run the full spatial query catalog demo (Section 6),
generate the map/charts, export CSVs, and print an execution summary --
same shape as the Spark version's summary, with a `MongoDB documents
loaded` line added.

Each run clears and reloads both collections (`delete_many({})` before
insert), so it's safe to re-run repeatedly while you're developing.

---

## 6. The spatial query catalog (`src/spatial_queries.py`)

Every operation from your requirements list is implemented here, each as
its own documented function. `main.py`'s `_run_spatial_query_demo()` runs
all of them once against the real loaded data so you see them actually
execute.

| Your requirement | Function | MongoDB mechanism |
|---|---|---|
| Intersects | `overlay_intersects` | `$geoIntersects` (native) |
| Union | `overlay_union` | **Shapely** (no native equivalent -- see note below) |
| Symmetrical Difference | `overlay_symmetric_difference` | **Shapely** |
| Identity | `overlay_identity` | **Shapely** |
| Proximity (buffer) | `query_proximity_buffer` | `$geoWithin` + `$centerSphere` (two radii -> donut) |
| Adjacency | `query_adjacency` | `$geoIntersects` (zero-distance proximity) |
| Distance (Euclidean) | `distance_euclidean` | Pure Python planar math (also what a 2d-index `$near` ranks by) |
| Distance (geodetic) | `distance_geodetic_haversine`, `query_nearest_with_geodetic_distance` | Haversine formula; `$geoNear` with `distanceField` |
| Spatial aggregation | `query_spatial_aggregation` | `$match` on `$geoWithin` + `$group` |
| Spatial join | `spatial_join_points_to_polygons` | `$geoWithin` run per-polygon (true geometric join, not an attribute join) |
| Intersection (as geometry) | `overlay_identity`'s `overlap_with_b`, or call Shapely directly | **Shapely** |
| Spatial range search | `query_spatial_range_box_euclidean`, `query_containment` | `$geoWithin` + `$box` (2d/legacy) or `$geometry` (2dsphere) |
| KNN search | `query_knn` | `$near` on 2dsphere index |
| KNN join | `query_knn_join` | One `$near` query per source point (documented limitation below) |
| Containment | `query_containment` | `$geoWithin` + `$geometry` |

### Important honesty note: what Mongo can and can't do here

MongoDB's geo operators **test** spatial relationships (is this point
inside that polygon? how far apart are two things?) but **none of them
compute a new geometry**. True overlay algebra -- Union, Symmetric
Difference, Identity -- needs actual polygon-clipping math, which Mongo
doesn't implement (this is the same reason PostGIS or Apache Sedona
exist as separate tools). Those three functions pull geometry out of
Mongo and use **Shapely** client-side. Everything else in the table above
is a real, native MongoDB query -- worth saying explicitly in your report
so it's clear which is which.

### Why two coordinate fields exist on every crime document

```json
"location":        { "type": "Point", "coordinates": [lon, lat] },  // 2dsphere index -> geodetic distance
"location_legacy":  [lon, lat]                                       // 2d index -> planar/Euclidean distance
```

This is what makes the Euclidean-vs-geodetic distinction in the table
above a real, queryable thing rather than just two Python functions: the
index type Mongo uses actually determines which distance metric a `$near`
query ranks by.

### Why grid cells are stored as real polygons

`grid_cells` isn't just `cell_x`/`cell_y` counters -- each occupied cell
is a GeoJSON `Polygon` document. That's what gives the overlay/
containment/adjacency/join queries actual geometry to operate on, without
needing a separate administrative-boundaries dataset. It also means the
existing hotspot-ranking logic (FR-4/FR-5) and the new spatial-query
catalog share the same underlying grid, rather than being two disconnected
features.

---

## 7. Outputs (`outputs/`)

Same as the Spark version -- `hotspot_map.html`, the 7 summary CSVs, and
`charts/*.png`. See the original PRD / earlier README section if you need
the full list again; nothing changed here.

---

## 8. Testing

```bash
pytest tests/ -v
```

- `test_spatial_grid.py` -- grid-cell math and polygon construction, pure
  Python, no Mongo needed.
- `test_spatial_queries_offline.py` -- distance math and the three
  Shapely-based overlay functions, also no Mongo needed.

Everything else in `spatial_queries.py` (KNN, containment, proximity,
adjacency, joins, `$geoIntersects`) needs a live Atlas cluster to
exercise meaningfully -- run `python main.py` against your own cluster to
see those execute; the printed demo output in Section 6's table is your
functional test of those paths.

The pipeline also self-checks **row-count conservation** on every run:
the sum of per-cell incident counts must equal the total document count
in `crimes`. If a query anywhere silently dropped or duplicated
documents, this assertion fails loudly instead of letting bad numbers
reach your report.

---

## 9. Limitations (documented deliberately)

- **Grid cells, not a projected/metric grid.** Same caveat as before --
  degrees aren't uniform ground distance outside the equator.
- **"Hotspots" are high-count cells, not statistically significant
  clusters.** No Getis-Ord Gi*/Moran's I test applied.
- **No predictive claim** -- historical report concentrations only.
- **KNN join is O(n) Mongo calls**, one `$near` per source point (see
  `query_knn_join`'s docstring). Fine at this project's scale
  (`KNN_JOIN_SAMPLE_SIZE` in `config.py` keeps the demo to 25 points by
  default); a production system at real scale would batch this
  differently or use an engine built for joins.
- **Union/Symmetric Difference/Identity are Shapely, not Mongo** -- see
  Section 6's honesty note. Don't present these as native MongoDB
  capability in your report; they're a legitimate client-side complement
  to it.
- Records with valid coordinates but unparseable/missing dates are kept
  for spatial analysis but excluded from every temporal/category-by-time
  breakdown (same as before).

---

## 10. Project structure

```
crime-hotspot-mongo/
├── .env.example                 # copy to .env, fill in your Atlas URI
├── data/                        # place crime_data.csv here (not included)
├── outputs/                     # generated on each run
│   └── charts/
├── src/
│   ├── db.py                    # Atlas connection handling
│   ├── data_loader.py           # FR-1 (pandas, was Spark)
│   ├── data_cleaning.py         # FR-2 (pandas, was Spark)
│   ├── spatial_grid.py          # FR-3 — grid math + GeoJSON polygon construction
│   ├── ingest.py                # builds documents, creates indexes, bulk-loads Atlas
│   ├── hotspot_analysis.py      # FR-4, FR-5 (Mongo aggregation, was Spark)
│   ├── temporal_analysis.py     # FR-6, FR-7 (Mongo aggregation, was Spark)
│   ├── spatial_queries.py       # the full query catalog — Section 6
│   └── visualization.py         # FR-8, FR-9 (unchanged logic, new input shape)
├── tests/
│   ├── test_spatial_grid.py
│   └── test_spatial_queries_offline.py
├── config.py                    # all tunables: Mongo URI/DB names, columns, grid, query radii
├── main.py                      # orchestrates the full pipeline + spatial query demo
└── requirements.txt
```

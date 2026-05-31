# Plan: GeoParquet Dataset Builder

## Context
Build a homogeneous quarterly-aggregate GeoParquet dataset from 15+ years of RIMNET/RREMS radiation monitoring data (2010–2026). Data spans two broad format families and two monitoring eras. Newer data (2025+) has lat/lon + location names; 2023–2024 has lat/lon but no names; pre-2023 has names but no coordinates. The strategy is to build a canonical location registry from 2025+ fixed monthly CSVs, then join coordinates backward to all older data. Monthly streaming data (2022 Jul+) is aggregated to quarterly to match historical granularity.

The parsing/reading layer does not yet exist — only download and discovery are implemented.

---

## Target Schema (one row = one location × one quarter)

| Column | Type | Notes |
|---|---|---|
| `location_name` | `str` | Normalised (whitespace + `*` stripped) |
| `geometry` | `Point (WGS84)` | Nullable for decommissioned sites |
| `year` | `int` | |
| `quarter` | `int` | 1–4 |
| `monitor_type` | `"fixed" \| "mobile"` | |
| `mean` | `float` | µGy/h |
| `min` | `float` | µGy/h |
| `max` | `float` | µGy/h |
| `std_dev` | `float` | µGy/h |
| `site_normal` | `float \| null` | Null for 2010–2011 (column absent) and all mobile files |

---

## Source File Format Summary

Inspection of the actual `bin/` directory revealed two families of files: pre-aggregated quarterly stats (2010–2022 Q2) and raw half-hourly streaming readings (2022 Jul–present). Within each family the schema is consistent enough to be handled by a single reader function per family.

### Family 1 — Stats files (2010–2022 Q2)

All files in this family contain one row per monitoring site, already aggregated over the quarter. They exist as either CSV or Excel (`.xlsx`). The table below captures what was observed on disk:

| Era | Extension | Monitor split | Preamble depth | Columns present |
|---|---|---|---|---|
| 2010–2011 | `.csv` | Fixed only | 0 rows | `Location, Units, Mean, Standard Deviation, Max, Min` |
| 2012–2013 Q1 | `.csv` | Fixed only | 6–7 rows | `Location, Site Normal Level, Std Dev, Mean, Min, Max` |
| 2013 Q2–2015 | `.xlsx` | Fixed only | 1 row (title) | `Location, Units, Site Normal Level, Standard Deviation, Mean, Max, Min` |
| 2016–2018 | `.xlsx` | Fixed + Mobile | 1 row (title) | same |
| 2019 | `.xlsx` + `.csv` | Fixed + Mobile | 1 row / 1–3 rows | same |
| 2020–2022 Q2 | `.csv` | Fixed + Mobile | 1–2 rows | same |

Key observations:
- **Preamble depth is not fixed** and must be discovered at read-time by scanning for the row where the first cell equals `"Location"` (case-insensitive). A fixed `header_row` offset is incorrect for most files.
- **`site_normal` is absent in 2010–2011** files. Its presence must be detected, not assumed.
- **Column name variants**: `Std Dev` and `Standard Deviation` both appear. `Site Normal Level` is the consistent name post-2011.
- **Mobile data begins in 2016.** Pre-2016 files are fixed-only.

### Family 2 — Monthly streaming files (2022 Jul–present)

All files contain raw half-hourly readings: ~85k–400k rows per file. These must be aggregated to quarterly stats before joining with Family 1 data.

Column names are inconsistent across sub-eras and require normalisation before processing:

| Sub-era | Files | Column name style | `monitor_location`? | `site_normal`? |
|---|---|---|---|---|
| 2022 Jul–Dec fixed | `*fixed*` | **Title Case** (`Reading Date & Time`, `Site Latitude`, …) | No | Yes |
| 2022 Jul–Dec mobile | `*mobile*` | snake\_case | No | No |
| 2023–2024 | all | snake\_case | No | Fixed only |
| 2025 Jan–Jul | all | snake\_case | Yes | Fixed only |
| 2025 Aug+ | all | snake\_case | Yes | Fixed only |

Column name normalisation map (applied before any other processing):

| Raw name | Normalised name |
|---|---|
| `Reading Date & Time` | `reading_date` |
| `Site Latitude` | `latitude` |
| `Site Longitude` | `longitude` |
| `Site Normal` | `site_normal` |
| `Reading` | `reading` |

After normalisation, `monitor_location` present → use directly (2025+); absent → resolve via `LocationRegistry.lookup_by_coords` (2023–2024) or leave null (2022 Jul–Dec, no location names available).

Note: the lat/lon values stored in the dataset rows for Jan–Jul 2025 are the lower-accuracy pre-upgrade coordinates. Only the `LocationRegistry` — built exclusively from Aug 2025+ files — uses the corrected coordinates, and those are what get attached to all pre-2023 rows during the geometry join step.

Mobile files **never** have `site_normal` across any sub-era. Always set to null for mobile.

---

## New Files

### `packages/uk-rimnet-core/src/uk_rimnet_core/_location_registry.py`

`LocationRegistry` — builds the canonical name→coords and coords→name lookup from all fixed monthly CSVs that carry location names, using a tiered priority strategy.

In August 2025 UKHSA upgraded the fixed monitor network and published corrected, higher-accuracy lat/lon coordinates for many sites. The registry must therefore be built in priority order so that the best available coordinates always win, while still capturing any sites that have since been decommissioned and would otherwise be lost.

**Build order (highest priority last, so later writes overwrite earlier ones):**

1. **All pre-Aug 2025 fixed monthly files that carry `monitor_location`** (Jan–Jul 2025) — lower-accuracy coordinates, but may include sites subsequently decommissioned. Provides a fallback for any name not present in Aug 2025+ data.
2. **Aug 2025+ fixed monthly files** — high-accuracy corrected coordinates. These overwrite any entry already written in step 1, so every site present in both periods ends up with the best coordinates.

The result: every location name ever recorded in any fixed monthly file gets an entry, and that entry carries the most accurate coordinates available for it.

```python
class LocationRegistry:
    def build(self) -> None
    def lookup_by_name(self, name: str) -> tuple[float, float] | None
    def lookup_by_coords(self, lat: float, lon: float, tolerance: float = 0.001) -> str | None
```

- Strips whitespace and `*` from `monitor_location` before indexing
- Decommissioned sites (present in pre-Aug 2025 files but absent from Aug 2025+ files) will retain their pre-upgrade coordinates — any coordinate is better than none
- Active sites will have their Aug 2025+ corrected coordinates
- Used to resolve names for 2023–2024 data (coord lookup) and coordinates for pre-2023 data (name lookup)

### `packages/uk-rimnet-core/src/uk_rimnet_core/_readers.py`

Two private reader functions, each returning a standard intermediate `pl.DataFrame` with columns:
`location_name, year, quarter, monitor_type, mean, min, max, std_dev, site_normal`

---

**`read_stats_file(path, year, quarter, monitor_type)`**

Handles all Family 1 files — both CSV and Excel, all preamble depths. Dispatches on file extension.

Algorithm:
1. Load all rows without a fixed header: `pl.read_csv(path, has_header=False, encoding="latin-1")` / `pl.read_excel(path, has_header=False)`
2. Scan rows to find the first row where the first cell equals `"Location"` (case-insensitive). This is the header row.
3. Slice from that row downward; promote the first row to column names.
4. Drop rows where `Location` is null or empty (blank separator rows present in some files).
5. Strip whitespace and `*` from `Location`.
6. Map column names: `Standard Deviation` / `Std Dev` → `std_dev`; `Site Normal Level` → `site_normal`.
7. If `site_normal` column is absent (2010–2011 files), add it as a null float column.
8. Cast all stat columns to `Float64`. Select and rename to the standard intermediate schema.

---

**`read_monthly_csv(path, year, month, monitor_type, registry)`**

Handles all Family 2 files (2022 Jul – present). One function for all three sub-eras.

Algorithm:
1. Load with `pl.read_csv(path, encoding="latin-1")`.
2. Apply column name normalisation map (Title Case → snake\_case).
3. Drop junk trailing columns (unnamed / RREMS metadata columns).
4. Cast `reading` and `site_normal` (if present) to `Float64`.
5. Group by `(latitude, longitude)`, aggregate: `mean(reading)`, `min(reading)`, `max(reading)`, `std(reading)`.
6. If `monitor_location` column is present: strip whitespace, use as `location_name`.
7. Else: resolve each `(lat, lon)` via `registry.lookup_by_coords(lat, lon)`.
8. `quarter = ceil(month / 3)`.
9. `site_normal`: mean of `site_normal` column per group if present (fixed files); null for mobile.
10. Attach `year`, `quarter`, `monitor_type`. Return standard intermediate schema.

---

**Period/type inference helper: `_parse_file_metadata(path: Path) -> _FileMeta`**

Parses `year`, `quarter` (or `month`), and `monitor_type` from the filename. The year is taken from the parent directory name (more reliable than filename). `monitor_type` defaults to `"fixed"` for pre-2016 files.

Quarter/month inference from filename stem (case-insensitive):

| Pattern examples | Quarter / month |
|---|---|
| `Q1`, `quarter-1`, `Quarter_1`, `q1-jan-mar` | Q1 |
| `jan-mar`, `january-march` | Q1 |
| `Q2`, `q2-apr-jun`, `apr-jun`, `april-june`, `Ap-Jun` | Q2 |
| `Q3`, `q3-jul-sep`, `jul-sep`, `july-september` | Q3 |
| `Q4`, `q4-oct-dec`, `oct-dec`, `october-december` | Q4 |
| `jan`, `feb`, … `dec`, `_01_`, `_02_`, … `_12_` | month number |

`monitor_type` inference: presence of `fixed` or `mobile` (case-insensitive) in the filename stem. Default `"fixed"` if neither present (pre-2016 era).

The switch from stats-file to monthly-streaming format within 2022 is determined purely by whether the file matches a monthly streaming pattern (single month name or `_MM_` in stem) vs a quarterly stats pattern.

### `packages/uk-rimnet-core/src/uk_rimnet_core/dataset.py`

Public module.

```python
class DatasetBuilder:
    """Builds a homogeneous quarterly GeoParquet dataset from all downloaded RIMNET/RREMS files."""

    def __init__(self, source_dir: Path) -> None: ...

    def build(self) -> gpd.GeoDataFrame:
        """Discover all data files, read and normalise each, join geometries, return GeoDataFrame."""

    def write_geoparquet(self, output_path: Path) -> None:
        """Build dataset and write to GeoParquet."""
```

Internally:
1. Instantiate and build `LocationRegistry` from `source_dir` using only fixed monthly files from August 2025 onwards (`2025_MM_fixed.csv` where MM ≥ 08, `2026_*_fixed.csv`, etc.) — these carry the corrected high-accuracy coordinates published with the August 2025 network upgrade.
2. Walk `source_dir` recursively for `.csv` and `.xlsx` files, skip `.DS_Store` and other non-data files.
3. For each file, call `_parse_file_metadata` then route to `read_stats_file` or `read_monthly_csv`.
4. `pl.concat` all intermediate DataFrames.
5. Join lat/lon from `LocationRegistry.lookup_by_name`.
6. Convert to `gpd.GeoDataFrame` with `shapely.Point(lon, lat)` geometry column (null Point for unresolved sites).
7. Set CRS to EPSG:4326. Return.

### `packages/uk-rimnet-core/src/uk_rimnet_core/__init__.py`

Add `DatasetBuilder` to public exports.

---

## Dependencies to Add

In `packages/uk-rimnet-core/pyproject.toml`:
```
geopandas >= 1.0.0
pyarrow >= 15.0.0   # GeoParquet engine used by geopandas
shapely >= 2.0.0    # geometry objects (transitive via geopandas but pin explicitly)
```

---

## Tests

### `tests/fixtures/`

Minimal fixture files — 5–8 rows each, one per format:
- `simple_stats_q1_2010.csv` — 2010-style, 0-row preamble, no `site_normal` column
- `preamble_stats_q1_2012.csv` — 6-row preamble, `Std Dev` column name
- `stats_q1_2014.xlsx` — Excel, 1-row title preamble, `Standard Deviation` column name
- `monthly_fixed_jan_2025.csv` — 2025-style with `monitor_location`
- `monthly_fixed_jan_2023.csv` — 2023-style without `monitor_location` (coords only)
- `monthly_fixed_jul_2022.csv` — 2022-style with Title Case column names

### `tests/test_dataset_builder.py`

Single test class `TestDatasetBuilder`, using an `autouse` fixture that:
- Copies fixture files into `tmp_path` in the expected subdirectory layout
- Instantiates `DatasetBuilder(tmp_path)`

Tests:
- `test_build_returns_geodataframe` — assert type, column names, CRS is EPSG:4326
- `test_all_formats_are_read` — assert rows from each fixture era are present
- `test_decommissioned_site_has_null_geometry` — use a fixture location absent from 2025 data
- `test_location_normalisation` — assert `*`-suffixed name from 2010 fixture resolves correctly
- `test_2023_location_resolved_by_coords` — assert coord-only 2023 row gets location name
- `test_2022_title_case_columns_normalised` — assert Jul 2022 fixed file reads correctly despite Title Case headers

---

## Verification

```bash
uv run poe all   # all checks + tests pass
```

Then smoke-test against the real data:
```python
from pathlib import Path
from uk_rimnet_core import DatasetBuilder

gdf = DatasetBuilder(Path("bin")).build()
assert len(gdf["location_name"].unique()) >= 90
assert gdf["geometry"].notna().sum() >= 81   # 81 sites with 2025+ equivalents
gdf.to_parquet("rimnet.parquet")
```

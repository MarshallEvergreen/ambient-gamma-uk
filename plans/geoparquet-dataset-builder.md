# Plan: GeoParquet Dataset Builder

## Context
Build a homogeneous quarterly-aggregate GeoParquet dataset from 15+ years of RIMNET/RREMS radiation monitoring data (2010–2026). Data spans seven distinct file formats and two monitoring eras. Newer data (2025+) has lat/lon + location names; 2023–2024 has lat/lon but no names; pre-2023 has names but no coordinates. The strategy is to build a canonical location registry from 2025+ fixed monthly CSVs, then join coordinates backward to all older data. Monthly streaming data (2023+) is aggregated to quarterly to match historical granularity.

The parsing/reading layer does not yet exist — only download and discovery are implemented.

---

## Target Schema (one row = one location × one quarter)

| Column | Type | Notes |
|---|---|---|
| `location_name` | `str` | Normalised (whitespace + `*` stripped) |
| `geometry` | `Point (WGS84)` | Nullable for 9 decommissioned sites |
| `year` | `int` | |
| `quarter` | `int` | 1–4 |
| `monitor_type` | `"fixed" \| "mobile"` | |
| `mean` | `float` | µGy/h |
| `min` | `float` | µGy/h |
| `max` | `float` | µGy/h |
| `std_dev` | `float` | µGy/h |
| `site_normal` | `float \| null` | Null for 2010–2011 (not in those files) |

---

## Source File Format Summary

| Era | Format | Reader needed | Location names? | Coords? | Preamble rows |
|---|---|---|---|---|---|
| 2010–2011 | Simple stats CSV | `read_simple_stats_csv` | Yes (with `*`) | No | 0 |
| 2012–2022 Q2 | Preamble stats CSV | `read_preamble_stats_csv` | Yes | No | 2–6 (varies) |
| 2013–2018 | Stats Excel (.xlsx) | `read_stats_excel` | Yes | No | 6 |
| 2022 Jul–Dec | Monthly RREMS CSV | `read_monthly_csv` | Yes | Yes | 0 |
| 2023–2024 | Monthly RREMS CSV | `read_monthly_csv` | **No** (coords only) | Yes | 0 |
| 2025–2026 | Monthly RREMS CSV | `read_monthly_csv` | Yes | Yes | 0 |

Fixed and mobile are separate files from ~2016 onwards. Earlier data is fixed-only.

---

## New Files

### `packages/uk-rimnet-core/src/uk_rimnet_core/_location_registry.py`

`LocationRegistry` — builds the canonical name→coords and coords→name lookup from all 2025+ **fixed** monthly CSVs (the only era with both names and coordinates reliably populated).

```python
class LocationRegistry:
    def build(self) -> None
    def lookup_by_name(self, name: str) -> tuple[float, float] | None
    def lookup_by_coords(self, lat: float, lon: float, tolerance: float = 0.001) -> str | None
```

- Strips whitespace from `monitor_location`
- Used to resolve names for 2023–2024 data (coord lookup) and coordinates for pre-2023 data (name lookup)
- 9 decommissioned sites will return `None` from `lookup_by_name` → geometry stored as null

### `packages/uk-rimnet-core/src/uk_rimnet_core/_readers.py`

Four private reader functions, each returning a standard intermediate `pl.DataFrame` with columns:
`location_name, year, quarter, monitor_type, mean, min, max, std_dev, site_normal`

**`read_simple_stats_csv(path, year, quarter, monitor_type)`**
- Reads 2010–2011 CSVs: no preamble, columns `Location / Units / Mean / Standard Deviation / Max / Min`
- `site_normal = null`
- Strips whitespace and `*` from location names

**`read_preamble_stats_csv(path, year, quarter, monitor_type)`**
- Reads 2012–2022 Q2 CSVs: auto-detects header row by scanning for the first row where the first cell is `"Location"` (case-insensitive). This handles the variable preamble depth across years.
- Column name mapping: `Std Dev / Standard Deviation → std_dev`, `Site Normal Level → site_normal`

**`read_stats_excel(path, year, quarter, monitor_type)`**
- Reads 2013–2018 xlsx using `pl.read_excel(path, read_options={"header_row": 6, "skip_rows": 1})`
- Same column mapping as preamble CSV
- Sheet name varies by file; always use first sheet

**`read_monthly_csv(path, year, month, monitor_type, registry)`**
- Reads 2022 Jul+, 2023–2024, 2025+ monthly streaming CSVs
- Detects whether `monitor_location` column is present:
  - Present (2022 Jul+, 2025+): use directly, strip whitespace
  - Absent (2023–2024): resolve via `registry.lookup_by_coords(lat, lon)`
- Aggregates per location per file (all readings in one month → mean/min/max/std_dev)
- Quarter = `ceil(month / 3)`
- Fixed CSVs have `site_normal` column; mobile do not → null for mobile

**Period/type inference helper: `_parse_file_metadata(path: Path) -> _FileMeta`**

Parses year, quarter (or month), and monitor_type from the filename. Handles patterns:
- `Q1 2010.csv`, `Quarter_1_2014_....xlsx` → quarter from digit
- `Jan-Mar_2018_....xlsx`, `jan-mar-2022-...csv` → quarter from month-range
- `jul_2022_...csv`, `Jan_2025_...csv` → month from name (reuses `_MONTH_NAME_TO_INT` from `client.py`)
- `*fixed*` / `*mobile*` in filename → monitor_type (default `"fixed"` for pre-split era)

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
1. Instantiate and build `LocationRegistry` from `source_dir`
2. Walk `source_dir` recursively for `.csv` and `.xlsx` files
3. For each file, call `_parse_file_metadata` then the appropriate reader
4. `pl.concat` all intermediate DataFrames
5. Join lat/lon from `LocationRegistry.lookup_by_name`
6. Convert to `gpd.GeoDataFrame` with `shapely.Point(lon, lat)` geometry column
7. Return

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
- `simple_stats_q1_2010.csv` — 2010-style, no preamble
- `preamble_stats_q1_2012.csv` — 6-row preamble
- `stats_q1_2014.xlsx` — Excel, header at row 6
- `monthly_fixed_jan_2025.csv` — 2025-style with location names
- `monthly_fixed_jan_2023.csv` — 2023-style without location names (coords only)

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

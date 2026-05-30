# Plan: uk-rimnet data wrangling + FastAPI

## Context

The UK government publishes hourly ambient gamma radiation dose rate readings from ~92 fixed and mobile monitors as monthly CSV files on GOV.UK. There is no official API. This plan covers:

1. `uk-rimnet-core` — discover, download, parse CSVs → write partitioned Parquet
2. `uk-rimnet-api` — FastAPI service exposing the stored data

Frontend is explicitly deferred.

---

## Known CSV schema (April 2026 fixed monitors sample)

```
reading_date,latitude,longitude,reading,units,monitor_location
30/04/2026 23:51,53.81132,-1.86678,0.1,µGy/h,Wilsden (Bingley)
```

- `reading_date` — `DD/MM/YYYY HH:MM`
- `latitude`, `longitude` — WGS84 float
- `reading` — dose rate (float)
- `units` — always `µGy/h` (verify; normalise if not)
- `monitor_location` — human-readable name
- CSVs have trailing empty columns and possible metadata rows — require defensive parsing

---

## Parquet storage schema

Plain Parquet (not GeoParquet). Lat/lon as floats — no geometry encoding needed.

| Column | Polars type | Notes |
|---|---|---|
| `reading_datetime` | `Datetime(us, UTC)` | Parsed from `reading_date`, assumed UK local time |
| `latitude` | `Float64` | |
| `longitude` | `Float64` | |
| `reading_ugy_h` | `Float64` | Normalised to µGy/h |
| `monitor_location` | `String` | |
| `monitor_type` | `Categorical` | `"fixed"` or `"mobile"` |

Partitioned by year + month:
```
{data_dir}/
  year=2026/month=04/readings.parquet
  year=2026/month=03/readings.parquet
  ...
```

`data_dir` is always caller-supplied — the library never assumes a default location.

---

## Package: `uk-rimnet-core`

### New dependencies
- `polars` — DataFrame operations and Parquet I/O
- `beautifulsoup4` — scraping GOV.UK publication index for file URLs

### Module structure

```
uk_rimnet_core/
  catalogue.py   # discovers available data releases from GOV.UK
  downloader.py  # streams CSV/ZIP files via httpx
  parser.py      # CSV bytes → typed Polars DataFrame
  store.py       # read/write partitioned Parquet
  models.py      # domain types
```

### Key types (`models.py`)

```python
@dataclass(frozen=True)
class DataRelease:
    year: int
    month: int
    monitor_type: Literal["fixed", "mobile"]
    url: str

@dataclass(frozen=True)
class IngestResult:
    release: DataRelease
    rows_written: int
    destination: Path
```

### `catalogue.py`

- `CatalogueClient` — Protocol with `list_releases() -> list[DataRelease]`
- `GovUkCatalogueClient` — httpx implementation scraping:
  `https://www.gov.uk/government/publications/ambient-gamma-radiation-dose-rates-across-the-uk`
- URL pattern for files: `assets.publishing.service.gov.uk/media/<id>/<filename>.csv`
- Filename encodes month/year and monitor type (fixed/mobile) — use regex to extract

### `downloader.py`

- Takes an injected `httpx.Client`
- Streams response to avoid loading 20–35 MB CSVs into memory at once
- Returns `bytes` (or async `AsyncIterator[bytes]` — decide sync vs async; lean sync for now, async later)

### `parser.py`

- Takes `bytes` + `MonitorType` → `pl.DataFrame`
- Strips trailing empty columns and metadata rows before parsing
- Parses `reading_date` with `strptime("%d/%m/%Y %H:%M")`
- Converts to UTC datetime (UK local time — handle BST/GMT offset via `zoneinfo`)
- Normalises units to `µGy/h`
- Validates schema — raises typed exception on unexpected shape

### `store.py`

- `write_release(df: pl.DataFrame, data_dir: Path, release: DataRelease) -> Path`
  - Writes `{data_dir}/year={Y}/month={M}/readings.parquet`
  - Overwrites if partition already exists (idempotent)
- `read_releases(data_dir: Path, *, year: int | None, month: int | None) -> pl.LazyFrame`
  - Uses `pl.scan_parquet` with glob + optional partition filter
  - Returns LazyFrame — callers `.collect()` when needed

### Public surface of `uk-rimnet-core`

Exposed from `__init__.py`:
- `GovUkCatalogueClient`
- `CatalogueClient` (Protocol)
- `DataRelease`, `IngestResult`
- `store.write_release`, `store.read_releases`
- `parser.parse_csv`

---

## Package: `uk-rimnet-api`

New package at `packages/uk-rimnet-api`. Depends on `uk-rimnet-core`.

### New dependencies
- `fastapi`
- `uvicorn[standard]`

### Module structure

```
uk_rimnet_api/
  main.py          # FastAPI app factory, mounts routers
  config.py        # settings (data_dir path, read from env)
  routers/
    monitors.py    # /monitors endpoints
    readings.py    # /readings endpoints
```

### Endpoints (initial scope)

**`GET /monitors`**
Returns all distinct monitor locations with their most recent reading.
```json
[
  {
    "monitor_location": "Wilsden (Bingley)",
    "latitude": 53.81132,
    "longitude": -1.86678,
    "latest_reading_ugy_h": 0.1,
    "latest_reading_datetime": "2026-04-30T23:51:00Z",
    "monitor_type": "fixed"
  }
]
```

**`GET /readings`**
Query readings with optional filters. All parameters optional.
```
?monitor_location=Wilsden%20(Bingley)
&from=2026-01-01T00:00:00Z
&to=2026-04-30T23:59:59Z
```
Returns array of reading objects. Polars LazyFrame filtered before `.collect()` — no full dataset load.

### Config

`data_dir` read from `RIMNET_DATA_DIR` env var. No default — raises on startup if unset.

---

## Testing approach

Consistent with CLAUDE.md:
- Test public API of each module only
- No patching — inject `httpx.Client` / filesystem paths
- `pytest tmp_path` fixture for store tests (real filesystem, temp dir)
- Fake `CatalogueClient` implementation (not a mock) for higher-level tests
- `httpx.MockTransport` for HTTP boundary tests — not `unittest.mock.patch`

New dev dependencies: `pytest`, `pytest-httpx`

---

## Implementation order

- [ ] 1. Add `polars`, `beautifulsoup4` to `uk-rimnet-core`; `pytest`, `pytest-httpx` to dev deps
- [ ] 2. `models.py` — domain types
- [ ] 3. `parser.py` + tests (pure function, easy to test with sample CSV bytes)
- [ ] 4. `store.py` + tests (tmp_path, real Parquet round-trip)
- [ ] 5. `catalogue.py` + tests (httpx.MockTransport with saved GOV.UK HTML fixture)
- [ ] 6. `downloader.py` + tests
- [ ] 7. Scaffold `uk-rimnet-api` package, add to workspace
- [ ] 8. `config.py`, `main.py`, routers
- [ ] 9. API integration tests (TestClient + real Parquet fixture in tmp_path)

---

## Verification

- `uv run poe test` passes across all packages
- `uv run poe ci:lint` and `uv run poe ci:fmt` clean
- Manual: `uv run uvicorn uk_rimnet_api.main:app --reload`, `curl /monitors` returns real data
- Manual: ingest one month of data end-to-end, inspect Parquet with `polars.read_parquet`

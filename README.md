# uk-rimnet

A Python library for accessing and processing UK ambient gamma radiation monitoring data.

## Background

The UK government publishes gamma radiation dose rate measurements from a network of fixed and mobile monitors distributed across the country. This data was historically collected by **RIMNET** (Radioactive Incident Monitoring Network), a system operated by the Met Office from 1989 until 2022. RIMNET was subsequently replaced by **RREMS** (Radiological Response and Emergency Management System), managed by the Department for Energy Security and Net Zero.

Data is published on GOV.UK under the [Ambient gamma radiation dose rates across the UK](https://www.gov.uk/government/publications/ambient-gamma-radiation-dose-rates-across-the-uk) publication. Historical records are available from 2010 onwards. All data is released under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

## The Problem

There is no official API. Each release is a large CSV or XLSX file (20–35 MB) hosted at an unpredictable URL, discoverable only by scraping the GOV.UK publication index. Beyond the access problem, the dataset as published is not analytically usable in a uniform way: the file format, schema, and available fields have changed substantially across the 15-year archive, and no geospatial coordinates were included in any release before 2022.

## Data Engineering

Producing a single, consistent, geospatially-enabled dataset from this archive required resolving a series of structural changes that accumulated over the transition from RIMNET to RREMS. These are documented below in approximate chronological order.

### Era 1 — 2010 to 2015: Fixed monitors only, quarterly aggregates

The earliest releases cover only the fixed monitor network. Data is distributed as quarterly summary statistics (mean, min, max, standard deviation) in CSV files bundled into annual ZIP archives. No mobile monitor data exists for this period; mobile monitoring was introduced in 2016.

The 2010 and 2011 fixed files lack a `site_normal` column entirely — the concept of a per-station long-run background level was added to the schema in later releases. These rows receive a null `site_normal` in the unified dataset.

No geospatial coordinates are present in any file from this era. Stations are identified by name only.

### Era 2 — 2016 to 2021: Fixed and mobile, quarterly aggregates

From 2016 the mobile monitoring network was brought online and published alongside fixed data. The quarterly summary format is retained. The `site_normal` column is consistently present for fixed monitors across this period; mobile files do not carry a site normal.

Still no coordinates. Station names remain the only spatial identifier.

### Era 3 — 2022: The transition year

2022 is structurally unique. In the first half of the year (Q1–Q2), RIMNET continued publishing quarterly summary files in the established format. At some point mid-year, the transition to RREMS brought a change in publication approach: Q3 and Q4 data was instead released as monthly streaming files containing one row per 10-minute reading per station.

The 2022 H2 fixed streaming files introduced a further wrinkle: column names were published in Title Case (`Reading Date & Time`, `Site Latitude`, `Site Longitude`) rather than the snake_case used by all other streaming files. These are normalised during ingest.

This year is handled as a discrete transition type in the data model, with explicit validation that quarterly data covers only H1 and monthly data covers only H2.

Coordinates appear in the monthly streaming files for the first time — but without station names. The 2022 streaming files carry only latitude and longitude.

### Era 4 — 2023 to 2024: Monthly streaming, coordinates only

From 2023 all data is published as monthly streaming files. The quarterly summary format is retired. Each file contains readings at approximately 10-minute intervals for each active monitoring station.

Coordinates are present but station names are absent. A station can be identified by its location, but there is no human-readable label attached.

### Era 5 — 2025 onwards: Monthly streaming with station names

In 2025, RREMS added a `monitor_location` column to the monthly files, providing both coordinates and a named identifier for each station in every row. This is the first era where a complete, self-contained spatial dataset can be constructed directly from the raw files.

---

### Column name normalisation

Across the archive, the same statistical fields appear under a range of different names depending on the year and file type. The ingest layer maps these to a canonical schema:

| Canonical field | Variants seen in source files |
|---|---|
| `std_dev` | `Standard Deviation`, `Std Deviation`, `Std Dev` |
| `mean` | `Mean`, `Avg`, `Average` |
| `site_normal` | `Site Normal Level`, `Site Normal` |
| `location_name` | `Location`, `Monitor_Location` |

Header rows are located by scanning for the first row whose leading cell contains the word `location` (case-insensitive), rather than by fixed offset. This makes the reader robust to the varying depths of metadata preamble found across years — some files have two lines of boilerplate before the header, others have five.

Trailing footnote rows (e.g. `*indicates a change to Site No.`) mixed into the data are filtered by requiring both `location_name` and `mean` to be non-null and non-empty.

Filename patterns for quarters were inconsistent across the archive and required explicit pattern matching: `Q1`, `Quarter-1`, `Quarter_1`, and `jan-mar` are all observed for the same calendar period across different years.

---

### The Location Registry

To produce a geospatially-enabled dataset spanning the full archive, a **location registry** is constructed from all 2025-onwards files and applied retrospectively.

The registry is built by reading the `latitude`, `longitude`, and `monitor_location` columns from every 2025+ monthly file, then grouping by station name and averaging coordinates across all observations. This averaging accounts for minor GPS drift between readings at the same physical station.

For years 2022–2024, where coordinates are present but station names are absent, the registry is applied by a **nearest-neighbour join** using the [Haversine formula](https://en.wikipedia.org/wiki/Haversine_formula) to compute great-circle distances between each unlabelled coordinate pair and every entry in the registry. Each observation is assigned the name of the closest registry entry, subject to a maximum match distance of **5 km** — observations with no registry entry within that threshold are excluded. This distance is conservative relative to the typical monitoring station spacing across the UK, and eliminates spurious matches to distant stations.

For the 2010–2021 quarterly files, where only station names are available, the join runs in the opposite direction: the registry is joined on `location_name` to attach coordinates to the named stations. Where a station name in the historical record has no entry in the registry (for example, stations that have since been decommissioned), the observation retains a null coordinate and is excluded from geospatial analysis.

The result is a unified dataset covering 2010 to the present, with consistent quarterly statistics and geospatial coordinates for every station that was still active in 2025.

## Project Structure

This is a [UV workspace](https://docs.astral.sh/uv/concepts/workspaces/) containing the following packages:

| Package | Import name | Description |
|---|---|---|
| `packages/uk-rimnet-core` | `uk_rimnet_core` | Core library: data discovery, download, processing, and location registry |

## Usage

```python
from uk_rimnet_core import build_dataset

df = await build_dataset(destination="./data")
```

`build_dataset` handles discovery, download, location registry construction, and processing in a single call. Raw files are cached at `destination` and skipped on subsequent runs, so repeated calls only fetch new releases. Provided DESNZ does not introduce another structural change to the publication format, this means the library is designed to be run continuously as new monthly data becomes available — each run will automatically discover and download any new files and the returned DataFrame will include the newly published quarters appended to the existing archive.

The resulting DataFrame carries one row per monitoring station per quarter with columns `location_name`, `latitude`, `longitude`, `monitor_type`, `year`, `quarter`, `mean`, `min`, `max`, `std_dev`, `site_normal`, and `unit` (µGy/h).

Both `build_dataset` and the underlying `Client` accept an `fs` parameter that takes any [fsspec](https://filesystem-spec.readthedocs.io/en/latest/)-compatible filesystem. This means the raw files can be written to — and read back from — any supported storage backend without changes to application code:

```python
import s3fs
from uk_rimnet_core import build_dataset

df = await build_dataset(
    destination="s3://my-bucket/uk-rimnet/",
    fs=s3fs.S3FileSystem(),
)
```

Any backend with an fsspec implementation works in the same way, including GCS, Azure Blob Storage, and in-memory filesystems for testing.

For lower-level access — for example to substitute a pre-built registry or process a subset of years — the individual components are also part of the public API:

```python
from uk_rimnet_core import Client, LocationRegistry

client = Client()
releases = await client.async_.download_releases(destination="./data")

registry = LocationRegistry()
registry.build_from_releases(releases)
```

## Citation

If you use this library or the processed dataset in your work, please cite:

```bibtex
@software{marshall2026ukrimnet,
  author    = {Marshall, Abie},
  title     = {{uk-rimnet}: A Python library for accessing and processing
               UK ambient gamma radiation monitoring data},
  year      = {2026},
  url       = {https://github.com/MarshallEvergreen/uk-rimnet},
  note      = {Data sourced from the UK Government under the Open Government
               Licence v3.0. \url{https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/}}
}
```

The underlying data should be attributed to the Department for Energy Security and Net Zero, published via GOV.UK at [Ambient gamma radiation dose rates across the UK](https://www.gov.uk/government/publications/ambient-gamma-radiation-dose-rates-across-the-uk).

## License

Source code: [MIT License](LICENSE).

Data sourced from GOV.UK is available under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

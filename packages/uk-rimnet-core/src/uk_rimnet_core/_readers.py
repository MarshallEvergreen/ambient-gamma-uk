"""Stats and monthly CSV readers for RIMNET/RREMS data releases."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path

    from uk_rimnet_core.models import MonitorType

_COLUMN_ALIASES: dict[str, str] = {
    "location": "location_name",
    "monitor_location": "location_name",
    "site normal level": "site_normal",
    "standard deviation": "std_dev",
    "std deviation": "std_dev",
    "std dev": "std_dev",
    "mean": "mean",
    "avg": "mean",
    "average": "mean",
    "min": "min",
    "max": "max",
}

_MONTHLY_COLUMN_ALIASES: dict[str, str] = {
    # Title Case variants (2022 H2 fixed files only)
    "reading date & time": "reading_date",
    "site latitude": "latitude",
    "site longitude": "longitude",
    "reading": "reading",
    "site normal": "site_normal",
    # Snake case (all other monthly files)
    "reading_date": "reading_date",
    "latitude": "latitude",
    "longitude": "longitude",
    "site_normal": "site_normal",
    "monitor_location": "location_name",
}

_MONTHLY_REQUIRED = frozenset(
    ["latitude", "longitude", "reading", "site_normal", "monitor_location"],
)

_QUARTERLY_CANONICAL_ROWS = frozenset(
    ["location_name", "site_normal", "std_dev", "mean", "min", "max"],
)


class StatsFileReadError(Exception):
    """Raised when a stats file cannot be parsed or is not in a recognised format."""


def read_quarterly_stats_file(
    path: Path,
    year: int,
    quarter: int,
    monitor_type: MonitorType,
) -> pl.DataFrame:
    """Read a quarterly stats CSV or XLSX file into a normalised DataFrame.

    Handles all RIMNET/RREMS quarterly stats file formats from 2010 onwards.
    The header row is located by scanning for the first row whose first cell
    contains 'location' (case-insensitive), making the function robust to any
    depth of metadata preamble. Column names are then normalised to a canonical
    set and blank separator rows are dropped.

    Args:
        path: Path to the CSV or XLSX stats file.
        year: Calendar year of the data in the file.
        quarter: Quarter of the data (1-4).
        monitor_type: Whether the file covers fixed or mobile monitors.

    Returns:
        A DataFrame with columns: location_name, year, quarter, monitor_type,
        mean, min, max, std_dev, site_normal. ``site_normal`` is null for
        mobile files and for the 2010-2011 fixed files that pre-date that
        column.

    Raises:
        StatsFileReadError: If no header row can be found in the file.

    """
    raw = _load_raw(path)
    header_idx = _find_header_row(raw, path)

    # Get the headers as they are in the excel sheet / csv file
    native_headers = [
        str(v).strip() if v is not None else "" for v in raw.row(header_idx)
    ]

    # Splice the dataframe to only include rows after the header row
    data = raw.slice(header_idx + 1)

    unnormalized_header_mappings = {
        col: native_headers[i] for i, col in enumerate(data.columns)
    }

    normalized_header_mappings = {
        k: normalized
        for k, v in unnormalized_header_mappings.items()
        if (normalized := _COLUMN_ALIASES.get(v.strip().lower())) is not None
    }

    data = data.rename(
        normalized_header_mappings,
    )

    data = data.select([c for c in data.columns if c in _QUARTERLY_CANONICAL_ROWS])

    # Mostly targetted to remove rows like:
    # *indicates a change to Site No… ┆ null        ┆ null     ┆ null    ┆ null ┆ null │
    data = data.filter(
        pl.col("location_name").is_not_null()
        & (pl.col("location_name").str.strip_chars() != "")
        & pl.col("mean").is_not_null()
        & (pl.col("mean").str.strip_chars() != ""),
    )
    data = data.with_columns(
        pl.col("location_name")
        .str.strip_chars()
        .str.replace_all(r"\*", "")
        .str.strip_chars(),
    )

    # Add site normal if its missing
    for col in ("site_normal", "latitude", "longitude"):
        if col not in data.columns:
            data = data.with_columns(pl.lit(None).cast(pl.Float64).alias(col))

    # Cast statistical rows to be floats
    for col in _QUARTERLY_CANONICAL_ROWS - {"location_name"}:
        if col in data.columns:
            data = data.with_columns(pl.col(col).cast(pl.Float64))

    # Add additional metadata columns
    return data.with_columns(
        pl.lit(year).alias("year"),
        pl.lit(quarter).alias("quarter"),
        pl.lit(monitor_type).alias("monitor_type"),
    )


def _load_raw(path: Path) -> pl.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pl.read_excel(path, has_header=False)
    return pl.read_csv(
        path,
        has_header=False,
        encoding="utf8-lossy",
        infer_schema_length=0,
    )


def _find_header_row(raw: pl.DataFrame, path: Path) -> int:
    for i, row in enumerate(raw.iter_rows()):
        if "location" in str(row[0] or "").strip().lower():
            return i
    msg = (
        f"No header row found in {path}: "
        "expected a row whose first cell contains 'location'."
    )
    raise StatsFileReadError(msg)


def read_monthly_csv(
    path: Path,
    year: int,
    month: int,
    monitor_type: MonitorType,
) -> pl.DataFrame:
    """Read a monthly streaming CSV file and aggregate it to quarterly stats.

    Handles all RIMNET/RREMS monthly streaming formats from 2022 H2 onwards,
    including the Title Case column names used in the 2022 H2 fixed files and
    the junk trailing metadata columns present in every file. Readings are
    grouped by monitoring station and aggregated to mean, min, max, and
    standard deviation.

    Location names are taken directly from the ``monitor_location`` column
    where present (2025 onwards). For earlier files that carry only coordinates
    the ``location_name`` column is null; callers that need names for those
    rows should resolve them separately via a location registry.

    Args:
        path: Path to the monthly CSV file.
        year: Calendar year of the data in the file.
        month: Calendar month of the data (1-12).
        monitor_type: Whether the file covers fixed or mobile monitors.

    Returns:
        A DataFrame with columns: location_name, year, quarter, monitor_type,
        mean, min, max, std_dev, site_normal. ``site_normal`` is null for
        mobile files. ``location_name`` is null for files that pre-date the
        addition of the monitor_location column (before 2025).

    """
    data = pl.read_csv(path, encoding="utf8-lossy")
    normalised_names = {
        raw: canonical
        for raw in data.columns
        if (canonical := _MONTHLY_COLUMN_ALIASES.get(raw.strip().lower())) is not None
        and canonical in _MONTHLY_REQUIRED
    }
    data = data.rename(normalised_names).select(list(normalised_names))
    for col in {"latitude", "longitude", "reading", "site_normal"} & set(data.columns):
        data = data.with_columns(pl.col(col).cast(pl.Float64))

    if "location_name" in data.columns:
        data = data.with_columns(
            pl.col("location_name")
            .str.strip_chars()
            .str.replace_all(r"\*", "")
            .str.strip_chars(),
        )
    else:
        data = data.with_columns(pl.lit(None).cast(pl.String).alias("location_name"))

    group_cols: list[str] = ["latitude", "longitude", "location_name"]

    agg = [
        pl.mean("reading").alias("mean"),
        pl.min("reading").alias("min"),
        pl.max("reading").alias("max"),
        pl.std("reading").alias("std_dev"),
    ]
    if "site_normal" in data.columns:
        agg.append(pl.mean("site_normal").alias("site_normal"))
    else:
        data = data.with_columns(pl.lit(None).cast(pl.Float64).alias("site_normal"))

    data = data.group_by(group_cols).agg(agg)

    return data.with_columns(
        pl.lit(year).alias("year"),
        pl.lit(month).alias("month"),
        pl.lit(monitor_type).alias("monitor_type"),
    )

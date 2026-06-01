"""Stats and monthly CSV readers for RIMNET/RREMS data releases."""

from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from fsspec.implementations.local import LocalFileSystem

from uk_rimnet_core._columns import (
    MONTHLY_ALIASES,
    MONTHLY_REQUIRED,
    QUARTERLY_CANONICAL,
    QUARTERLY_STAT_ALIASES,
)

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem

    from uk_rimnet_core.models import MonitorType


class StatsFileReadError(Exception):
    """Raised when a stats file cannot be parsed or is not in a recognised format."""


def read_quarterly_stats_file(
    path: str | Path,
    year: int,
    quarter: int,
    monitor_type: MonitorType,
    fs: AbstractFileSystem | None = None,
) -> pl.DataFrame:
    """Read a quarterly stats CSV or XLSX file into a normalised DataFrame.

    Handles all RIMNET/RREMS quarterly stats file formats from 2010 onwards.
    The header row is located by scanning for the first row whose first cell
    contains 'location' (case-insensitive), making the function robust to any
    depth of metadata preamble. Column names are then normalised to a canonical
    set and blank separator rows are dropped.

    Args:
        path: Path to the CSV or XLSX stats file. May be a local path or any
            path supported by ``fs``.
        year: Calendar year of the data in the file.
        quarter: Quarter of the data (1-4).
        monitor_type: Whether the file covers fixed or mobile monitors.
        fs: Filesystem to read from. Defaults to the local filesystem.

    Returns:
        A DataFrame with columns: location_name, year, quarter, monitor_type,
        mean, min, max, std_dev, site_normal. ``site_normal`` is null for
        mobile files and for the 2010-2011 fixed files that pre-date that
        column.

    Raises:
        StatsFileReadError: If no header row can be found in the file.

    """
    resolved_fs = fs or LocalFileSystem()
    raw = _load_raw(path, resolved_fs)
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
        if (normalized := QUARTERLY_STAT_ALIASES.get(v.strip().lower())) is not None
    }

    data = data.rename(
        normalized_header_mappings,
    )

    data = data.select([c for c in data.columns if c in QUARTERLY_CANONICAL])

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
    for col in QUARTERLY_CANONICAL - {"location_name"}:
        if col in data.columns:
            data = data.with_columns(pl.col(col).cast(pl.Float64))

    # Add additional metadata columns
    return data.with_columns(
        pl.lit(year).alias("year"),
        pl.lit(quarter).alias("quarter"),
        pl.lit(monitor_type).alias("monitor_type"),
    )


def _load_raw(path: str | Path, fs: AbstractFileSystem) -> pl.DataFrame:
    with fs.open(path, "rb") as f:
        if Path(path).suffix.lower() == ".xlsx":
            return pl.read_excel(f, has_header=False)
        return pl.read_csv(
            f,
            has_header=False,
            encoding="utf8-lossy",
            infer_schema_length=0,
        )


def _find_header_row(raw: pl.DataFrame, path: str | Path) -> int:
    for i, row in enumerate(raw.iter_rows()):
        if "location" in str(row[0] or "").strip().lower():
            return i
    msg = (
        f"No header row found in {path}: "
        "expected a row whose first cell contains 'location'."
    )
    raise StatsFileReadError(msg)


def read_monthly_csv(
    path: str | Path,
    year: int,
    month: int,
    monitor_type: MonitorType,
    fs: AbstractFileSystem | None = None,
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
        path: Path to the monthly CSV file. May be a local path or any path
            supported by ``fs``.
        year: Calendar year of the data in the file.
        month: Calendar month of the data (1-12).
        monitor_type: Whether the file covers fixed or mobile monitors.
        fs: Filesystem to read from. Defaults to the local filesystem.

    Returns:
        A DataFrame with columns: location_name, year, quarter, monitor_type,
        mean, min, max, std_dev, site_normal. ``site_normal`` is null for
        mobile files. ``location_name`` is null for files that pre-date the
        addition of the monitor_location column (before 2025).

    """
    resolved_fs = fs or LocalFileSystem()
    with resolved_fs.open(path, "rb") as f:
        data = pl.read_csv(f, encoding="utf8-lossy")
    normalised_names = {
        raw: canonical
        for raw in data.columns
        if (canonical := MONTHLY_ALIASES.get(raw.strip().lower())) is not None
        and canonical in MONTHLY_REQUIRED
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

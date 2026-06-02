"""Processing logic for RIMNET data releases."""

from typing import TYPE_CHECKING

import polars as pl

from uk_rimnet_core._geospatial import haversine
from uk_rimnet_core._readers import read_monthly_csv, read_quarterly_stats_file
from uk_rimnet_core.models import (
    AnnualYearData,
    MonitorType,
    MonthlyData,
    PreMobileYearData,
    QuarterlyData,
    QuarterlyYearData,
    TransitionYearData,
)

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem

    from uk_rimnet_core import LocationRegistry


def _concat_monthly_quarters_together(
    year: int,
    quarterly_data: QuarterlyData,
    location_registry: LocationRegistry,
    monitoring_type: MonitorType,
    fs: AbstractFileSystem | None,
) -> pl.DataFrame:
    return (
        pl.concat(
            [
                read_quarterly_stats_file(pq[0], year, pq[1], monitoring_type, fs)
                for pq in quarterly_data.present_quarters
            ],
            how="diagonal",
        )
        .drop("latitude", "longitude")
        .join(
            location_registry.data,
            on="location_name",
            how="left",
        )
    )


_MONTHLY_STAT_COLS: frozenset[str] = frozenset(
    ["latitude", "longitude", "mean", "min", "max", "std_dev", "site_normal"],
)


def _assign_locations_from_registry(
    data: pl.DataFrame,
    registry: LocationRegistry,
) -> pl.DataFrame:
    reg = registry.data.rename(
        {"location_name": "_reg_name", "latitude": "_reg_lat", "longitude": "_reg_lon"},
    )
    cross = (
        data.with_row_index("_row_idx")
        .join(reg, how="cross")
        .with_columns(
            haversine(
                pl.col("latitude"),
                pl.col("longitude"),
                pl.col("_reg_lat"),
                pl.col("_reg_lon"),
            ).alias("_dist"),
        )
    )
    agg_cols = [c for c in cross.columns if c != "_row_idx"]
    return (
        cross.sort("_dist")
        .group_by("_row_idx")
        .agg([pl.first(c) for c in agg_cols])
        .drop("_row_idx", "_reg_lat", "_reg_lon", "_dist", "location_name")
        .rename({"_reg_name": "location_name"})
    )


def _process_months_into_quarters(
    year: int,
    release: MonthlyData,
    registry: LocationRegistry,
    monitoring_type: MonitorType,
    fs: AbstractFileSystem | None,
) -> pl.DataFrame:
    potentially_null_quarters: list[list[str] | None] = [
        release.q1_monthly_file_names,
        release.q2_monthly_file_names,
        release.q3_monthly_file_names,
        release.q4_monthly_file_names,
    ]

    quarter_frames: list[pl.DataFrame] = []
    for quarter_idx, files in enumerate(potentially_null_quarters):
        if files is None:
            continue
        quarter = quarter_idx + 1
        start_month = quarter_idx * 3 + 1
        monthly = pl.concat(
            [
                read_monthly_csv(f, year, start_month + i, monitoring_type, fs)
                for i, f in enumerate(files)
            ],
            how="diagonal",
        )
        stat_cols = [c for c in monthly.columns if c in _MONTHLY_STAT_COLS]
        if monthly["location_name"].is_null().all():
            monthly = _assign_locations_from_registry(monthly, registry)
        quarter_frames.append(
            monthly.group_by("location_name")
            .agg([pl.mean(c) for c in stat_cols])
            .with_columns(
                pl.lit(year).alias("year"),
                pl.lit(quarter).alias("quarter"),
                pl.lit(monitoring_type).alias("monitor_type"),
                pl.lit("µGy/h").alias("unit"),
            )
            .drop("latitude", "longitude")
            .join(registry.data, on="location_name", how="left"),
        )

    return pl.concat(quarter_frames, how="diagonal")


def _process_pre_mobile(
    release: PreMobileYearData,
    registry: LocationRegistry,
    fs: AbstractFileSystem | None,
) -> pl.DataFrame:

    return _concat_monthly_quarters_together(
        release.year,
        release.fixed,
        registry,
        "fixed",
        fs,
    )


def _process_quarterly(
    release: QuarterlyYearData,
    registry: LocationRegistry,
    fs: AbstractFileSystem | None = None,
) -> pl.DataFrame:
    fixed = _concat_monthly_quarters_together(
        release.year,
        release.fixed,
        registry,
        "fixed",
        fs,
    )
    mobile = _concat_monthly_quarters_together(
        release.year,
        release.mobile,
        registry,
        "mobile",
        fs,
    )
    return pl.concat([fixed, mobile], how="diagonal")


def _process_transition(
    release: TransitionYearData,
    registry: LocationRegistry,
    fs: AbstractFileSystem | None = None,
) -> pl.DataFrame:
    fixed_h1_quarterly = _concat_monthly_quarters_together(
        release.year,
        release.quarterly_fixed,
        registry,
        "fixed",
        fs,
    )
    mobile_h1_quarterly = _concat_monthly_quarters_together(
        release.year,
        release.quarterly_mobile,
        registry,
        "mobile",
        fs,
    )
    fixed_h2_monthly = _process_months_into_quarters(
        release.year,
        release.monthly_fixed,
        registry,
        "fixed",
        fs,
    )
    mobile_h2_monthly = _process_months_into_quarters(
        release.year,
        release.monthly_mobile,
        registry,
        "mobile",
        fs,
    )
    return pl.concat(
        [fixed_h1_quarterly, mobile_h1_quarterly, fixed_h2_monthly, mobile_h2_monthly],
        how="diagonal",
    )


def process_single_release(
    release: AnnualYearData,
    registry: LocationRegistry,
    fs: AbstractFileSystem | None = None,
) -> pl.DataFrame:
    match release:
        # case MonthlyYearData():  # noqa: ERA001
        #     return _process_monthly(release)  # noqa: ERA001
        case QuarterlyYearData():
            return _process_quarterly(release, registry, fs)
        case TransitionYearData():
            return _process_transition(release, registry, fs)
        case PreMobileYearData():
            return _process_pre_mobile(release, registry, fs)

    msg = f"Processing not implemented for release type {type(release)}"
    raise NotImplementedError(msg)

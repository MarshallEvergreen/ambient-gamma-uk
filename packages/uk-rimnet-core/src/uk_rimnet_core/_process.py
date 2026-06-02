"""Processing logic for RIMNET data releases."""

from typing import TYPE_CHECKING

import polars as pl

from uk_rimnet_core._readers import read_quarterly_stats_file
from uk_rimnet_core.models import (
    AnnualYearData,
    MonitorType,
    PreMobileYearData,
    QuarterlyData,
    QuarterlyYearData,
)

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem

    from uk_rimnet_core import LocationRegistry


def _concat_quarters_together(
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


def _process_pre_mobile(
    release: PreMobileYearData,
    registry: LocationRegistry,
    fs: AbstractFileSystem | None,
) -> pl.DataFrame:

    return _concat_quarters_together(
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
    fixed = _concat_quarters_together(
        release.year,
        release.fixed,
        registry,
        "fixed",
        fs,
    )
    mobile = _concat_quarters_together(
        release.year,
        release.mobile,
        registry,
        "mobile",
        fs,
    )
    return pl.concat([fixed, mobile], how="diagonal")


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
        # case TransitionYearData():  # noqa: ERA001
        #     return _process_transition(release)  # noqa: ERA001
        case PreMobileYearData():
            return _process_pre_mobile(release, registry, fs)

    msg = f"Processing not implemented for release type {type(release)}"
    raise NotImplementedError(msg)

"""Processing logic for RIMNET data releases."""

from typing import TYPE_CHECKING

import polars as pl

from uk_rimnet_core._readers import read_quarterly_stats_file
from uk_rimnet_core.models import (
    AnnualYearData,
    PreMobileYearData,
)

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem

    from uk_rimnet_core import LocationRegistry


def _process_pre_mobile(
    release: PreMobileYearData,
    registry: LocationRegistry,
    fs: AbstractFileSystem | None = None,
) -> pl.DataFrame:
    fixed_data = release.fixed

    return (
        pl.concat(
            [
                read_quarterly_stats_file(pq[0], release.year, pq[1], "fixed", fs)
                for pq in fixed_data.present_quarters
            ],
            how="diagonal",
        )
        .drop("latitude", "longitude")
        .join(
            registry.data,
            on="location_name",
            how="left",
        )
    )


def process_single_release(
    release: AnnualYearData,
    registry: LocationRegistry,
    fs: AbstractFileSystem | None = None,
) -> pl.DataFrame:
    match release:
        # case MonthlyYearData():  # noqa: ERA001
        #     return _process_monthly(release)  # noqa: ERA001
        # case QuarterlyYearData():  # noqa: ERA001
        #     return _process_quarterly(release)  # noqa: ERA001
        # case TransitionYearData():  # noqa: ERA001
        #     return _process_transition(release)  # noqa: ERA001
        case PreMobileYearData():
            return _process_pre_mobile(release, registry, fs)

    msg = f"Processing not implemented for release type {type(release)}"
    raise NotImplementedError(msg)

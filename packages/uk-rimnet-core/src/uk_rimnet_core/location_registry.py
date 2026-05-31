"""Location Registry for RIMNET data releases."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uk_rimnet_core.models import MonthlyYearData

import polars as pl


class LocationRegistryError(Exception):  # noqa: D101
    pass


class LocationRegistry:
    """Builds the location registry from releases post 2025.

    2025 is the year when the RRMES data releases started to include geospatial
    coordinates along with the name of the monitoring station. Therefore, the location
    registry can be built from the releases starting from 2025 and used to retrospectively
    assign coordinates to stations in earlier releases, where only station names are provided.
    """  # noqa: E501

    def __init__(self) -> None:  # noqa: D107
        self._registry = {}

    def build_from_releases(
        self,
        release_2025: MonthlyYearData,
        subsequent_releases: list[MonthlyYearData],
    ) -> pl.DataFrame:
        """Build a location registry from 2025 and subsequent monthly releases.

        Files are processed in chronological order — January 2025 first, then
        February 2025, and so on through any subsequent years. When the same
        monitoring location appears in more than one file the most recent
        coordinates take precedence, so the registry always reflects the latest
        known position for each station.

        Args:
            release_2025: The 2025 annual release. Must have year == 2025.
            subsequent_releases: Any releases for years after 2025, in
                chronological order.

        Returns:
            A DataFrame with one row per unique monitoring location, containing
            columns ``latitude``, ``longitude``, and ``monitor_location``.

        Raises:
            LocationRegistryError: If ``release_2025`` does not have year 2025.

        """
        if release_2025.year != 2025:  # noqa: PLR2004
            msg = "release_2025 must have year 2025."
            raise LocationRegistryError(msg)

        files_2025 = (
            release_2025.fixed.ordered_monthly_file_names
            + release_2025.mobile.ordered_monthly_file_names
        )

        all_files = files_2025 + [
            f
            for r in subsequent_releases
            for f in r.fixed.ordered_monthly_file_names
            + r.mobile.ordered_monthly_file_names
        ]

        df = None
        for f in all_files:
            _df = pl.read_csv(
                f,
                encoding="utf8-lossy",
                columns=["latitude", "longitude", "monitor_location"],
            ).unique(subset=["monitor_location"], keep="last")
            if df is None:
                df = _df
            else:
                df = df.update(_df, on="monitor_location", how="full")

        if df is None:
            msg = "No files found in releases to build registry from."
            raise LocationRegistryError(msg)

        return df

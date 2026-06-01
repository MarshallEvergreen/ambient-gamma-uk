"""Location Registry for RIMNET data releases."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

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
        self._registry: pl.DataFrame | None = None

    def build_from_releases(
        self,
        release_2025: MonthlyYearData,
        subsequent_releases: list[MonthlyYearData],
    ) -> pl.DataFrame:
        """Build a location registry from 2025 and subsequent monthly releases.

        All files are read and concatenated, then grouped by monitoring station.
        Where the same station appears across multiple files (e.g. due to minor
        GPS drift) its coordinates are averaged across all observations.

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

        frames = [
            pl.read_csv(
                f,
                encoding="utf8-lossy",
                columns=["latitude", "longitude", "monitor_location"],
            )
            for f in all_files
        ]

        if not frames:
            msg = "No files found in releases to build registry from."
            raise LocationRegistryError(msg)

        self._registry = (
            pl.concat(frames)
            .group_by("monitor_location")
            .agg(
                pl.col("latitude").mean(),
                pl.col("longitude").mean(),
            )
        )
        return self._registry

    def save(self, path: Path) -> None:
        """Write the registry to a CSV file.

        Args:
            path: Destination path for the CSV file.

        Raises:
            LocationRegistryError: If the registry has not been built yet.

        """
        if self._registry is None:
            msg = "Registry has not been built. Call build_from_releases first."
            raise LocationRegistryError(msg)
        self._registry.write_csv(path)

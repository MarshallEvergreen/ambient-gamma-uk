"""Location Registry for RIMNET data releases."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from uk_rimnet_core.models import AnnualYearData

import polars as pl

from uk_rimnet_core._columns import MONTHLY_ALIASES
from uk_rimnet_core.models import MonthlyYearData


class LocationRegistryError(Exception):  # noqa: D101
    pass


_REGISTRY_YEAR = 2025


class LocationRegistry:
    """Builds the location registry from all downloaded releases from 2025 onwards.

    2025 is the year when RREMS data releases started to include geospatial
    coordinates alongside the monitoring station name. The registry is built
    from all such releases and used to retrospectively assign coordinates to
    stations in earlier releases where only station names are provided.
    """

    def __init__(self) -> None:  # noqa: D107
        self._registry: pl.DataFrame | None = None

    @property
    def data(self) -> pl.DataFrame:
        """Get the location registry data.

        Returns:
            A DataFrame with one row per unique monitoring location, containing
            columns ``latitude``, ``longitude``, and ``location_name``.

        Raises:
            LocationRegistryError: If the registry has not been built yet.

        """
        if self._registry is None:
            msg = "Registry has not been built. Call build_from_releases first."
            raise LocationRegistryError(msg)
        return self._registry

    def build_from_releases(self, releases: Sequence[AnnualYearData]) -> pl.DataFrame:
        """Build a location registry from all downloaded releases from 2025 onwards.

        Releases predating 2025 are ignored. All monthly files from qualifying
        releases are concatenated, then grouped by monitoring station. Where the
        same station appears across multiple files (e.g. due to minor GPS drift)
        its coordinates are averaged across all observations.

        Args:
            releases: All downloaded annual releases, as returned by
                ``Client.download_releases``. Releases before 2025 are ignored.

        Returns:
            A DataFrame with one row per unique monitoring location, containing
            columns ``latitude``, ``longitude``, and ``location_name``.

        Raises:
            LocationRegistryError: If no files are found in releases from 2025
                onwards.

        """
        all_files = [
            f
            for r in releases
            if isinstance(r, MonthlyYearData) and r.year >= _REGISTRY_YEAR
            for f in (
                r.fixed.ordered_monthly_file_names + r.mobile.ordered_monthly_file_names
            )
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
            .rename({"monitor_location": MONTHLY_ALIASES["monitor_location"]})
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

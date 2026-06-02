"""Tests for LocationRegistry."""

from typing import TYPE_CHECKING

import polars as pl
import pytest
from uk_rimnet_core.location_registry import LocationRegistry, LocationRegistryError
from uk_rimnet_core.models import MonthlyData, MonthlyYearData

if TYPE_CHECKING:
    from pathlib import Path


class TestLocationRegistryBuildFromReleases:  # noqa: D101
    @pytest.fixture(autouse=True)
    def _setup_tmp(self, tmp_path: Path) -> None:
        self._tmp = tmp_path

    def _write_csv(self, filename: str, rows: list[dict[str, object]]) -> str:
        path = self._tmp / filename
        pl.DataFrame(rows).write_csv(path)
        return str(path)

    def _release(
        self,
        year: int,
        fixed_files: list[str | None] | None = None,
        mobile_files: list[str | None] | None = None,
    ) -> MonthlyYearData:
        months = [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ]
        fixed_kwargs: dict[str, str] = {}
        mobile_kwargs: dict[str, str] = {}
        for i, f in enumerate(fixed_files or []):
            if f is not None:
                fixed_kwargs[months[i]] = f
        for i, f in enumerate(mobile_files or []):
            if f is not None:
                mobile_kwargs[months[i]] = f
        return MonthlyYearData(
            year=year,
            fixed=MonthlyData(**fixed_kwargs),
            mobile=MonthlyData(**mobile_kwargs),
        )

    def test_averages_coordinates_across_files(self) -> None:
        # A station that appears across multiple files with slightly different
        # coordinates (e.g. GPS drift) resolves to the mean of all observed values.

        # Arrange
        jan = self._write_csv(
            "jan.csv",
            [{"latitude": 51.0, "longitude": -1.0, "monitor_location": "ALPHA"}],
        )
        feb = self._write_csv(
            "feb.csv",
            [{"latitude": 53.0, "longitude": -3.0, "monitor_location": "ALPHA"}],
        )
        releases = [self._release(2025, fixed_files=[jan, feb])]

        # Act
        df = LocationRegistry().build_from_releases(releases)

        # Assert
        row = df.filter(pl.col("location_name") == "ALPHA")
        assert row["latitude"][0] == pytest.approx(52.0)
        assert row["longitude"][0] == pytest.approx(-2.0)

    def test_ignores_releases_before_2025(self) -> None:
        # Releases predating 2025 carry no location names and must be skipped.

        # Arrange
        jan = self._write_csv(
            "jan.csv",
            [{"latitude": 51.0, "longitude": -1.0, "monitor_location": "ALPHA"}],
        )
        releases = [self._release(2024, fixed_files=[jan])]

        # Act / Assert
        with pytest.raises(LocationRegistryError):
            LocationRegistry().build_from_releases(releases)

    def test_uses_files_from_multiple_years(self) -> None:
        # Releases from 2025 and later are both used to build the registry.

        # Arrange
        jan_2025 = self._write_csv(
            "jan_2025.csv",
            [{"latitude": 51.0, "longitude": -1.0, "monitor_location": "ALPHA"}],
        )
        jan_2026 = self._write_csv(
            "jan_2026.csv",
            [{"latitude": 53.0, "longitude": -3.0, "monitor_location": "ALPHA"}],
        )
        releases = [
            self._release(2025, fixed_files=[jan_2025]),
            self._release(2026, fixed_files=[jan_2026]),
        ]

        # Act
        df = LocationRegistry().build_from_releases(releases)

        # Assert
        row = df.filter(pl.col("location_name") == "ALPHA")
        assert row["latitude"][0] == pytest.approx(52.0)
        assert row["longitude"][0] == pytest.approx(-2.0)

    def test_save_writes_registry_to_csv(self) -> None:
        # Arrange
        jan = self._write_csv(
            "jan.csv",
            [{"latitude": 51.5, "longitude": -0.1, "monitor_location": "BRAVO"}],
        )
        registry = LocationRegistry()
        registry.build_from_releases([self._release(2025, fixed_files=[jan])])
        out = self._tmp / "registry.csv"

        # Act
        registry.save(out)

        # Assert
        df = pl.read_csv(out)
        row = df.filter(pl.col("location_name") == "BRAVO")
        assert row["latitude"][0] == pytest.approx(51.5)
        assert row["longitude"][0] == pytest.approx(-0.1)

    def test_save_raises_when_registry_not_built(self) -> None:
        # Arrange
        out = self._tmp / "registry.csv"

        # Act / Assert
        with pytest.raises(LocationRegistryError):
            LocationRegistry().save(out)

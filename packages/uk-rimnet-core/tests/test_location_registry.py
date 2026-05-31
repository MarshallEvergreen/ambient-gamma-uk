"""Tests for LocationRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
import pytest
from uk_rimnet_core.location_registry import LocationRegistry, LocationRegistryError
from uk_rimnet_core.models import MonthlyDataFile, MonthlyYearData

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
            fixed=MonthlyDataFile(**fixed_kwargs),
            mobile=MonthlyDataFile(**mobile_kwargs),
        )

    def test_upserts_coordinates_with_most_recent_value(self) -> None:
        # A station that appears in January with one set of coordinates and then
        # again in February with updated coordinates should resolve to the February values.  # noqa: E501

        # Arrange
        jan = self._write_csv(
            "jan.csv",
            [{"latitude": 51.0, "longitude": -1.0, "monitor_location": "ALPHA"}],
        )
        feb = self._write_csv(
            "feb.csv",
            [{"latitude": 52.0, "longitude": -2.0, "monitor_location": "ALPHA"}],
        )
        release = self._release(2025, fixed_files=[jan, feb])

        # Act
        df = LocationRegistry().build_from_releases(release, [])

        # Assert
        row = df.filter(pl.col("monitor_location") == "ALPHA")
        assert row["latitude"][0] == pytest.approx(52.0)
        assert row["longitude"][0] == pytest.approx(-2.0)

    def test_raises_when_release_2025_has_wrong_year(self) -> None:
        # Arrange
        release = self._release(2026)

        # Act / Assert
        with pytest.raises(LocationRegistryError):
            LocationRegistry().build_from_releases(release, [])

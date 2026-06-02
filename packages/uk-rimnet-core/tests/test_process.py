"""Tests for process_single_release."""

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path
import pytest
from uk_rimnet_core._process import process_single_release
from uk_rimnet_core.location_registry import LocationRegistry
from uk_rimnet_core.models import (
    PreMobileYearData,
    QuarterlyData,
    QuarterlyYearData,
)

_CSV_HEADER = "Location,Mean,Min,Max,Std Dev\n"


def _quarter_csv(location: str) -> str:
    return f"{_CSV_HEADER}{location},0.10,0.05,0.15,0.01\n"


def _make_registry(*names: str) -> LocationRegistry:
    registry = LocationRegistry()
    registry._registry = pl.DataFrame(  # noqa: SLF001
        {
            "location_name": list(names),
            "latitude": [float(i + 1) * 10 for i in range(len(names))],
            "longitude": [float(-(i + 1)) for i in range(len(names))],
        },
    )
    return registry


class TestProcessPreMobileYearData:
    """process_single_release routes PreMobileYearData through _process_pre_mobile."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self._tmp = tmp_path

    def _write_csv(self, name: str, location: str) -> str:
        path = self._tmp / name
        path.write_text(_quarter_csv(location))
        return str(path)

    def test_quarters_are_concatenated_and_registry_coordinates_are_joined(
        self,
    ) -> None:
        # Arrange — four quarters each carry a distinct location to prove concatenation
        q1 = self._write_csv("q1.csv", "North")
        q2 = self._write_csv("q2.csv", "South")
        q3 = self._write_csv("q3.csv", "East")
        q4 = self._write_csv("q4.csv", "West")

        release = PreMobileYearData(
            year=2014,
            fixed=QuarterlyData(q1=q1, q2=q2, q3=q3, q4=q4),
        )
        # Registry: North=10.0, South=20.0, East=30.0, West=40.0
        registry = _make_registry("North", "South", "East", "West")

        # Act
        result = process_single_release(release, registry)

        # Assert
        assert result.height == 4
        assert set(result["location_name"].to_list()) == {
            "North",
            "South",
            "East",
            "West",
        }

        # Coordinates come from the registry, not the source files
        by_location = result.sort("location_name")
        assert by_location["latitude"].to_list() == pytest.approx(
            [30.0, 10.0, 20.0, 40.0],  # East, North, South, West
        )
        assert by_location["longitude"].to_list() == pytest.approx(
            [-3.0, -1.0, -2.0, -4.0],
        )


class TestProcessQuarterlyYearData:
    """process_single_release routes QuarterlyYearData through _process_quarterly."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self._tmp = tmp_path

    def _write_csv(self, name: str, location: str) -> str:
        path = self._tmp / name
        path.write_text(_quarter_csv(location))
        return str(path)

    def test_fixed_and_mobile_quarters_concatenated_with_registry_coordinates_joined(
        self,
    ) -> None:
        # Arrange — each of fixed/mobile has a distinct location per quarter
        fixed_q1 = self._write_csv("fixed_q1.csv", "Alpha")
        fixed_q2 = self._write_csv("fixed_q2.csv", "Beta")
        mobile_q1 = self._write_csv("mobile_q1.csv", "Gamma")
        mobile_q2 = self._write_csv("mobile_q2.csv", "Delta")

        release = QuarterlyYearData(
            year=2018,
            fixed=QuarterlyData(q1=fixed_q1, q2=fixed_q2),
            mobile=QuarterlyData(q1=mobile_q1, q2=mobile_q2),
        )
        # Registry: Alpha=10.0, Beta=20.0, Gamma=30.0, Delta=40.0
        registry = _make_registry("Alpha", "Beta", "Gamma", "Delta")

        # Act
        result = process_single_release(release, registry)

        # Assert
        assert result.height == 4
        assert set(result["location_name"].to_list()) == {
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
        }

        # Coordinates come from the registry, not the source files
        by_location = result.sort("location_name")
        assert by_location["latitude"].to_list() == pytest.approx(
            [10.0, 20.0, 40.0, 30.0],  # Alpha, Beta, Delta, Gamma
        )
        assert by_location["longitude"].to_list() == pytest.approx(
            [-1.0, -2.0, -4.0, -3.0],
        )

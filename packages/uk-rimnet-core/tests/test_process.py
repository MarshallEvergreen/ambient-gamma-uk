"""Tests for process_single_release."""

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path
import pytest
from uk_rimnet_core._process import process_single_release
from uk_rimnet_core.location_registry import LocationRegistry
from uk_rimnet_core.models import (
    MonthlyData,
    MonthlyYearData,
    PreMobileYearData,
    QuarterlyData,
    QuarterlyYearData,
    TransitionYearData,
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


class TestProcessTransitionYearData:
    """process_single_release routes TransitionYearData through _process_transition."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self._tmp = tmp_path

    def _write_quarterly_csv(self, name: str, location: str) -> str:
        path = self._tmp / name
        path.write_text(_quarter_csv(location))
        return str(path)

    def _write_monthly_csv(self, name: str, lat: float, lon: float) -> str:
        # Monthly streaming format: no location name, coordinates only.
        # _assign_locations_from_registry resolves to named locations via haversine.
        path = self._tmp / name
        path.write_text(f"latitude,longitude,reading\n{lat},{lon},0.10\n")
        return str(path)

    def test_h1_quarterly_and_h2_monthly_combined_with_registry_coordinates_joined(
        self,
    ) -> None:
        # Arrange — one quarterly file per monitor type to give one row each from H1
        fixed_q1 = self._write_quarterly_csv("fixed_q1.csv", "Alpha")
        mobile_q1 = self._write_quarterly_csv("mobile_q1.csv", "Gamma")

        # H2 monthly files carry coordinates matching registry entries for Beta/Delta.
        # TransitionYearData requires all six H2 months; _complete_quarter yields
        # one complete Q3 triplet (Jul-Sep) when all six are present.
        beta_lat, beta_lon = 20.0, -2.0  # registry entry for Beta (index 1)
        delta_lat, delta_lon = 40.0, -4.0  # registry entry for Delta (index 3)

        fixed_monthly = {
            "jul": self._write_monthly_csv("fixed_jul.csv", beta_lat, beta_lon),
            "aug": self._write_monthly_csv("fixed_aug.csv", beta_lat, beta_lon),
            "sep": self._write_monthly_csv("fixed_sep.csv", beta_lat, beta_lon),
            "oct": self._write_monthly_csv("fixed_oct.csv", beta_lat, beta_lon),
            "nov": self._write_monthly_csv("fixed_nov.csv", beta_lat, beta_lon),
            "dec": self._write_monthly_csv("fixed_dec.csv", beta_lat, beta_lon),
        }
        mobile_monthly = {
            "jul": self._write_monthly_csv("mobile_jul.csv", delta_lat, delta_lon),
            "aug": self._write_monthly_csv("mobile_aug.csv", delta_lat, delta_lon),
            "sep": self._write_monthly_csv("mobile_sep.csv", delta_lat, delta_lon),
            "oct": self._write_monthly_csv("mobile_oct.csv", delta_lat, delta_lon),
            "nov": self._write_monthly_csv("mobile_nov.csv", delta_lat, delta_lon),
            "dec": self._write_monthly_csv("mobile_dec.csv", delta_lat, delta_lon),
        }

        release = TransitionYearData(
            year=2022,
            quarterly_fixed=QuarterlyData(q1=fixed_q1),
            quarterly_mobile=QuarterlyData(q1=mobile_q1),
            monthly_fixed=MonthlyData(**fixed_monthly),
            monthly_mobile=MonthlyData(**mobile_monthly),
        )
        # Registry: Alpha=10/-1, Beta=20/-2, Gamma=30/-3, Delta=40/-4
        registry = _make_registry("Alpha", "Beta", "Gamma", "Delta")

        # Act
        result = process_single_release(release, registry)

        # Assert — 6 rows: Alpha+Gamma (1 each, H1), Beta+Delta (2 each, H2 Q3+Q4)
        assert result.height == 6
        assert set(result["location_name"].to_list()) == {
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
        }

        # Fixed: Alpha (1 row H1) + Beta (2 rows H2); mobile: Gamma (1) + Delta (2)
        fixed = result.filter(pl.col("monitor_type") == "fixed")
        mobile = result.filter(pl.col("monitor_type") == "mobile")
        assert set(fixed["location_name"].unique().to_list()) == {"Alpha", "Beta"}
        assert set(mobile["location_name"].unique().to_list()) == {"Gamma", "Delta"}


class TestProcessMonthlyYearData:
    """process_single_release routes MonthlyYearData through _process_monthly."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self._tmp = tmp_path

    def _write_monthly_csv(self, name: str, lat: float, lon: float) -> str:
        path = self._tmp / name
        path.write_text(f"latitude,longitude,reading\n{lat},{lon},0.10\n")
        return str(path)

    def test_fixed_and_mobile_months_processed_with_registry_coordinates_joined(
        self,
    ) -> None:
        # Arrange — Q1 (Jan-Mar) for each monitor type; each file carries unique coords
        # that haversine-match to distinct registry stations
        alpha_lat, alpha_lon = 10.0, -1.0  # registry entry for Alpha (index 0)
        beta_lat, beta_lon = 20.0, -2.0  # registry entry for Beta (index 1)

        fixed_months = {
            "jan": self._write_monthly_csv("fixed_jan.csv", alpha_lat, alpha_lon),
            "feb": self._write_monthly_csv("fixed_feb.csv", alpha_lat, alpha_lon),
            "mar": self._write_monthly_csv("fixed_mar.csv", alpha_lat, alpha_lon),
        }
        mobile_months = {
            "jan": self._write_monthly_csv("mobile_jan.csv", beta_lat, beta_lon),
            "feb": self._write_monthly_csv("mobile_feb.csv", beta_lat, beta_lon),
            "mar": self._write_monthly_csv("mobile_mar.csv", beta_lat, beta_lon),
        }

        release = MonthlyYearData(
            year=2023,
            fixed=MonthlyData(**fixed_months),
            mobile=MonthlyData(**mobile_months),
        )
        registry = _make_registry("Alpha", "Beta")

        # Act
        result = process_single_release(release, registry)

        # Assert
        assert result.height == 2
        assert set(result["location_name"].to_list()) == {"Alpha", "Beta"}

        by_location = result.sort("location_name")
        assert by_location["latitude"].to_list() == pytest.approx([10.0, 20.0])
        assert by_location["longitude"].to_list() == pytest.approx([-1.0, -2.0])

        assert result.filter(pl.col("location_name") == "Alpha")[
            "monitor_type"
        ].to_list() == ["fixed"]
        assert result.filter(pl.col("location_name") == "Beta")[
            "monitor_type"
        ].to_list() == ["mobile"]

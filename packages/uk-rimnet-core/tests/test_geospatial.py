"""Tests for geospatial utilities."""

import polars as pl
import pytest
from uk_rimnet_core._geospatial import haversine


class TestHaversine:  # noqa: D101
    def _registry(self, entries: list[tuple[float, float, str]]) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "latitude": [e[0] for e in entries],
                "longitude": [e[1] for e in entries],
                "location_name": [e[2] for e in entries],
            },
        )

    def _readings(self, points: list[tuple[float, float]]) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "latitude": [p[0] for p in points],
                "longitude": [p[1] for p in points],
            },
        )

    def _nearest(self, readings: pl.DataFrame, registry: pl.DataFrame) -> pl.DataFrame:
        return (
            readings.join(registry, how="cross", suffix="_registry")
            .with_columns(
                haversine(
                    pl.col("latitude"),
                    pl.col("longitude"),
                    pl.col("latitude_registry"),
                    pl.col("longitude_registry"),
                ).alias("distance"),
            )
            .sort("distance")
            .group_by(["latitude", "longitude"], maintain_order=True)
            .first()
        )

    def test_london_to_edinburgh_distance(self) -> None:
        # Verify the haversine value against the known ~534 km great-circle distance

        # Arrange
        registry = self._registry([(55.9533, -3.1883, "Edinburgh")])
        readings = self._readings(
            [
                (51.5074, -0.1278),
            ],
        )

        # Act
        result = self._nearest(readings, registry)

        # Assert
        assert result["distance"][0] == pytest.approx(534.0, abs=1.0)

    def test_nearest_station_resolves_correctly(self) -> None:
        # A reading closer to London than Edinburgh should resolve to London.

        # Arrange
        registry = self._registry(
            [
                (51.5074, -0.1278, "London"),
                (55.9533, -3.1883, "Edinburgh"),
            ],
        )
        readings = self._readings([(51.6, -0.2)])  # just north of London

        # Act
        result = self._nearest(readings, registry)

        # Assert
        assert result["location_name"][0] == "London"

    def test_zero_distance_for_exact_match(self) -> None:
        # A reading at the exact coordinates of a registry entry has distance zero.

        # Arrange
        registry = self._registry([(51.5074, -0.1278, "London")])
        readings = self._readings([(51.5074, -0.1278)])

        # Act
        result = self._nearest(readings, registry)

        # Assert
        assert result["distance"][0] == pytest.approx(0.0)

"""Geospatial Utilities."""

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl


def haversine(
    lat1: pl.Expr,
    lon1: pl.Expr,
    lat2: pl.Expr,
    lon2: pl.Expr,
) -> pl.Expr:
    """Compute haversine distance in kilometres between two sets of coordinates.

    Args:
        lat1: Latitude of the first point in degrees.
        lon1: Longitude of the first point in degrees.
        lat2: Latitude of the second point in degrees.
        lon2: Longitude of the second point in degrees.

    Returns:
        Distance in kilometres as a Float64 expression.

    """
    r = 6371.0
    dlat = (lat2 - lat1) * (math.pi / 180)
    dlon = (lon2 - lon1) * (math.pi / 180)
    lat1_rad = lat1 * (math.pi / 180)
    lat2_rad = lat2 * (math.pi / 180)
    a = (dlat / 2).sin().pow(2) + lat1_rad.cos() * lat2_rad.cos() * (
        dlon / 2
    ).sin().pow(2)
    return a.sqrt().arcsin() * 2 * r

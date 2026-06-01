"""Canonical column name mappings for RIMNET/RREMS data files."""

QUARTERLY_STAT_ALIASES: dict[str, str] = {
    "location": "location_name",
    "monitor_location": "location_name",
    "site normal level": "site_normal",
    "standard deviation": "std_dev",
    "std deviation": "std_dev",
    "std dev": "std_dev",
    "mean": "mean",
    "avg": "mean",
    "average": "mean",
    "min": "min",
    "max": "max",
}

MONTHLY_ALIASES: dict[str, str] = {
    # Title Case variants (2022 H2 fixed files only)
    "reading date & time": "reading_date",
    "site latitude": "latitude",
    "site longitude": "longitude",
    "reading": "reading",
    "site normal": "site_normal",
    # Snake case (all other monthly files)
    "reading_date": "reading_date",
    "latitude": "latitude",
    "longitude": "longitude",
    "site_normal": "site_normal",
    "monitor_location": "location_name",
}

MONTHLY_REQUIRED: frozenset[str] = frozenset(
    ["latitude", "longitude", "reading", "site_normal", "monitor_location"],
)

QUARTERLY_CANONICAL: frozenset[str] = frozenset(
    ["location_name", "site_normal", "std_dev", "mean", "min", "max"],
)

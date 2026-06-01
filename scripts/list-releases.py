"""List the currently available releases."""  # noqa: INP001

import asyncio
from pathlib import Path

import polars as pl
from loguru import logger
from uk_rimnet_core import LocationRegistry
from uk_rimnet_core._readers import read_quarterly_stats_file
from uk_rimnet_core.client import Client


async def _main() -> None:
    client = Client()

    destination = "/Users/abie/Dev/uk-rimnet/bin"

    releases = await client.async_.download_releases(
        destination=destination,
    )

    logger.info(f"Found {len(releases)} releases")
    for release in releases:
        logger.info("Found release: {release}", release=release)

    # Build the Location Registry
    registry = LocationRegistry()
    registry_data = registry.build_from_releases(
        release_2025=releases[-2],  # ty:ignore[invalid-argument-type]
        subsequent_releases=releases[-1:],  # ty:ignore[invalid-argument-type]
    )
    registry.save(Path("bin/registry.csv"))
    logger.info(f"Location registry built with {len(registry_data)} unique locations.")
    path_xlsx = Path(
        "/Users/abie/Dev/uk-rimnet/bin/2020/rimmet-mobile-monitors-summary-july-september-2020.csv",
    )

    quarterly_xlsx = read_quarterly_stats_file(path_xlsx, 17, 1, "fixed")

    quarterly_xlsx = (
        quarterly_xlsx.join(
            registry_data,
            left_on="location_name",
            right_on="location_name",
            how="left",
        )
        .with_columns(
            pl.coalesce(["latitude", "latitude_right"]).alias("latitude"),
            pl.coalesce(["longitude", "longitude_right"]).alias("longitude"),
        )
        .drop(["latitude_right", "longitude_right"])
    )

    quarterly_xlsx.filter(pl.col("longitude").is_null())


if __name__ == "__main__":
    asyncio.run(main=_main())

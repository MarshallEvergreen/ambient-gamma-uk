"""List the currently available releases."""  # noqa: INP001

import asyncio

from loguru import logger
from uk_rimnet_core import LocationRegistry
from uk_rimnet_core.client import GovUkRIMNETRRMESClient


async def _main() -> None:
    client = GovUkRIMNETRRMESClient()

    destination = "/Users/abie/Dev/uk-rimnet/bin"

    releases = await client.async_.download_releases(
        destination=destination,
    )

    logger.info(f"Found {len(releases)} releases")
    for release in releases:
        logger.info("Found release: {release}", release=release)

    # Build the Location Registry
    registry = LocationRegistry().build_from_releases(
        release_2025=releases[-2],  # ty:ignore[invalid-argument-type]
        subsequent_releases=releases[-1:],  # ty:ignore[invalid-argument-type]
    )
    logger.info(f"Location registry built with {len(registry)} unique locations.")


if __name__ == "__main__":
    asyncio.run(main=_main())

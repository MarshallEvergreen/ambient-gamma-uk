"""List the currently available releases."""  # noqa: INP001

import asyncio

from loguru import logger
from uk_rimnet_core.client import GovUkCatalogueClient


async def _main() -> None:
    client = GovUkCatalogueClient()
    downloads = await client.download_releases(
        destination="/Users/abie/Dev/uk-rimnet/bin",
    )

    logger.info(f"Found {len(downloads)} releases")
    for release in downloads:
        logger.info("Found release: {release}", release=release)


if __name__ == "__main__":
    asyncio.run(main=_main())

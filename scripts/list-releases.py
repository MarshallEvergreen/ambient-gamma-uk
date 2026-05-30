"""List the currently available releases."""  # noqa: INP001

from loguru import logger
from uk_rimnet_core.catalogue import GovUkCatalogueClient

if __name__ == "__main__":
    client = GovUkCatalogueClient()
    releases = client.list_releases()

    logger.info(f"Found {len(releases)} releases")
    for release in releases:
        logger.info("Found release: {release}", release=release)

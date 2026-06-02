"""High-level dataset builder for the full RIMNET/RREMS archive."""

import asyncio
from typing import TYPE_CHECKING

import polars as pl

from uk_rimnet_core._process import process_single_release
from uk_rimnet_core.client import Client
from uk_rimnet_core.location_registry import LocationRegistry

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem


async def build_dataset_async(
    destination: str,
    client: Client | None = None,
    fs: AbstractFileSystem | None = None,
) -> pl.DataFrame:
    """Download all available releases and return the unified geospatial dataset.

    This is the primary entry point for working with the full archive. It
    orchestrates three steps: downloading all releases from GOV.UK, constructing
    the location registry from 2025-onwards files, and processing every annual
    release into a single consistent DataFrame with quarterly statistics and
    geospatial coordinates for each monitoring station.

    Args:
        destination: Directory path to download raw files into. Files that
            already exist are skipped, so repeated calls are cheap.
        client: Client instance to use for discovery and download. A default
            client is created if not provided.
        fs: Filesystem to write downloaded files to. Defaults to the local
            filesystem. Accepts any ``fsspec``-compatible filesystem (e.g. S3,
            GCS, in-memory).

    Returns:
        A DataFrame with one row per monitoring station per quarter, containing
        columns: ``location_name``, ``latitude``, ``longitude``,
        ``monitor_type``, ``year``, ``quarter``, ``mean``, ``min``, ``max``,
        ``std_dev``, ``site_normal``, ``unit``.

        Stations that cannot be matched to a known location are excluded.
        ``site_normal`` is null for mobile monitors and for fixed monitors
        predating 2012.

    """
    resolved_client = client or Client()
    releases = await resolved_client.async_.download_releases(
        destination=destination,
        fs=fs,
    )
    registry = LocationRegistry()
    registry.build_from_releases(releases)
    return pl.concat(
        [process_single_release(r, registry) for r in releases],
        how="diagonal",
    )


def build_dataset(destination: str, client: Client | None = None) -> pl.DataFrame:
    """Synchronous version of build_dataset."""  # noqa: D401
    return asyncio.run(build_dataset_async(destination=destination, client=client))

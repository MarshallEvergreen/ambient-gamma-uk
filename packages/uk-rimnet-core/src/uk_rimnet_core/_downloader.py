import asyncio
from typing import TYPE_CHECKING

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fsspec import AbstractFileSystem

    from uk_rimnet_core.models import DataRelease


class Downloader:
    """Downloads a set of data releases concurrently to a remote filesystem.

    Args:
        client: An httpx.AsyncClient used to stream file downloads.

    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient()

    async def download_all(
        self,
        releases: set[DataRelease],
        destination: str,
        fs: AbstractFileSystem,
    ) -> Sequence[str]:
        """Download all releases concurrently, skipping files that already exist.

        Args:
            releases: The set of releases to download.
            destination: Directory path on ``fs`` to write files into.
            fs: The target filesystem (local, S3, memory, etc.).

        Returns:
            List of paths to the downloaded files, one per release.

        Raises:
            ExceptionGroup: If any individual download fails.

        """
        fs.makedirs(destination, exist_ok=True)
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            results = await asyncio.gather(
                *[
                    self._download_one(release, destination, fs, progress)
                    for release in releases
                ],
                return_exceptions=True,
            )
        errors: Sequence[Exception] = [r for r in results if isinstance(r, Exception)]
        if errors:
            msg = "download failures"
            raise ExceptionGroup(msg, errors)
        return [r for r in results if isinstance(r, str)]

    async def _download_one(
        self,
        release: DataRelease,
        destination: str,
        fs: AbstractFileSystem,
        progress: Progress,
    ) -> str:
        filename = release.filename
        path = f"{destination}/{filename}"
        if fs.exists(path):
            return path
        async with self._client.stream("GET", release.url) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            task_id = progress.add_task(
                filename,
                total=int(content_length) if content_length else None,
            )
            with fs.open(path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))
        return path

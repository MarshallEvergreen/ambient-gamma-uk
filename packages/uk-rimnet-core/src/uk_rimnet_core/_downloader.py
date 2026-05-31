import asyncio
from typing import TYPE_CHECKING

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fsspec import AbstractFileSystem

    from uk_rimnet_core.models import DataRelease

_PROGRESS_COLUMNS = (
    SpinnerColumn(),
    TextColumn("[bold blue]{task.description}", justify="left"),
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
)


class Downloader:
    """Downloads data releases to a filesystem sequentially or concurrently.

    Args:
        async_client: An httpx.AsyncClient used for concurrent downloads.
        sync_client: An httpx.Client used for sequential downloads.

    """

    def __init__(
        self,
        async_client: httpx.AsyncClient | None = None,
        sync_client: httpx.Client | None = None,
    ) -> None:
        self._async_client = async_client or httpx.AsyncClient()
        self._sync_client = sync_client or httpx.Client()

    def download_all_sync(
        self,
        releases: set[DataRelease],
        destination: str,
        fs: AbstractFileSystem,
    ) -> list[str]:
        """Download all releases sequentially, skipping files that already exist.

        Args:
            releases: The set of releases to download.
            destination: Directory path on ``fs`` to write files into.
            fs: The target filesystem (local, S3, memory, etc.).

        Returns:
            List of paths to the downloaded (or already-existing) files.

        Raises:
            httpx.HTTPStatusError: If any individual file download fails.

        """
        fs.makedirs(destination, exist_ok=True)
        sorted_releases = sorted(releases, key=lambda r: r.filename)
        total = len(sorted_releases)
        paths: list[str] = []
        with Progress(*_PROGRESS_COLUMNS) as progress:
            task_id = progress.add_task("", total=None)
            for i, release in enumerate(sorted_releases, start=1):
                description = f"[{i}/{total}] {release.filename}"
                path = self._download_one_sync(
                    release,
                    destination,
                    fs,
                    progress,
                    task_id,
                    description,
                )
                paths.append(path)
        return paths

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
        with Progress(*_PROGRESS_COLUMNS) as progress:
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

    def _download_one_sync(  # noqa: PLR0913
        self,
        release: DataRelease,
        destination: str,
        fs: AbstractFileSystem,
        progress: Progress,
        task_id: TaskID,
        description: str,
    ) -> str:
        path = f"{destination}/{release.filename}"
        if fs.exists(path):
            return path
        with self._sync_client.stream("GET", release.url) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            progress.reset(
                task_id,
                description=description,
                total=int(content_length) if content_length else None,
            )
            with fs.open(path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))
        return path

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
        async with self._async_client.stream("GET", release.url) as response:
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

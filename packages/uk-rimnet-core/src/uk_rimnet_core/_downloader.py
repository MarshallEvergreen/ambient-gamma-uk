import asyncio
import zipfile
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

from uk_rimnet_core._indexer import build_annual_year_data

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem

    from uk_rimnet_core.models import AnnualYearData, DataRelease

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

    async def download_all(
        self,
        releases: set[DataRelease],
        destination: str,
        fs: AbstractFileSystem,
    ) -> list[AnnualYearData]:
        """Download all releases concurrently, skipping files that already exist.

        Args:
            releases: The set of releases to download.
            destination: Directory path on ``fs`` to write files into.
            fs: The target filesystem (local, S3, memory, etc.).

        Returns:
            One ``AnnualYearData`` per calendar year covered by the releases.

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
        errors: list[Exception] = [r for r in results if isinstance(r, Exception)]
        if errors:
            msg = "download failures"
            raise ExceptionGroup(msg, errors)

        release_paths: list[tuple[DataRelease, str]] = []
        for result in results:
            if isinstance(result, BaseException):
                continue
            release, path = result  # type: ignore[misc]
            if path.endswith(".zip"):
                release_paths.extend(
                    (release, extracted)
                    for extracted in self._unzip(path, destination, fs)
                )
            else:
                release_paths.append((release, path))

        return build_annual_year_data(release_paths)

    def _unzip(self, path: str, destination: str, fs: AbstractFileSystem) -> list[str]:
        extracted: list[str] = []
        zip_name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        out_dir = f"{destination}/{zip_name}"
        fs.makedirs(out_dir, exist_ok=True)
        with fs.open(path, "rb") as f, zipfile.ZipFile(f) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                archived_filename = info.filename.rsplit("/", 1)[-1]
                out_path = f"{out_dir}/{archived_filename}"
                with zf.open(info) as member, fs.open(out_path, "wb") as out:
                    while chunk := member.read(65536):
                        out.write(chunk)
                extracted.append(out_path)
        return extracted

    async def _download_one(
        self,
        release: DataRelease,
        destination: str,
        fs: AbstractFileSystem,
        progress: Progress,
    ) -> tuple[DataRelease, str]:
        filename = release.filename
        path = f"{destination}/{filename}"
        if fs.exists(path):
            return release, path
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
        return release, path

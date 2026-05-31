"""Downloader tests."""

from typing import TYPE_CHECKING

import httpx
import pytest
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.local import LocalFileSystem
from uk_rimnet_core._downloader import Downloader
from uk_rimnet_core.models import AnnualRelease, MonthlyRelease

if TYPE_CHECKING:
    from pathlib import Path

_CSV_CONTENT = b"reading_date,latitude,longitude,reading,units,monitor_location\n"
_ZIP_CONTENT = b"PK\x03\x04fake zip content"

_FIXED_URL = "https://assets.publishing.service.gov.uk/media/abc/Apr_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv"
_MOBILE_URL = "https://assets.publishing.service.gov.uk/media/def/Apr_2026_ambient_gamma_dose_rates_across_the_UK__mobile_RREMS_monitors_.csv"
_ANNUAL_URL = "https://assets.publishing.service.gov.uk/media/ghi/2020-ambient-gamma-radiation-dose-rates-across-the-uk.zip"


class _MockAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: dict[str, bytes]) -> None:
        self._responses = responses

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        content = self._responses.get(str(request.url))
        if content is not None:
            return httpx.Response(200, content=content)
        return httpx.Response(404)


class TestDownloader:  # noqa: D101
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.fs = DirFileSystem(fs=LocalFileSystem(), path=tmp_path.as_posix())

    def make_downloader(self, responses: dict[str, bytes]) -> Downloader:
        return Downloader(
            async_client=httpx.AsyncClient(transport=_MockAsyncTransport(responses)),
        )

    @pytest.mark.asyncio
    async def test_downloads_single_csv_to_destination(self) -> None:

        # Arrange
        releases: set[MonthlyRelease | AnnualRelease] = {
            MonthlyRelease(year=2026, month=4, monitor_type="fixed", url=_FIXED_URL),
        }
        downloader = self.make_downloader({_FIXED_URL: _CSV_CONTENT})

        # Act
        paths = await downloader.download_all(releases, "/output", self.fs)

        # Assert
        assert len(paths) == 1
        assert paths[0] == "/output/2026_04_fixed.csv"
        assert self.fs.cat(paths[0]) == _CSV_CONTENT

    @pytest.mark.asyncio
    async def test_downloads_multiple_releases_concurrently(self) -> None:

        # Arrange
        releases: set[MonthlyRelease | AnnualRelease] = {
            MonthlyRelease(year=2026, month=4, monitor_type="fixed", url=_FIXED_URL),
            MonthlyRelease(year=2026, month=4, monitor_type="mobile", url=_MOBILE_URL),
        }
        downloader = self.make_downloader(
            {_FIXED_URL: _CSV_CONTENT, _MOBILE_URL: _CSV_CONTENT},
        )

        # Act
        paths = await downloader.download_all(releases, "/output", self.fs)

        # Assert
        assert len(paths) == 2
        assert set(paths) == {
            "/output/2026_04_fixed.csv",
            "/output/2026_04_mobile.csv",
        }

    @pytest.mark.asyncio
    async def test_downloads_annual_zip_release(self) -> None:

        # Arrange
        releases: set[MonthlyRelease | AnnualRelease] = {
            AnnualRelease(year=2020, url=_ANNUAL_URL),
        }
        downloader = self.make_downloader({_ANNUAL_URL: _ZIP_CONTENT})

        # Act
        paths = await downloader.download_all(releases, "/output", self.fs)

        # Assert
        assert len(paths) == 1
        assert paths[0] == "/output/2020.zip"
        assert self.fs.cat(paths[0]) == _ZIP_CONTENT

    @pytest.mark.asyncio
    async def test_creates_destination_directory_if_missing(self) -> None:

        # Arrange
        releases: set[MonthlyRelease | AnnualRelease] = {
            MonthlyRelease(year=2026, month=4, monitor_type="fixed", url=_FIXED_URL),
        }
        downloader = self.make_downloader({_FIXED_URL: _CSV_CONTENT})

        # Act
        await downloader.download_all(releases, "/nested/output", self.fs)

        # Assert
        assert self.fs.isdir("/nested/output")

    @pytest.mark.asyncio
    async def test_skips_file_that_already_exists(self) -> None:

        # Arrange
        releases: set[MonthlyRelease | AnnualRelease] = {
            MonthlyRelease(year=2026, month=4, monitor_type="fixed", url=_FIXED_URL),
        }
        downloader = self.make_downloader({})  # no responses — would 404 if called
        existing_path = "/output/2026_04_fixed.csv"
        self.fs.makedirs("/output", exist_ok=True)
        with self.fs.open(existing_path, "wb") as f:
            f.write(_CSV_CONTENT)

        # Act
        paths = await downloader.download_all(releases, "/output", self.fs)

        # Assert
        assert paths == [existing_path]
        assert self.fs.cat(existing_path) == _CSV_CONTENT

    @pytest.mark.asyncio
    async def test_raises_on_failed_download(self) -> None:

        # Arrange
        releases: set[MonthlyRelease | AnnualRelease] = {
            MonthlyRelease(year=2026, month=4, monitor_type="fixed", url=_FIXED_URL),
        }
        downloader = self.make_downloader({})  # no responses — all return 404

        # Act / Assert
        with pytest.raises(ExceptionGroup):
            await downloader.download_all(releases, "/output", self.fs)

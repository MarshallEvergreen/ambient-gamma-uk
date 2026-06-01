"""Cataloguing tests."""

import io
import zipfile
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from pathlib import Path
import pytest
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.local import LocalFileSystem
from uk_rimnet_core.client import _PUBLICATION_URL, Client
from uk_rimnet_core.models import (
    AnnualRelease,
    MonthlyRelease,
    MonthlyYearData,
    QuarterlyYearData,
)

_CSV_CONTENT = b"reading_date,latitude,longitude,reading,units,monitor_location\n"
_ZIP_CSV_NAME = "q1_fixed_2020_stats.csv"


def _zip_bytes(name: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, content)
    return buf.getvalue()


_ZIP_CONTENT = _zip_bytes(_ZIP_CSV_NAME, _CSV_CONTENT)

_FIXED_URL = "https://assets.publishing.service.gov.uk/media/abc/Apr_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv"
_MOBILE_URL = "https://assets.publishing.service.gov.uk/media/def/Apr_2026_ambient_gamma_dose_rates_across_the_UK__mobile_RREMS_monitors_.csv"
_ANNUAL_URL = "https://assets.publishing.service.gov.uk/media/ghi/2020-ambient-gamma-radiation-dose-rates-across-the-uk.zip"


def _make_html(*hrefs: str) -> str:
    links = "\n".join(f'<a href="{href}">download</a>' for href in hrefs)
    return f"<html><body>{links}</body></html>"


class _MockTransport(httpx.BaseTransport):
    def __init__(
        self,
        html: str,
        file_responses: dict[str, bytes] | None = None,
    ) -> None:
        self._html = html
        self._file_responses = file_responses or {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == _PUBLICATION_URL:
            return httpx.Response(200, text=self._html)
        content = self._file_responses.get(url)
        if content is not None:
            return httpx.Response(200, content=content)
        return httpx.Response(404)


class _MockAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: dict[str, bytes]) -> None:
        self._responses = responses

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        content = self._responses.get(str(request.url))
        if content is not None:
            return httpx.Response(200, content=content)
        return httpx.Response(404)


class TestGovUkCatalogueClientListReleases:  # noqa: D101
    def _make_client(self, html: str) -> Client:
        return Client(
            client=httpx.Client(transport=_MockTransport(html)),
        )

    def test_returns_fixed_and_mobile_monthly_releases(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/abc/Apr_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            "https://assets.publishing.service.gov.uk/media/def/Apr_2026_ambient_gamma_dose_rates_across_the_UK__mobile_RREMS_monitors_.csv",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 2
        assert (
            MonthlyRelease(
                year=2026,
                month=4,
                monitor_type="fixed",
                url="https://assets.publishing.service.gov.uk/media/abc/Apr_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            )
            in releases
        )
        assert (
            MonthlyRelease(
                year=2026,
                month=4,
                monitor_type="mobile",
                url="https://assets.publishing.service.gov.uk/media/def/Apr_2026_ambient_gamma_dose_rates_across_the_UK__mobile_RREMS_monitors_.csv",
            )
            in releases
        )

    def test_returns_releases_across_multiple_months(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/abc/Apr_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            "https://assets.publishing.service.gov.uk/media/def/Mar_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            "https://assets.publishing.service.gov.uk/media/ghi/Jan_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 3
        monthly = [r for r in releases if isinstance(r, MonthlyRelease)]
        assert {r.month for r in monthly} == {1, 3, 4}

    def test_returns_monthly_release_for_full_month_name_in_filename(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/abc/June_2025_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            "https://assets.publishing.service.gov.uk/media/def/July_2025_ambient_gamma_dose_rates_across_the_UK__mobile_RREMS_monitors_.csv",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 2
        assert (
            MonthlyRelease(
                year=2025,
                month=6,
                monitor_type="fixed",
                url="https://assets.publishing.service.gov.uk/media/abc/June_2025_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            )
            in releases
        )
        assert (
            MonthlyRelease(
                year=2025,
                month=7,
                monitor_type="mobile",
                url="https://assets.publishing.service.gov.uk/media/def/July_2025_ambient_gamma_dose_rates_across_the_UK__mobile_RREMS_monitors_.csv",
            )
            in releases
        )

    def test_returns_monthly_release_for_rrems_filename_format(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/67cfef51bc1f4a3395b33cc4/mobile-rrems-monitors-feb-2025-ambient-gamma-dose-rates.csv",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 1
        assert (
            MonthlyRelease(
                year=2025,
                month=2,
                monitor_type="mobile",
                url="https://assets.publishing.service.gov.uk/media/67cfef51bc1f4a3395b33cc4/mobile-rrems-monitors-feb-2025-ambient-gamma-dose-rates.csv",
            )
            in releases
        )

    def test_returns_monthly_release_for_rrems_reversed_filename_format(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/6978d1a51c24881f40a4d6b1/ambient-gamma-dose-rates-mobile-rrems-monitors-nov-2025.csv",
            "https://assets.publishing.service.gov.uk/media/6978d12f5da1fd4ddea98c33/ambient-gamma-dose-rates-fixed-rrems-monitors-dec-2025.csv",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 2
        assert (
            MonthlyRelease(
                year=2025,
                month=11,
                monitor_type="mobile",
                url="https://assets.publishing.service.gov.uk/media/6978d1a51c24881f40a4d6b1/ambient-gamma-dose-rates-mobile-rrems-monitors-nov-2025.csv",
            )
            in releases
        )
        assert (
            MonthlyRelease(
                year=2025,
                month=12,
                monitor_type="fixed",
                url="https://assets.publishing.service.gov.uk/media/6978d12f5da1fd4ddea98c33/ambient-gamma-dose-rates-fixed-rrems-monitors-dec-2025.csv",
            )
            in releases
        )

    def test_returns_annual_release_for_zip_url(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/abc/2020-ambient-gamma-radiation-dose-rates-across-the-uk.zip",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 1
        assert (
            AnnualRelease(
                year=2020,
                url="https://assets.publishing.service.gov.uk/media/abc/2020-ambient-gamma-radiation-dose-rates-across-the-uk.zip",
            )
            in releases
        )

    def test_returns_annual_release_for_underscore_zip_url(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/5a84402ee5274a2e8ab5a3d3/2015_ambient_gamma_radiation_dose_rates_across_the_UK.zip",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 1
        assert (
            AnnualRelease(
                year=2015,
                url="https://assets.publishing.service.gov.uk/media/5a84402ee5274a2e8ab5a3d3/2015_ambient_gamma_radiation_dose_rates_across_the_UK.zip",
            )
            in releases
        )

    def test_returns_annual_release_for_rrems_zip_url(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/6615811d2138736672031baa/ambient-gamma-dose-rates-rrems-monitors-2023.zip",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 1
        assert (
            AnnualRelease(
                year=2023,
                url="https://assets.publishing.service.gov.uk/media/6615811d2138736672031baa/ambient-gamma-dose-rates-rrems-monitors-2023.zip",
            )
            in releases
        )

    def test_returns_mix_of_monthly_and_annual_releases(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/abc/Apr_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            "https://assets.publishing.service.gov.uk/media/def/2020-ambient-gamma-radiation-dose-rates-across-the-uk.zip",
            "https://assets.publishing.service.gov.uk/media/ghi/2019-ambient-gamma-radiation-dose-rates-across-the-uk.zip",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 3
        assert sum(1 for r in releases if isinstance(r, MonthlyRelease)) == 1
        assert sum(1 for r in releases if isinstance(r, AnnualRelease)) == 2

    def test_ignores_non_data_links(self) -> None:

        # Arrange
        html = _make_html(
            "https://assets.publishing.service.gov.uk/media/abc/Apr_2026_ambient_gamma_dose_rates_across_the_UK__Fixed_RREMS_monitors_.csv",
            "https://www.gov.uk/some/other/page",
            "/relative/link",
            "https://assets.publishing.service.gov.uk/media/xyz/some_other_file.csv",
        )

        # Act
        releases = self._make_client(html).list_releases()

        # Assert
        assert len(releases) == 1

    def test_raises_on_http_error(self) -> None:

        # Arrange
        class _ErrorTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:  # noqa: ARG002
                return httpx.Response(503)

        client = Client(
            client=httpx.Client(transport=_ErrorTransport()),
        )

        # Act / Assert
        try:
            client.list_releases()
            pytest.fail("expected HTTPStatusError")
        except httpx.HTTPStatusError:
            pass


class TestGovUkCatalogueClientAsyncDownloadReleases:  # noqa: D101
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.fs = DirFileSystem(fs=LocalFileSystem(), path=tmp_path.as_posix())

    def _make_client(
        self,
        html: str,
        file_responses: dict[str, bytes],
    ) -> Client:
        return Client(
            client=httpx.Client(transport=_MockTransport(html)),
            async_client=httpx.AsyncClient(
                transport=_MockAsyncTransport(file_responses),
            ),
        )

    @pytest.mark.asyncio
    async def test_downloads_csv_to_destination(self) -> None:

        # Arrange
        client = self._make_client(_make_html(_FIXED_URL), {_FIXED_URL: _CSV_CONTENT})

        # Act
        result = await client.async_.download_releases("/output", self.fs)

        # Assert
        assert len(result) == 1
        data = result[0]
        assert isinstance(data, MonthlyYearData)
        assert data.year == 2026
        assert data.fixed is not None
        path = data.fixed.apr
        assert path is not None
        assert path == "/output/2026_04_fixed.csv"
        assert self.fs.cat(path) == _CSV_CONTENT

    @pytest.mark.asyncio
    async def test_downloads_multiple_releases(self) -> None:

        # Arrange
        client = self._make_client(
            _make_html(_FIXED_URL, _MOBILE_URL),
            {_FIXED_URL: _CSV_CONTENT, _MOBILE_URL: _CSV_CONTENT},
        )

        # Act
        result = await client.async_.download_releases("/output", self.fs)

        # Assert — both releases are for 2026 so they are grouped into one year
        assert len(result) == 1
        data = result[0]
        assert isinstance(data, MonthlyYearData)
        assert data.year == 2026
        assert data.fixed is not None
        assert data.fixed.apr == "/output/2026_04_fixed.csv"
        assert data.mobile is not None
        assert data.mobile.apr == "/output/2026_04_mobile.csv"

    @pytest.mark.asyncio
    async def test_downloads_annual_zip(self) -> None:

        # Arrange
        client = self._make_client(_make_html(_ANNUAL_URL), {_ANNUAL_URL: _ZIP_CONTENT})

        # Act
        result = await client.async_.download_releases("/output", self.fs)

        # Assert
        assert len(result) == 1
        data = result[0]
        assert isinstance(data, QuarterlyYearData)
        assert data.year == 2020
        path = data.fixed.q1
        assert path is not None
        assert path == f"/output/2020/{_ZIP_CSV_NAME}"
        assert self.fs.cat(path) == _CSV_CONTENT

    @pytest.mark.asyncio
    async def test_creates_destination_directory_if_missing(self) -> None:

        # Arrange
        client = self._make_client(_make_html(_FIXED_URL), {_FIXED_URL: _CSV_CONTENT})

        # Act
        await client.async_.download_releases("/nested/output", self.fs)

        # Assert
        assert self.fs.isdir("/nested/output")

    @pytest.mark.asyncio
    async def test_skips_file_that_already_exists(self) -> None:

        # Arrange
        client = self._make_client(
            _make_html(_FIXED_URL),
            {},
        )  # no responses — would 404 if called
        existing_path = "/output/2026_04_fixed.csv"
        self.fs.makedirs("/output", exist_ok=True)
        with self.fs.open(existing_path, "wb") as f:
            f.write(_CSV_CONTENT)

        # Act
        result = await client.async_.download_releases("/output", self.fs)

        # Assert
        assert len(result) == 1
        data = result[0]
        assert isinstance(data, MonthlyYearData)
        assert data.fixed is not None
        path = data.fixed.apr
        assert path is not None
        assert path == existing_path
        assert self.fs.cat(path) == _CSV_CONTENT

    @pytest.mark.asyncio
    async def test_raises_on_failed_download(self) -> None:

        # Arrange
        client = self._make_client(
            _make_html(_FIXED_URL),
            {},
        )  # no responses — all return 404

        # Act / Assert
        with pytest.raises(ExceptionGroup):
            await client.async_.download_releases("/output", self.fs)

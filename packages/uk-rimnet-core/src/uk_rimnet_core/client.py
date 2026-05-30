"""UK Government RIMNET Catalogue."""

import re
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup
from fsspec.implementations.local import LocalFileSystem

from uk_rimnet_core._downloader import Downloader
from uk_rimnet_core.models import (
    AnnualRelease,
    DataRelease,
    MonitorType,
    MonthlyRelease,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fsspec import AbstractFileSystem


_PUBLICATION_URL = "https://www.gov.uk/government/publications/ambient-gamma-radiation-dose-rates-across-the-uk"
_ASSET_HOST = "assets.publishing.service.gov.uk"

_MONTH_NAME_TO_INT: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_MONTHLY_FILENAME_RE = re.compile(
    r"(\w{3,4})_(\d{4})_ambient_gamma_dose_rates_across_the_UK__"
    r"(Fixed|mobile)_RREMS_monitors_\.csv$",
    re.IGNORECASE,
)

_MONTHLY_RREMS_FILENAME_RE = re.compile(
    r"(fixed|mobile)-rrems-monitors-(\w{3})-(\d{4})-ambient-gamma-dose-rates\.csv$",
    re.IGNORECASE,
)

_MONTHLY_RREMS_FILENAME_RE2 = re.compile(
    r"ambient-gamma-dose-rates-(fixed|mobile)-rrems-monitors-(\w{3})-(\d{4})\.csv$",
    re.IGNORECASE,
)

_ANNUAL_FILENAME_RE = re.compile(
    r"(\d{4})[-_]ambient[-_]gamma[-_]radiation[-_]dose[-_]rates[-_]across[-_]the[-_]uk\.zip$",
    re.IGNORECASE,
)

_ANNUAL_RREMS_FILENAME_RE = re.compile(
    r"ambient-gamma-dose-rates-rrems-monitors-(\d{4})\.zip$",
    re.IGNORECASE,
)


class GovUkCatalogueClient:
    """Scrapes the GOV.UK publication page to discover available data releases.

    Args:
        client: An httpx.Client used to fetch the publication index page.

    """

    def __init__(  # noqa: D107
        self,
        client: httpx.Client | None = None,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._sync_client = client or httpx.Client()
        self._async_client = async_client or httpx.AsyncClient()
        self._downloader = Downloader(self._async_client)

    def list_releases(self) -> set[DataRelease]:
        """Fetch and parse the GOV.UK publication page to list all releases.

        Returns:
            A list of DataRelease objects for every CSV or ZIP file linked from the page.

        Raises:
            httpx.HTTPStatusError: If the publication page returns a non-2xx response.

        """  # noqa: E501
        response = self._sync_client.get(_PUBLICATION_URL)
        response.raise_for_status()
        return _parse_releases(response.text)

    async def download_releases(  # noqa: D102
        self,
        destination: str,
        fs: AbstractFileSystem | None = None,
    ) -> Sequence[str]:
        fs = fs or LocalFileSystem()
        releases = self.list_releases()
        return await self._downloader.download_all(
            releases=releases,
            destination=destination,
            fs=fs,
        )


def _parse_releases(html: str) -> set[DataRelease]:
    soup = BeautifulSoup(html, "html.parser")
    releases: list[DataRelease] = []
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if href is None or not isinstance(href, str) or _ASSET_HOST not in href:
            continue
        release = _parse_url(href)
        if release is not None:
            releases.append(release)
    return set(releases)


def _make_monthly_release(
    month_str: str,
    year_str: str,
    type_str: str,
    url: str,
) -> MonthlyRelease | None:
    month = _MONTH_NAME_TO_INT.get(month_str.lower()[:3])
    if month is None:
        return None
    monitor_type: MonitorType = "fixed" if type_str.lower() == "fixed" else "mobile"
    return MonthlyRelease(
        year=int(year_str),
        month=month,
        monitor_type=monitor_type,
        url=url,
    )


def _parse_url(url: str) -> DataRelease | None:
    filename = url.rsplit("/", 1)[-1]

    if m := _MONTHLY_FILENAME_RE.match(filename):
        month_str, year_str, type_str = m.groups()
        return _make_monthly_release(month_str, year_str, type_str, url)

    if m := _MONTHLY_RREMS_FILENAME_RE.match(filename):
        type_str, month_str, year_str = m.groups()
        return _make_monthly_release(month_str, year_str, type_str, url)

    if m := _MONTHLY_RREMS_FILENAME_RE2.match(filename):
        type_str, month_str, year_str = m.groups()
        return _make_monthly_release(month_str, year_str, type_str, url)

    if m := _ANNUAL_FILENAME_RE.match(filename):
        return AnnualRelease(year=int(m.group(1)), url=url)

    if m := _ANNUAL_RREMS_FILENAME_RE.match(filename):
        return AnnualRelease(year=int(m.group(1)), url=url)

    return None

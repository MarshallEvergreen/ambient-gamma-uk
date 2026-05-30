"""UK Government RIMNET Catalogue."""

import logging
import re

import httpx
from bs4 import BeautifulSoup

from uk_rimnet_core.models import (
    AnnualRelease,
    DataRelease,
    MonitorType,
    MonthlyRelease,
)

_logger = logging.getLogger(__name__)

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
    r"(\w{3})_(\d{4})_ambient_gamma_dose_rates_across_the_UK__"
    r"(Fixed|mobile)_RREMS_monitors_\.csv$",
    re.IGNORECASE,
)

_ANNUAL_FILENAME_RE = re.compile(
    r"(\d{4})-ambient-gamma-radiation-dose-rates-across-the-uk\.zip$",
    re.IGNORECASE,
)


class GovUkCatalogueClient:
    """Scrapes the GOV.UK publication page to discover available data releases.

    Args:
        client: An httpx.Client used to fetch the publication index page.

    """

    def __init__(self, client: httpx.Client | None = None) -> None:  # noqa: D107
        self._client = client or httpx.Client()

    def list_releases(self) -> set[DataRelease]:
        """Fetch and parse the GOV.UK publication page to list all releases.

        Returns:
            A list of DataRelease objects for every CSV or ZIP file linked from the page.

        Raises:
            httpx.HTTPStatusError: If the publication page returns a non-2xx response.

        """
        response = self._client.get(_PUBLICATION_URL)
        response.raise_for_status()
        return _parse_releases(response.text)


def _parse_releases(html: str) -> set[DataRelease]:
    soup = BeautifulSoup(html, "html.parser")
    releases: list[DataRelease] = []
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if href is None or _ASSET_HOST not in href:
            continue
        _logger.debug("Found candidate asset URL: %s", href)
        release = _parse_url(href)
        if release is not None:
            releases.append(release)
    return set(releases)


def _parse_url(url: str) -> DataRelease | None:
    filename = url.rsplit("/", 1)[-1]

    if monthly_match := _MONTHLY_FILENAME_RE.match(filename):
        month_str, year_str, type_str = monthly_match.groups()
        month = _MONTH_NAME_TO_INT.get(month_str.lower())
        if month is None:
            return None
        monitor_type: MonitorType = "fixed" if type_str.lower() == "fixed" else "mobile"
        return MonthlyRelease(
            year=int(year_str), month=month, monitor_type=monitor_type, url=url
        )

    if annual_match := _ANNUAL_FILENAME_RE.match(filename):
        (year_str,) = annual_match.groups()
        return AnnualRelease(year=int(year_str), url=url)

    return None

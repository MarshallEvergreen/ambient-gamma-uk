"""Cataloguing tests."""

import httpx
import pytest
from uk_rimnet_core.catalogue import _PUBLICATION_URL, GovUkCatalogueClient
from uk_rimnet_core.models import AnnualRelease, MonthlyRelease


def _make_html(*hrefs: str) -> str:
    links = "\n".join(f'<a href="{href}">download</a>' for href in hrefs)
    return f"<html><body>{links}</body></html>"


class _MockTransport(httpx.BaseTransport):
    def __init__(self, html: str) -> None:
        self._html = html

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == _PUBLICATION_URL:
            return httpx.Response(200, text=self._html)
        return httpx.Response(404)


class TestGovUkCatalogueClient:  # noqa: D101
    def _make_client(self, html: str) -> GovUkCatalogueClient:
        return GovUkCatalogueClient(client=httpx.Client(transport=_MockTransport(html)))

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

        client = GovUkCatalogueClient(client=httpx.Client(transport=_ErrorTransport()))

        # Act / Assert
        try:
            client.list_releases()
            pytest.fail("expected HTTPStatusError")
        except httpx.HTTPStatusError:
            pass

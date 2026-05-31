"""Data Release Models."""

from abc import ABC, abstractmethod
from typing import Annotated, Literal

from pydantic import BaseModel, Field

type MonitorType = Literal["fixed", "mobile"]


class _Release(BaseModel, ABC):
    url: str

    def __hash__(self) -> int:
        return hash(self.url)

    @property
    @abstractmethod
    def filename(self) -> str: ...


class MonthlyRelease(_Release):
    """A monthly data release containing readings for a single monitor type.

    Attributes:
        kind: Discriminator field, always "monthly".
        year: The calendar year of the release (e.g. 2026).
        month: The calendar month of the release as an integer (1-12).
        monitor_type: Whether the release covers fixed or mobile monitors.
        url: The direct download URL for the CSV file.

    """

    kind: Literal["monthly"] = "monthly"
    year: int
    month: int
    monitor_type: MonitorType

    @property
    def filename(self) -> str:
        """Return a canonical filename for this release."""
        return f"{self.year}_{self.month:02d}_{self.monitor_type}.csv"


class AnnualRelease(_Release):
    """An annual data release bundling all monitors for a full year as a ZIP.

    Attributes:
        kind: Discriminator field, always "annual".
        year: The calendar year covered by the release.
        url: The direct download URL for the ZIP file.

    """

    kind: Literal["annual"] = "annual"
    year: int

    @property
    def filename(self) -> str:
        """Return a canonical filename for this release."""
        return f"{self.year}.zip"


type DataRelease = Annotated[
    MonthlyRelease | AnnualRelease,
    Field(discriminator="kind"),
]


class AnnualData(BaseModel):
    """A data release that has been downloaded to local storage."""

    year: int

    quarterly_fixed_data: QuarterlyData | None = None
    quarterly_mobile_data: QuarterlyData | None = None

    monthly_fixed_data: MonthlyDataFile | None = None
    monthly_mobile_data: MonthlyDataFile | None = None


class QuarterlyData(BaseModel):
    """A data release that has been downloaded to local storage."""

    q1: str | None
    q2: str | None
    q3: str | None
    q4: str | None


class MonthlyDataFile(BaseModel):
    """A data release that has been downloaded to local storage."""

    jan: str | None
    feb: str | None
    mar: str | None
    apr: str | None
    may: str | None
    jun: str | None
    jul: str | None
    aug: str | None
    sep: str | None
    oct: str | None
    nov: str | None
    dec: str | None

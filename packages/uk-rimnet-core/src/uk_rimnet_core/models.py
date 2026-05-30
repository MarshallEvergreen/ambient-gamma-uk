"""Data Release Models."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

type MonitorType = Literal["fixed", "mobile"]


class _Release(BaseModel):
    url: str

    def __hash__(self) -> int:
        return hash(self.url)


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


class AnnualRelease(_Release):
    """An annual data release bundling all monitors for a full year as a ZIP.

    Attributes:
        kind: Discriminator field, always "annual".
        year: The calendar year covered by the release.
        url: The direct download URL for the ZIP file.

    """

    kind: Literal["annual"] = "annual"
    year: int


type DataRelease = Annotated[
    MonthlyRelease | AnnualRelease,
    Field(discriminator="kind"),
]

"""Data Release Models."""

from abc import ABC, abstractmethod
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

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


class QuarterlyData(BaseModel):
    """File paths for quarterly stats files.

    Attributes:
        q1: Path to the Q1 stats file, or None if absent.
        q2: Path to the Q2 stats file, or None if absent.
        q3: Path to the Q3 stats file, or None if absent.
        q4: Path to the Q4 stats file, or None if absent.

    """

    q1: str | None = None
    q2: str | None = None
    q3: str | None = None
    q4: str | None = None


class MonthlyDataFile(BaseModel):
    """File paths for monthly streaming CSVs.

    Attributes:
        jan: Path to the January CSV, or None if absent.
        feb: Path to the February CSV, or None if absent.
        mar: Path to the March CSV, or None if absent.
        apr: Path to the April CSV, or None if absent.
        may: Path to the May CSV, or None if absent.
        jun: Path to the June CSV, or None if absent.
        jul: Path to the July CSV, or None if absent.
        aug: Path to the August CSV, or None if absent.
        sep: Path to the September CSV, or None if absent.
        oct: Path to the October CSV, or None if absent.
        nov: Path to the November CSV, or None if absent.
        dec: Path to the December CSV, or None if absent.

    """

    jan: str | None = None
    feb: str | None = None
    mar: str | None = None
    apr: str | None = None
    may: str | None = None
    jun: str | None = None
    jul: str | None = None
    aug: str | None = None
    sep: str | None = None
    oct: str | None = None
    nov: str | None = None
    dec: str | None = None


class AnnualDataError(ValueError):
    """Raised when an annual year data model fails validation."""


class PreMobileYearData(BaseModel):
    """Annual data for years before 2016 when only fixed quarterly monitoring existed.

    Mobile monitoring was introduced in 2016; this era predates it.

    Attributes:
        kind: Discriminator field, always "pre_mobile".
        year: Calendar year, must be before 2016.
        fixed: Quarterly stats files for fixed monitors.

    """

    kind: Literal["pre_mobile"] = "pre_mobile"
    year: int
    fixed: QuarterlyData

    @field_validator("year")
    @classmethod
    def _validate_year(cls, v: int) -> int:
        if v >= 2016:  # noqa: PLR2004
            msg = f"PreMobileYearData requires a year before 2016; got {v}."
            raise AnnualDataError(msg)
        return v


class QuarterlyYearData(BaseModel):
    """Annual data for 2016-2021 when both fixed and mobile quarterly data existed.

    Attributes:
        kind: Discriminator field, always "quarterly".
        year: Calendar year, must be in the range 2016-2021.
        fixed: Quarterly stats files for fixed monitors.
        mobile: Quarterly stats files for mobile monitors.

    """

    kind: Literal["quarterly"] = "quarterly"
    year: int
    fixed: QuarterlyData
    mobile: QuarterlyData

    @field_validator("year")
    @classmethod
    def _validate_year(cls, v: int) -> int:
        if not 2016 <= v <= 2021:  # noqa: PLR2004
            msg = f"QuarterlyYearData requires a year between 2016 and 2021; got {v}."
            raise AnnualDataError(msg)
        return v


class TransitionYearData(BaseModel):
    """Annual data for 2022 when RREMS switched from quarterly to monthly mid-year.

    Q1-Q2 were published as quarterly stats; Q3-Q4 as monthly streaming CSVs.
    Quarterly fields must carry only Q1-Q2; monthly fields must carry only Jul-Dec.

    Attributes:
        kind: Discriminator field, always "transition".
        year: Always 2022.
        quarterly_fixed: Q1-Q2 quarterly stats for fixed monitors.
        quarterly_mobile: Q1-Q2 quarterly stats for mobile monitors.
        monthly_fixed: Q3-Q4 monthly streaming files for fixed monitors.
        monthly_mobile: Q3-Q4 monthly streaming files for mobile monitors.

    """

    kind: Literal["transition"] = "transition"
    year: Literal[2022] = 2022
    quarterly_fixed: QuarterlyData
    quarterly_mobile: QuarterlyData
    monthly_fixed: MonthlyDataFile
    monthly_mobile: MonthlyDataFile

    @model_validator(mode="after")
    def _validate_quarterly_is_h1_only(self) -> Self:
        for data, label in [
            (self.quarterly_fixed, "fixed"),
            (self.quarterly_mobile, "mobile"),
        ]:
            if data.q3 is not None or data.q4 is not None:
                msg = (
                    f"In 2022, Q3 and Q4 for {label} monitors were published "
                    "as monthly; quarterly data must only carry q1 and q2."
                )
                raise AnnualDataError(msg)
        return self

    @model_validator(mode="after")
    def _validate_monthly_is_h2_only(self) -> Self:
        for data, label in [
            (self.monthly_fixed, "fixed"),
            (self.monthly_mobile, "mobile"),
        ]:
            h1_present = (
                data.jan is not None
                or data.feb is not None
                or data.mar is not None
                or data.apr is not None
                or data.may is not None
                or data.jun is not None
            )
            if h1_present:
                msg = (
                    f"In 2022, Jan-Jun for {label} monitors were published "
                    "as quarterly; monthly data must only carry Jul-Dec."
                )
                raise AnnualDataError(msg)
        return self

    @model_validator(mode="after")
    def _validate_monthly_h2_is_complete(self) -> Self:
        for data, label in [
            (self.monthly_fixed, "fixed"),
            (self.monthly_mobile, "mobile"),
        ]:
            missing = [
                m
                for m, v in [
                    ("jul", data.jul),
                    ("aug", data.aug),
                    ("sep", data.sep),
                    ("oct", data.oct),
                    ("nov", data.nov),
                    ("dec", data.dec),
                ]
                if v is None
            ]
            if missing:
                months = ", ".join(missing)
                msg = (
                    f"In 2022, all H2 months must be present for {label} monitors; "
                    f"missing: {months}."
                )
                raise AnnualDataError(msg)
        return self


class MonthlyYearData(BaseModel):
    """Annual data for 2023 onwards when RREMS publishes monthly streaming CSVs.

    For the current calendar year, data is published progressively so fixed
    and mobile may be None or partially populated.

    Attributes:
        kind: Discriminator field, always "monthly".
        year: Calendar year, must be 2023 or later.
        fixed: Monthly streaming files for fixed monitors, or None if not yet
            downloaded.
        mobile: Monthly streaming files for mobile monitors, or None if not yet
            downloaded.

    """

    kind: Literal["monthly"] = "monthly"
    year: int
    fixed: MonthlyDataFile = MonthlyDataFile()
    mobile: MonthlyDataFile = MonthlyDataFile()

    @field_validator("year")
    @classmethod
    def _validate_year(cls, v: int) -> int:
        if v < 2023:  # noqa: PLR2004
            msg = f"MonthlyYearData requires a year of 2023 or later; got {v}."
            raise AnnualDataError(msg)
        return v


type AnnualYearData = Annotated[
    PreMobileYearData | QuarterlyYearData | TransitionYearData | MonthlyYearData,
    Field(discriminator="kind"),
]

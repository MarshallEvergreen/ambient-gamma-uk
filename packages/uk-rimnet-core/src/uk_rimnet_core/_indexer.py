"""Filename parsing and annual year data index building."""

from typing import TYPE_CHECKING

from uk_rimnet_core.models import (
    AnnualYearData,
    MonthlyDataFile,
    MonthlyRelease,
    MonthlyYearData,
    PreMobileYearData,
    QuarterlyData,
    QuarterlyYearData,
    TransitionYearData,
)

if TYPE_CHECKING:
    from uk_rimnet_core.models import DataRelease, MonitorType

_MONTH_FIELDS: dict[int, str] = {
    1: "jan",
    2: "feb",
    3: "mar",
    4: "apr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "aug",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dec",
}

_QUARTER_PATTERNS: dict[int, tuple[str, ...]] = {
    1: ("q1", "quarter-1", "quarter_1", "jan-mar"),
    2: (
        "q2",
        "quarter-2",
        "quarter_2",
        "apr-jun",
        "apr_jun",
        "ap-jun",
        "apr_to_june",
        "april-june",
    ),
    3: ("q3", "quarter-3", "quarter_3", "jul-sep", "july-sep", "july-september"),
    4: (
        "q4",
        "quarter-4",
        "quarter_4",
        "oct-dec",
        "oct_dec",
        "october-dec",
        "october-december",
    ),
}


def _stem(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _parse_quarter(stem: str) -> int | None:
    lower = stem.lower()
    for quarter, patterns in _QUARTER_PATTERNS.items():
        if any(p in lower for p in patterns):
            return quarter
    return None


def _parse_month(stem: str) -> int | None:
    lower = stem.lower()
    for month, abbr in _MONTH_FIELDS.items():
        if abbr in lower:
            return month
    return None


def _parse_monitor_type(stem: str) -> MonitorType | None:
    lower = stem.lower()
    if "mobile" in lower:
        return "mobile"
    if "fixed" in lower or "station" in lower:
        return "fixed"
    return None


def build_annual_year_data(
    release_paths: list[tuple[DataRelease, str]],
) -> list[AnnualYearData]:
    """Build one ``AnnualYearData`` per calendar year from release-path pairs.

    Args:
        release_paths: Pairs of ``(release, absolute_path)`` for every file on disk.
            The release carries year and, for monthly releases, month and monitor type.
            For annual releases the corresponding metadata is parsed from the filename.

    Returns:
        A list of ``AnnualYearData`` instances sorted by year, one per calendar year
        represented in ``release_paths``.

    """
    by_year: dict[int, list[tuple[DataRelease, str]]] = {}
    for release, path in release_paths:
        by_year.setdefault(release.year, []).append((release, path))
    return [_build_year(year, pairs) for year, pairs in sorted(by_year.items())]


def _build_year(year: int, pairs: list[tuple[DataRelease, str]]) -> AnnualYearData:
    if year >= 2023:  # noqa: PLR2004
        return _build_monthly_year(year, pairs)
    if year == 2022:  # noqa: PLR2004
        return _build_transition_year(pairs)
    if year >= 2016:  # noqa: PLR2004
        return _build_quarterly_year(year, pairs)
    return _build_pre_mobile_year(year, pairs)


def _build_pre_mobile_year(
    year: int,
    pairs: list[tuple[DataRelease, str]],
) -> PreMobileYearData:
    fixed: dict[str, str] = {}
    for _, path in pairs:
        quarter = _parse_quarter(_stem(path))
        if quarter is not None:
            fixed[f"q{quarter}"] = path
    return PreMobileYearData(year=year, fixed=QuarterlyData(**fixed))


def _build_quarterly_year(
    year: int,
    pairs: list[tuple[DataRelease, str]],
) -> QuarterlyYearData:
    fixed: dict[str, str] = {}
    mobile: dict[str, str] = {}
    for _, path in pairs:
        quarter = _parse_quarter(_stem(path))
        monitor_type = _parse_monitor_type(_stem(path))
        if quarter is None or monitor_type is None:
            continue
        target = fixed if monitor_type == "fixed" else mobile
        target[f"q{quarter}"] = path
    return QuarterlyYearData(
        year=year,
        fixed=QuarterlyData(**fixed),
        mobile=QuarterlyData(**mobile),
    )


def _build_transition_year(pairs: list[tuple[DataRelease, str]]) -> TransitionYearData:
    quarterly_fixed: dict[str, str] = {}
    quarterly_mobile: dict[str, str] = {}
    monthly_fixed: dict[str, str] = {}
    monthly_mobile: dict[str, str] = {}

    for release, path in pairs:
        if isinstance(release, MonthlyRelease):
            field = _MONTH_FIELDS[release.month]
            if release.monitor_type == "fixed":
                monthly_fixed[field] = path
            else:
                monthly_mobile[field] = path
        else:
            stem = _stem(path)
            monitor_type = _parse_monitor_type(stem)
            if monitor_type is None:
                continue
            quarter = _parse_quarter(stem)
            if quarter is not None:
                target = (
                    quarterly_fixed if monitor_type == "fixed" else quarterly_mobile
                )
                target[f"q{quarter}"] = path
            else:
                month = _parse_month(stem)
                if month is not None:
                    field = _MONTH_FIELDS[month]
                    monthly = (
                        monthly_fixed if monitor_type == "fixed" else monthly_mobile
                    )
                    monthly[field] = path

    return TransitionYearData(
        quarterly_fixed=QuarterlyData(**quarterly_fixed),
        quarterly_mobile=QuarterlyData(**quarterly_mobile),
        monthly_fixed=MonthlyDataFile(**monthly_fixed),
        monthly_mobile=MonthlyDataFile(**monthly_mobile),
    )


def _build_monthly_year(
    year: int,
    pairs: list[tuple[DataRelease, str]],
) -> MonthlyYearData:
    fixed_fields: dict[str, str] = {}
    mobile_fields: dict[str, str] = {}
    for release, path in pairs:
        if isinstance(release, MonthlyRelease):
            field = _MONTH_FIELDS[release.month]
            if release.monitor_type == "fixed":
                fixed_fields[field] = path
            else:
                mobile_fields[field] = path
        else:
            stem = _stem(path)
            monitor_type = _parse_monitor_type(stem)
            if monitor_type is None:
                continue
            month = _parse_month(stem)
            if month is not None:
                field = _MONTH_FIELDS[month]
                if monitor_type == "fixed":
                    fixed_fields[field] = path
                else:
                    mobile_fields[field] = path
    return MonthlyYearData(
        year=year,
        fixed=MonthlyDataFile(**fixed_fields),
        mobile=MonthlyDataFile(**mobile_fields),
    )

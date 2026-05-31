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
    from fsspec import AbstractFileSystem

    from uk_rimnet_core.models import DataRelease, MonitorType

_PROGRESS_COLUMNS = (
    SpinnerColumn(),
    TextColumn("[bold blue]{task.description}", justify="left"),
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
)

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


def _stem(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _build_annual_year_data(
    release_paths: list[tuple[DataRelease, str]],
) -> list[AnnualYearData]:
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

        return _build_annual_year_data(release_paths)

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

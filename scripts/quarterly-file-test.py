"""Test script to check quarterly Excel file parsing."""  # noqa: INP001

from pathlib import Path

from uk_rimnet_core._readers import read_monthly_csv, read_quarterly_stats_file

if __name__ == "__main__":
    path_xlsx = Path(
        "/Users/abie/Dev/uk-rimnet/bin/2017/rimnet-2017-q1-jan-mar-fixed-monitors.xlsx",
    )
    path_csv = Path(
        "/Users/abie/Dev/uk-rimnet/bin/2019/rimnet-mobile-monitors-summary-oct-dec-2019.csv",
    )
    path_monthly_no_location = Path(
        "/Users/abie/Dev/uk-rimnet/bin/2024/sep-2024-ambient-gamma-dose-rates-fixed-rrems-monitors.csv",
    )
    quarterly_xlsx = read_quarterly_stats_file(path_xlsx, 17, 1, "fixed")
    quarterly_csv = read_quarterly_stats_file(path_csv, 17, 1, "fixed")

    monthly_no_location = read_monthly_csv(path_monthly_no_location, 17, 1, "fixed")
    monthly_no_location = read_monthly_csv(path_monthly_no_location, 17, 1, "fixed")

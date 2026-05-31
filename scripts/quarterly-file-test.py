"""Test script to check quarterly Excel file parsing."""  # noqa: INP001

from pathlib import Path

from uk_rimnet_core._readers import read_quarterly_stats_file

if __name__ == "__main__":
    path_xlsx = Path(
        "/Users/abie/Dev/uk-rimnet/bin/2017/rimnet-2017-q1-jan-mar-fixed-monitors.xlsx",
    )
    path_csv = Path(
        "/Users/abie/Dev/uk-rimnet/bin/2019/rimnet-mobile-monitors-summary-oct-dec-2019.csv",
    )
    read_quarterly_stats_file(path_csv, 17, 1, "fixed")

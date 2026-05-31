import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
def _():

    import polars as pl

    return (pl,)


@app.cell
def _(pl):
    _csv_path = "/Users/abie/Dev/uk-rimnet/bin/2010_ambient_gamma_radiation_dose_rates_across_the_UK/Q1 2010.csv"
    Q1_2010_df = pl.read_csv(_csv_path, encoding="utf8-lossy")
    return (Q1_2010_df,)


@app.cell
def _(Q1_2010_df):
    Q1_2010_df


@app.cell
def _(pl):
    _csv_path = "/Users/abie/Dev/uk-rimnet/bin/2012_ambient_gamma_radiation_dose_rates_across_the_UK/Quarter_1_2012_ambient_gamma_radiation_dose_rates_across_the_UK.csv"
    Q1_2012_df = pl.read_csv(
        _csv_path,
        skip_rows=6,  # skip the 6 metadata rows before the header
        skip_rows_after_header=1,  # skip the blank row between header and data
        encoding="utf8-lossy",
    )
    Q1_2012_df


@app.cell
def _(pl):
    _csv_path = "/Users/abie/Dev/uk-rimnet/bin/2016-ambient-gamma-radiation-dose-rates-across-the-uk/rimnet-2016-q1-jan-mar-mobile-monitors.xlsx"

    Q1_2014_df = pl.read_excel(
        _csv_path,
        sheet_name="Jan 2014 - Mar 2014",
        read_options={"header_row": 6, "skip_rows": 1},
    ).filter(pl.col("Location").is_not_null())
    Q1_2014_df


if __name__ == "__main__":
    app.run()

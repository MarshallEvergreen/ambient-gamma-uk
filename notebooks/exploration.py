import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
async def _():

    import polars as pl
    from loguru import logger
    from uk_rimnet_core import LocationRegistry
    from uk_rimnet_core.client import GovUkRIMNETRRMESClient

    client = GovUkRIMNETRRMESClient()

    destination = "/Users/abie/Dev/uk-rimnet/bin"

    releases = await client.async_.download_releases(
        destination=destination,
    )
    release_2025 = releases[-2]
    release_2026 = releases[-1]
    return pl, release_2025, release_2026


@app.cell
def _(release_2026):
    release_2026.fixed.ordered_monthly_file_names
    return


@app.cell
def _(pl, release_2025, release_2026):
    df = None
    for f in [*release_2025.fixed.ordered_monthly_file_names, 
              *release_2025.mobile.ordered_monthly_file_names,
              *release_2026.fixed.ordered_monthly_file_names,
              *release_2026.mobile.ordered_monthly_file_names,
             ]:
        _df = pl.read_csv(f, encoding="utf8-lossy", columns=["latitude", "longitude", "monitor_location"]).unique(subset=["monitor_location"], keep="last")
        if df is None:
            df = _df
        else:
            df = df.update(_df, on="monitor_location", how="full")

    df
    return (df,)


@app.cell
def _(df):
    import geopandas as gpd

    gdf = gpd.GeoDataFrame(
        df.to_pandas(),
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"], crs="EPSG:4326"),
        crs="EPSG:4326"
    )

    gdf.plot(markersize=5, figsize=(10, 8))
    return


@app.cell
def _(release_2025):
    release_2025.mobile.ordered_monthly_file_names
    return


@app.cell
def _(pl):
    _csv_path = "/Users/abie/Dev/uk-rimnet/bin/2010_ambient_gamma_radiation_dose_rates_across_the_UK/Q1 2010.csv"
    Q1_2010_df = pl.read_csv(_csv_path, encoding="utf8-lossy")
    return (Q1_2010_df,)


@app.cell
def _(Q1_2010_df):
    Q1_2010_df
    return


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
    return


@app.cell
def _(pl):
    _csv_path = "/Users/abie/Dev/uk-rimnet/bin/2016-ambient-gamma-radiation-dose-rates-across-the-uk/rimnet-2016-q1-jan-mar-mobile-monitors.xlsx"

    Q1_2014_df = pl.read_excel(
        _csv_path,
        sheet_name="Jan 2014 - Mar 2014",
        read_options={"header_row": 6, "skip_rows": 1},
    ).filter(pl.col("Location").is_not_null())
    Q1_2014_df
    return


if __name__ == "__main__":
    app.run()

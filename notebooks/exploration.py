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
    df = pl.concat([
        pl.read_csv(
            f,
            encoding="utf8-lossy",
            columns=["latitude", "longitude", "monitor_location"],
        ).unique()
        for f in [
            *release_2025.fixed.ordered_monthly_file_names,
            *release_2025.mobile.ordered_monthly_file_names,
            *release_2026.fixed.ordered_monthly_file_names,
            *release_2026.mobile.ordered_monthly_file_names,
        ]
    ]).unique()
    df
    return (df,)


@app.cell
def _(df):
    import geopandas as gpd
    import contextily as ctx

    gdf = gpd.GeoDataFrame(
        df.to_pandas(),
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"], crs="EPSG:4326"),
        crs="EPSG:4326",
    )

    import folium

    m = folium.Map(
        location=[54.5, -2],
        zoom_start=6,
        tiles="CartoDB positron",
    )

    # Optical/satellite basemap
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite",
    ).add_to(m)

    for _, row in gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3,
            color="blue",
            fill=True,
            tooltip=row["monitor_location"],  # shows on hover
            popup=row["monitor_location"],    # shows on click
        ).add_to(m)
    m
    return


@app.cell
def _(release_2025):
    release_2025.mobile.ordered_monthly_file_names
    return


@app.cell
def _():
    from uk_rimnet_core._readers import read_quarterly_stats_file, read_monthly_csv
    from pathlib import Path

    _csv_path = Path("/Users/abie/Dev/uk-rimnet/bin/2025_01_fixed.csv")
    Q1_2010_df = read_monthly_csv(_csv_path, 2010, 1, "fixed")
    Q1_2010_df
    return


if __name__ == "__main__":
    app.run()

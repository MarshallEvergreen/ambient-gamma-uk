import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
async def _():
    from uk_rimnet_core import LocationRegistry
    from uk_rimnet_core.client import Client

    client = Client()

    destination = "/Users/abie/Dev/uk-rimnet/bin"

    releases = await client.async_.download_releases(
        destination=destination,
    )
    releases
    return LocationRegistry, releases


@app.cell
def _(LocationRegistry, releases):
    registry = LocationRegistry()
    registry_data = registry.build_from_releases(releases)
    registry_data
    return (registry_data,)


@app.cell
def _():
    import polars as pl
    from uk_rimnet_core._process import process_single_release

    return pl, process_single_release


@app.cell
def _(pl, process_single_release, registry_data, releases):
    df = pl.concat(
        [process_single_release(releases[i]) for i in range(5 + 1)], how="diagonal"
    )

    df.drop("latitude", "longitude").join(
        registry_data,
        on="location_name",
        how="left",
    )
    return


if __name__ == "__main__":
    app.run()

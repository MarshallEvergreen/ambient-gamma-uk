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
    return (registry,)


@app.cell
def _():
    import polars as pl
    from uk_rimnet_core._process import process_single_release

    return pl, process_single_release


@app.cell
def _(pl, process_single_release, registry, releases):
    df = pl.concat(
        [process_single_release(releases[i], registry) for i in range(12 + 1)],
        how="diagonal",
    )
    df
    return


if __name__ == "__main__":
    app.run()

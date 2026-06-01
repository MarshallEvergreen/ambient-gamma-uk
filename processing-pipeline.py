import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return


@app.cell
async def _():
    from uk_rimnet_core.client import Client
    from uk_rimnet_core import LocationRegistry

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
    return


@app.cell
def _(releases):
    from uk_rimnet_core._readers import read_quarterly_stats_file

    y2010 = releases[0]
    y2010
    # quarterly_xlsx = read_quarterly_stats_file(path_xlsx, 17, 1, "fixed")

    return


if __name__ == "__main__":
    app.run()

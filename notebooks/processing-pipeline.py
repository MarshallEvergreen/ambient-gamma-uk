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
        [process_single_release(r, registry) for r in releases],
        how="diagonal",
    )
    df
    return (df,)


@app.cell
def _(df):
    import marimo as mo

    year_options = {str(y): y for y in sorted(df["year"].unique().to_list())}
    year_dropdown = mo.ui.dropdown(
        options=year_options,
        value=str(max(df["year"].to_list())),
        label="Year",
    )
    quarter_dropdown = mo.ui.dropdown(
        options={"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4},
        value="Q1",
        label="Quarter",
    )
    mo.hstack([year_dropdown, quarter_dropdown], justify="start")
    return mo, quarter_dropdown, year_dropdown


@app.cell
def _(df, mo, pl, quarter_dropdown, year_dropdown):
    import colorsys
    import folium  # type: ignore[import]

    _OUTLINE: dict[str, str] = {"fixed": "#111111", "mobile": "#1a5fa8"}
    _RADIUS_MIN = 5.0
    _RADIUS_MAX = 22.0
    _ELEVATED_THRESHOLD = 1.0
    _ELEVATED_MAX = 1.15

    def _hsl_hex(h: float, s: float, l: float) -> str:  # noqa: E741
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    def _fill_colour(ratio: float) -> str:
        t = max(0.0, min(1.0, (ratio - _ELEVATED_THRESHOLD) / (_ELEVATED_MAX - _ELEVATED_THRESHOLD)))
        hue = (1.0 - t) * (120.0 / 360.0)
        lightness = 0.38 - t * 0.06
        return _hsl_hex(hue, 0.72, lightness)

    def _scale(value: float, lo: float, hi: float, out_lo: float, out_hi: float) -> float:
        if hi == lo:
            return (out_lo + out_hi) / 2
        t = max(0.0, min(1.0, (value - lo) / (hi - lo)))
        return out_lo + t * (out_hi - out_lo)

    _filtered = df.filter(
        (pl.col("year") == year_dropdown.value)
        & (pl.col("quarter") == quarter_dropdown.value)
        & pl.col("latitude").is_not_null()
        & pl.col("longitude").is_not_null()
    )

    if _filtered.is_empty():
        _output = mo.md(
            f"_No data for {year_dropdown.value} Q{quarter_dropdown.value}._"
        )
    else:
        _std_series = _filtered["std_dev"].drop_nulls()
        _std_lo = float(_std_series.min() or 0.0)
        _std_hi = float(_std_series.max() or 1.0)

        _m = folium.Map(location=[54.5, -2.5], zoom_start=6, tiles="cartodbpositron")

        for _row in _filtered.iter_rows(named=True):
            _mean: float | None = _row["mean"]
            _std: float | None = _row["std_dev"]
            _normal: float | None = _row["site_normal"]

            _radius = _scale(_std or _std_lo, _std_lo, _std_hi, _RADIUS_MIN, _RADIUS_MAX)

            if _mean is not None and _normal is not None and _normal > 0:
                _ratio = _mean / _normal
            else:
                _ratio = 1.0
            _fc = _fill_colour(_ratio)
            _outline = _OUTLINE.get(_row["monitor_type"], "#555555")

            _mean_str = f"{_mean:.3f}" if _mean is not None else "N/A"
            _std_str = f"{_std:.3f}" if _std is not None else "N/A"
            _normal_str = f"{_normal:.3f}" if _normal is not None else "N/A"
            _ratio_str = f"{_ratio:.2f}×" if _ratio != 1.0 else "1.00× (normal)"
            folium.CircleMarker(
                location=[_row["latitude"], _row["longitude"]],
                radius=_radius,
                color=_outline,
                weight=1.5,
                fill=True,
                fill_color=_fc,
                fill_opacity=0.85,
                tooltip=_row["location_name"],
                popup=folium.Popup(
                    f"<b>{_row['location_name']}</b><br>"
                    f"Type: {_row['monitor_type']}<br>"
                    f"Mean: {_mean_str} µGy/h<br>"
                    f"Site normal: {_normal_str} µGy/h<br>"
                    f"Ratio: {_ratio_str}<br>"
                    f"Std dev: {_std_str} µGy/h",
                    max_width=240,
                ),
            ).add_to(_m)

        _legend = """
        <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
                    background:white;padding:10px 14px;border-radius:6px;
                    border:1px solid #bbb;font-size:13px;line-height:1.8;">
            <b>Outline = monitor type</b><br>
            <svg width="16" height="16" style="vertical-align:middle">
              <circle cx="8" cy="8" r="6" fill="none" stroke="#111" stroke-width="2"/>
            </svg>&nbsp;Fixed<br>
            <svg width="16" height="16" style="vertical-align:middle">
              <circle cx="8" cy="8" r="6" fill="none" stroke="#1a5fa8" stroke-width="2"/>
            </svg>&nbsp;Mobile<br>
            <hr style="margin:6px 0;">
            <b>Fill = vs site normal</b><br>
            <svg width="16" height="16" style="vertical-align:middle">
              <circle cx="8" cy="8" r="6" fill="#2e7d32"/>
            </svg>&nbsp;Normal (&le;1.0&times;)<br>
            <svg width="16" height="16" style="vertical-align:middle">
              <circle cx="8" cy="8" r="6" fill="#f5a623"/>
            </svg>&nbsp;Elevated (~1.08&times;)<br>
            <svg width="16" height="16" style="vertical-align:middle">
              <circle cx="8" cy="8" r="6" fill="#c0392b"/>
            </svg>&nbsp;High (&ge;1.15&times;)<br>
            <hr style="margin:6px 0;">
            <b>Size</b> = std dev
        </div>
        """
        _m.get_root().html.add_child(folium.Element(_legend))  # ty: ignore[unresolved-attribute]

        _output = mo.Html(_m._repr_html_())
    _output
    return


if __name__ == "__main__":
    app.run()

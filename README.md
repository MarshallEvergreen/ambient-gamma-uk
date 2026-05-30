# uk-rimnet

A Python library for accessing and visualising UK ambient gamma radiation monitoring data.

## Background

The UK government publishes hourly gamma radiation dose rate measurements from a network of fixed and mobile monitors across the country. This data was historically collected by **RIMNET** (Radioactive Incident Monitoring Network), operated by the Met Office from 1989 until 2022. RIMNET was subsequently replaced by **RREMS** (Radiological Response and Emergency Management System), managed by the Department for Energy Security and Net Zero.

Data is published monthly as CSV files on GOV.UK under the [Ambient gamma radiation dose rates across the UK](https://www.gov.uk/government/publications/ambient-gamma-radiation-dose-rates-across-the-uk) publication. Historical data is available back to 2010. All data is released under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

## The Problem

There is no official API for this data. Each monthly release is a large CSV file (20–35 MB) hosted at an unpredictable URL, discoverable only by scraping the GOV.UK publication index page. Working with this data requires manually navigating the publication page, downloading files, and parsing them — a poor experience for anyone wanting to do analysis or build on top of it.

## This Project

`uk-rimnet` provides a clean Python API for:

- **Discovering** available data releases by scraping the GOV.UK publication index
- **Downloading** monthly CSV data for fixed and mobile monitor networks
- **Parsing** readings into well-typed, easy-to-use data structures
- **Plotting** monitor readings on a map of the UK

## Project Structure

This is a [UV workspace](https://docs.astral.sh/uv/concepts/workspaces/) containing the following packages:

| Package | Description |
|---|---|
| `packages/uk-rimnet-core` | Core library: data discovery, download, and parsing |

## License

Data sourced from GOV.UK is available under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

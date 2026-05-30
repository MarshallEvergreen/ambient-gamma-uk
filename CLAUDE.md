# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Python library for accessing and visualising UK ambient gamma radiation dose rate data published by RREMS (the successor to RIMNET) on GOV.UK. Data is published as monthly CSV files — there is no official API. See README.md for full background.

## Engineering standards

Write code as a principal engineer. This is not a scripting project. The team's primary languages are C++ and Rust, and those principles carry directly into Python:

- **Fully typed, always.** Every function signature has explicit parameter and return type annotations. No `Any` unless genuinely unavoidable, and never as a shortcut.
- **Clean architecture over convenience.** Separate concerns — I/O, parsing, domain logic, and presentation belong in distinct layers. Avoid god objects and functions that do too many things.
- **Extensibility by design.** Prefer abstractions (protocols, abstract base classes) at boundaries so that implementations can be swapped. Design for the caller, not the implementation.
- **Testability is a first-class constraint.** If code is hard to test, that is a design smell. Inject dependencies; avoid hidden global state.

## Testing philosophy

Test the public API of the system, not its implementation details.

- Tests should assert *observable behaviour* — what the system produces given inputs, not how it produces it.
- Internal refactors must not require test changes. If a test breaks because an internal function was renamed or restructured, the test was written at the wrong level.
- Use appropriate test doubles (fakes, stubs) at system boundaries (network, filesystem) to isolate behaviour — but keep these at the edges, not threaded through unit internals.
- Prefer fewer, well-constructed behaviour tests over many fine-grained implementation tests.
- **Patching is explicitly forbidden.** `unittest.mock.patch` and monkey-patching bypass the public API and couple tests to internal import paths and implementation details. If something needs to be substituted in a test, the design should accommodate that through dependency injection or a protocol boundary — not by reaching inside the module and swapping internals at runtime.

## Workspace structure

UV workspace. The root `pyproject.toml` holds all shared tooling config (ruff, ty, poe tasks, dev dependencies). Individual packages live under `packages/` and have their own `pyproject.toml` for package metadata only.

| Package | Import name |
|---|---|
| `packages/uk-rimnet-core` | `uk_rimnet_core` |

## Commands

All commands run via poe from the workspace root:

```bash
uv run poe fmt        # format with ruff
uv run poe lint       # lint with ruff (auto-fix)
uv run poe check      # type check with basedpyright
uv run poe test       # run pytest
uv run poe all        # fmt → lint → check → test

uv run poe ci:fmt     # format check (no writes, for CI)
uv run poe ci:lint    # lint check (no fixes, for CI)
uv run poe sync       # uv sync --all-packages --all-groups
```

## Tooling rules

- **ruff**: `select = ["ALL"]` — every rule is enabled. Add `ignore` entries in `[tool.ruff.lint]` when rules conflict or are intentionally not applicable.
- **ty**: `all = "error"` — all diagnostics are errors.
- **ruff + ty split**: ruff enforces annotation *presence* (ANN rules); ty validates annotation *correctness*.

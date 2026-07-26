# Agents

This is a uv workspace monorepo for Open WebUI plugins.
Each plugin lives under `plugins/*/` and is its own `uv`-managed package.

## Project-level config

- `pyproject.toml` — workspace root, dev dependencies, tool config (ruff, pytest)
- `conftest.py` — shared pytest fixtures and markers (`integration`, `unit`)
- `tests/` — shared/integration tests


## General conventions

- Python 3.11+, target-version `py311`
- Ruff linting with `E`, `F`, `I`, `N`, `W` (line-length 100, ignore `E501`)
- pytest with `asyncio_mode = auto`
- `integration` marker requires a running Open WebUI container
- `unit` marker does not require a container

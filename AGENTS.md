# Agents

This is a uv workspace monorepo for Open WebUI plugins.
Each plugin lives under `plugins/*/` and is its own `uv`-managed package.

## Project-level config

- `pyproject.toml` — workspace root, dev dependencies, tool config (ruff, pytest)
- `conftest.py` — shared pytest fixtures and markers (`integration`, `unit`)
- `tests/` — shared/integration tests

## Development Guidelines
- [plugin_development](docs/plugin_development.md)
- [valves_conventions](docs/valves_conventions.md)
- [plugin_qa](docs/plugin_qa.md)
- [plugin_readme_template](docs/plugin_readme_template.md)
- [plugin_meta_template](docs/plugin_meta_template)
- [release](docs/release.md)


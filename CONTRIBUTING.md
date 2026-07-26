## Development
Each plugin lives under `plugins/<name>/`
Plugins are collected into a monorepo to simplify sharing of common logic.

### Quick Start
```bash
git clone <repo-url>
cd owui-plugins
uv sync --dev

# Install git hooks (lint/format on commit, tests on push)
uv run pre-commit install --hook-type pre-push

# Install hooks after a fresh clone:
uv run pre-commit install --hook-type pre-push
```

Install `docker` to run integration tests


### Linting and formatting
```bash
# Lint all plugins
uv run ruff check plugins/

# Auto-fix issues
uv run ruff check --fix plugins/

# Validate plugin metadata
uv run python scripts/validate_plugin.py
```

### Quality control hooks
Pre-commit hooks are managed via [pre-commit](https://pre-commit.com) and run automatically:

| Hook | Trigger | What it does |
|------|---------|-------------|
| `ruff --fix` | `git commit` | Auto-fixes lint issues (imports, unused code, whitespace) |
| `ruff-format` | `git commit` | Auto-formats code to consistent style |
| `run_tests_for_changes.py` | `git push` | Runs `pytest -m "not integration"` for **changed plugins only** — if core files (`conftest.py`, `pyproject.toml`, `tests/`) are touched, all unit tests run |

### Automated testing (CI or local)
Integration tests run against a real Open WebUI container using `docker compose`.
```bash
# Integration testing

uv sync --dev && \
uv run pytest plugins/optimized-search/tests -v
# This starts a open-webui container, runs the tests, then tears it down.
```

```bash
# Unit testing

uv run pytest -m "not integration" -v
# Skips all `@pytest.mark.integration` tests, 
# so no Docker container is started.

uv run pytest -m unit -v
# To run only explicitly-marked unit tests:
```


### Manual Testing (iterate without restarting)
```bash
docker compose -f tests/docker-compose.yml up -d && \
OWUI_URL=http://localhost:3000 uv run pytest plugins/optimized-search/tests -v && \
docker compose -f tests/docker-compose.yml down -v
```

Set `OWUI_URL` to skip container lifecycle and connect to a running instance.


### Add a new plugin test suite
Copy the `plugins/optimized-search/tests/` directory as a template. Each plugin's `tests/conftest.py` provides the `owui_client` fixture — see `tests/owui_client.py` for the shared API client.
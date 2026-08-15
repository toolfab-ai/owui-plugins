## Quick Start
```bash
git clone <repo-url>
cd owui-plugins
uv sync --dev

# Install git hooks (lint/format on commit, tests on push)
uv run pre-commit install --hook-type pre-push
```

Install `docker` to run integration tests.

## Workspace Overview
This project is a `uv` workspace monorepo. Each plugin is located in `plugins/*/` and managed as an individual package.

## Plugin Development
See the [Plugin Development Guide](docs/plugin_development.md) for architecture, coding standards, and compilation mechanics.

## Quality Assurance
All plugins must meet the following mandatory requirements:
- **Unit & Integration Tests**: Every plugin must include both unit tests (logic) and integration tests (container-gated).
- **Manual Verification**: Features must be manually verified in the live Open WebUI environment.
- **Hook Compliance**: Linting and formatting must pass all pre-commit and push checks.

For detailed guides, credentials, and infrastructure details, see the [Plugin QA Guide](docs/plugin_qa.md).

## Releasing
Only project maintainers are eligible to trigger official plugin releases. The release process is fully automated via GitHub Actions and triggered by specific Git tags. For more details, see the [Release Guide](docs/release.md).

## Quick Commands
```bash
# Lint and format
uv run ruff check plugins/
uv run ruff format plugins/

# Run tests
uv run pytest -m unit         # Fast (no Docker)
uv run pytest -m integration  # Full (requires Docker)

# Manual UI testing environment
uv run python -m scripts.bootstrap_test_env
```

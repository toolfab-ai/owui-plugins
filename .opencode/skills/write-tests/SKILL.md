---
name: write-tests
description: Guides agents on writing unit and integration tests for Open WebUI plugins, using optimized-search as the reference implementation.
---

# Write Tests for Open WebUI Plugins

This skill provides patterns, infrastructure, and conventions for writing tests across this monorepo. The reference implementation is `plugins/optimized-search/`, which has thorough unit and integration test coverage.

## Table of Contents

- [Test Infrastructure](./references/test-infrastructure.md) — conftest, fixtures, plugin loader, OWUI client
- [Unit Testing](./references/unit-testing.md) — pure-logic tests with inline plugin loading
- [Integration Testing](./references/integration-testing.md) — container-based tests via OwuiClient
- [Best Practices](./references/best-practices.md) — conventions, markers, naming, and tips

## Core Principles

- **Two tiers of tests**: Unit tests (no container, pure logic) and integration tests (require running Open WebUI via docker-compose).
- **Plugin loading**: Use `tests/_plugin_loader.load_plugin()` to dynamically import hyphen-named plugin modules — standard `import` won't work because filenames use hyphens (e.g. `optimized-search.py`).
- **`conftest.py` at repo root**: Provides the `owui_url` and `owui_client` fixtures used by all integration tests across all plugins.
- **Markers**: `@pytest.mark.integration` for container-required tests; unit tests are the default and do not need a marker.
- **Test discovery**: Configured in `pyproject.toml` — `testpaths = ["tests", "plugins"]`, so plugin-level `tests/` dirs are discovered automatically.

# Open WebUI Plugin QA Guide

This guide covers the testing infrastructure, patterns, and workflows for developing and verifying Open WebUI plugins in this monorepo.

## Testing Strategy

Testing is organized into three distinct routes depending on your goal:

| Route | Type | Container | Speed | Trigger |
|-------|------|-----------|-------|---------|
| **Route 1** | Unit | No | Fast | `git push`, Local |
| **Route 2** | Integration | Yes | Slow | Local, CI |
| **Route 3** | Manual | Yes | - | Manual |

---

## Route 1: Unit Testing (Pure Logic)

Unit tests cover pure-logic methods (heuristics, parsing, SSRF protection) that do not require a running Open WebUI container.

### 1. File Structure
Place unit tests in `plugins/<plugin-name>/tests/test_<feature>.py`.

### 2. Loading the Plugin
Because plugin files often contain hyphens (which are invalid in Python `import` statements), use the shared `load_plugin` helper:

```python
from tests._plugin_loader import load_plugin

# Dynamically load the plugin module by its directory name
mod = load_plugin("my-plugin-folder")
Tools = mod.Tools
```

### 3. Basic Pattern
```python
import pytest

@pytest.mark.unit
class TestLogic:
    def setup_method(self) -> None:
        # Each test gets a fresh instance
        self.tools = Tools()

    def test_processing(self) -> None:
        result = self.tools.process("input")
        assert result == "expected"
```

### 4. Running Unit Tests
```bash
# All unit tests
uv run pytest -m unit

# Specific plugin tests
uv run pytest plugins/my-plugin/tests/
```

---

## Route 2: Integration Testing (Container-Gated)

Integration tests verify that the plugin can be uploaded to Open WebUI, and that its valves and specifications are correctly registered.

### 1. Requirements
Integration tests require **Docker** to be running. The test runner automatically handles starting the container via `docker-compose`.

### 2. Marking
Every integration test class or method **must** be marked with `@pytest.mark.integration`.

### 3. Standard Test Class Pattern
```python
import pytest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
PLUGIN_SOURCE = (PLUGIN_DIR / "plugin.py").read_text("utf-8")
FUNCTION_ID = "my_plugin_id"

@pytest.mark.integration
class TestMyPlugin:
    async def test_upload(self, owui_client) -> None:
        """Verify the plugin can be successfully uploaded."""
        # owui_client is a global fixture that handles auth automatically
        resp = await owui_client.create_function(
            function_id=FUNCTION_ID,
            name="My Plugin",
            content=PLUGIN_SOURCE,
        )
        assert resp["id"] == FUNCTION_ID

    async def test_valves_spec(self, owui_client) -> None:
        """Verify valve properties are correctly registered."""
        spec = await owui_client.get_function_valves_spec(FUNCTION_ID)
        assert "MY_SETTING" in spec["properties"]
```

### 4. Running Integration Tests
```bash
# All integration tests (starts container if needed)
uv run pytest -m integration -v

# Skip integration tests
uv run pytest -m "not integration"
```

---

## Route 3: Manual Testing (UI Iteration)

Use this route to prepare a live environment for manual testing in the browser.

### 1. Setup the Environment
This script starts the container, creates test users, and installs all plugins. It leaves the container running until you manually shut it down.
```bash
uv run python -m scripts.bootstrap_test_env
```

### 2. Test Credentials
| User | Email | Password | Role |
|------|-------|----------|------|
| Admin | `admin@test.com` | `testpassword123` | Admin |
| User 1 | `user1@test.com` | `testpassword123` | User |

### 3. Teardown
```bash
docker compose -f tests/docker-compose.yml down -v
```

---

## CI/CD & Automation

Quality control is enforced via [pre-commit](https://pre-commit.com) hooks:

| Hook | Trigger | Description |
|------|---------|-------------|
| `ruff --fix` | `git commit` | Auto-fixes lint issues and sorts imports. |
| `ruff-format` | `git commit` | Enforces consistent code style. |
| `run_tests_for_changes.py` | `git push` | Runs unit tests for **changed plugins only**. If core files (`conftest.py`, `pyproject.toml`) are modified, all unit tests run. |

To install the hooks locally:
```bash
uv run pre-commit install --hook-type pre-push
```

---

## Best Practices

### Naming Conventions
- Unit test files: `test_<name>.py` (e.g., `test_search.py`)
- Integration test files: `test_<name>_integration.py` (e.g., `test_search_integration.py`)
- Test classes: `Test<Feature>` (e.g., `TestRecencyDetection`)
- Test methods: `test_<behavior>` (e.g., `test_year_2025_detected`)

### Assertions
- Prefer `is True` / `is False` for booleans: `assert needs is True`.
- Use class-level constants for long test strings (e.g., `LONG_SNIPPET = "..."`).

### Mocking Dependencies
If your plugin depends on external Open WebUI modules (like `open_webui.utils.chat`), mock them in your unit tests:

```python
import sys
from unittest.mock import MagicMock

sys.modules["open_webui"] = MagicMock()
sys.modules["open_webui.utils"] = MagicMock()
```

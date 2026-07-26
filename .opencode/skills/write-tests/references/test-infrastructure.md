# Test Infrastructure

## Plugin Loader (`tests/_plugin_loader.py`)

Plugin source files use hyphens in their names (e.g. `optimized-search.py`), making them non-importable via `import optimized-search`. The `load_plugin` helper uses `importlib` to load them dynamically:

```python
import importlib.util
from pathlib import Path


def load_plugin(plugin_name: str):
    plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
    plugin_file = plugins_dir / plugin_name / f"{plugin_name}.py"
    mod_name = plugin_name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(mod_name, plugin_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

Usage in a unit test:

```python
from tests._plugin_loader import load_plugin

mod = load_plugin("optimized-search")
Tools = mod.Tools  # Access the plugin's Tools class
```

## OwuiClient (`tests/owui_client.py`)

A thin async HTTP client wrapping the Open WebUI REST API. Used by integration tests to create/list/update tools and manage valves.

Key methods:
- `signup(email, password, name)` — create + authenticate admin user
- `signin(email, password)` — re-authenticate
- `create_tool(tool_id, name, content, description)` — upload a plugin
- `get_tools()` — list installed tools
- `get_tool_by_id(tool_id)` — fetch tool specs
- `get_tool_valves_spec(tool_id)` — fetch valve schema
- `update_tool_valves(tool_id, valves)` — update admin valves
- `delete_tool(tool_id)` — remove a tool

## conftest.py (`conftest.py` at repo root)

Session-level fixtures shared across all plugins:

- **`owui_url`** (session scope): Starts/connects to Open WebUI via docker-compose (`tests/docker-compose.yml`), waits for readiness (up to 120s), yields the URL, and tears down the container. Set `OWUI_URL` env var to skip container lifecycle for manual testing.
- **`owui_client`** (function scope): Wraps `owui_url` in an `OwuiClient`, performs signup/signin, and yields the authenticated client.

```python
@pytest.fixture(scope="session")
def owui_url() -> str: ...


@pytest.fixture
async def owui_client(owui_url: str) -> OwuiClient: ...
```

## Test Discovery (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests", "plugins"]
markers = [
    "integration: marks tests that require a running Open WebUI container",
    "unit: marks tests that do not require a container",
]
```

Tests placed in `plugins/<plugin-name>/tests/` are auto-discovered.

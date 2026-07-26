# Integration Testing

Integration tests require a running Open WebUI container. They use the `owui_client` fixture defined in the root `conftest.py`, which starts docker-compose, waits for readiness, and tears down afterward.

## Marking

Every integration test must be marked with `@pytest.mark.integration`:

```python
import pytest


@pytest.mark.integration
class TestMyPlugin: ...
```

## Example: `tests/test_integration.py` (optimized-search)

Full file at `plugins/optimized-search/tests/test_integration.py` (56 lines).

### Test Class with Container-Gated Fixture

```python
import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
PLUGIN_SOURCE = (PLUGIN_DIR / "optimized-search.py").read_text("utf-8")
TOOL_ID = "optimized_search"
TOOL_NAME = "Optimized Search"


@pytest.mark.integration
class TestOptimizedSearchTool:
    async def test_upload_tool(self, owui_client):
        tool = await owui_client.create_tool(
            tool_id=TOOL_ID,
            name=TOOL_NAME,
            content=PLUGIN_SOURCE,
            description="Primary web search with auto mode selection",
        )
        assert tool["id"] == TOOL_ID
        assert tool["name"] == TOOL_NAME
```

### Testing Tool Upload and Listing

```python
async def test_tool_listed(self, owui_client):
    tools = await owui_client.get_tools()
    ids = [t["id"] for t in tools]
    assert TOOL_ID in ids
```

### Testing Tool Specs (Method Parameters)

```python
async def test_tool_specs(self, owui_client):
    tool = await owui_client.get_tool_by_id(TOOL_ID)
    specs = tool.get("specs", {})
    assert len(specs) >= 1

    method_names = [s.get("name") for s in specs]
    assert "optimized_search" in method_names

    opt_spec = next(s for s in specs if s["name"] == "optimized_search")
    params = opt_spec.get("parameters", {})
    properties = params.get("properties", {})
    assert "query" in properties
```

### Testing Valve Specifications

```python
async def test_valves_spec(self, owui_client):
    spec = await owui_client.get_tool_valves_spec(TOOL_ID)
    assert spec is not None
    props = spec.get("properties", {})
    assert "SEARXNG_URL" in props
    assert "DEFAULT_MODE" in props
    assert "DEFAULT_MAX_RESULTS" in props
    assert props["DEFAULT_MAX_RESULTS"].get("default") == 5
```

### Testing Valve Update/Read Cycle

```python
async def test_valves_update_and_read(self, owui_client):
    updated = await owui_client.update_tool_valves(
        TOOL_ID,
        {"DEFAULT_MAX_RESULTS": 10, "SHOW_SELECTION_REASONING": False},
    )
    assert updated.get("DEFAULT_MAX_RESULTS") == 10
    assert updated.get("SHOW_SELECTION_REASONING") is False
```

## Critical Setup

Create the tool **first**, then run subsequent tests that depend on it. Tests within a class run sequentially by default (pytest class-order), so the first test method should upload the tool.

## Running Integration Tests

```bash
# All integration tests (starts container if needed)
uv run pytest -m integration -v

# Specific integration test file
uv run pytest plugins/optimized-search/tests/test_integration.py -v

# Skip integration tests
uv run pytest -m "not integration"

# With custom Open WebUI URL (skip container lifecycle)
OWUI_URL=http://localhost:3000 uv run pytest -m integration
```

## When to Write Integration Tests

- Validating that the plugin can be uploaded to Open WebUI
- Verifying valve schemas match expectations (defaults, types, constraints)
- Checking that tool specs expose the correct method names and parameters
- Testing end-to-end valve update/read cycles
- Do **not** use integration tests for pure-logic assertions — those belong in unit tests

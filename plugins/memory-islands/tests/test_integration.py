from pathlib import Path
from typing import Any

import pytest

pytest.skip(
    "Skipping integration tests for Memory Islands plugin: environment not configured",
    allow_module_level=True,
)

# Integration tests for Memory Islands filter plugin.
PLUGIN_DIR = Path(__file__).resolve().parent.parent
FUNCTION_ID = "memory_islands"
FUNCTION_NAME = "Memory Islands"


@pytest.fixture
def plugin_source() -> str:
    """Load the plugin source. Lazy loaded to prevent pytest collection errors."""
    path = PLUGIN_DIR / "plugin.py"
    if not path.exists():
        pytest.skip(f"plugin.py not found at {path}.")
    return path.read_text("utf-8")


@pytest.mark.integration
class TestMemoryIslandsFilter:
    """Integration test suite verifying Memory Islands filter inside running Open WebUI container."""

    async def test_upload_filter(self, owui_client: Any, plugin_source: str) -> None:
        """Verify the Filter plugin can be successfully uploaded to the Open WebUI container."""
        # Clean up any stale function registrations to ensure robustness across repeated local runs
        try:
            await owui_client.delete_function(FUNCTION_ID)
        except Exception:
            pass

        filter_func = await owui_client.create_function(
            function_id=FUNCTION_ID,
            name=FUNCTION_NAME,
            content=plugin_source,
            description="Dynamic, folder-scoped context and memory isolation for Open WebUI",
        )
        assert filter_func["id"] == FUNCTION_ID
        assert filter_func["name"] == FUNCTION_NAME

    async def test_filter_listed(self, owui_client: Any) -> None:
        """Check if the plugin is successfully listed in Open WebUI's active functions index."""
        functions = await owui_client.get_functions()
        ids = [f["id"] for f in functions]
        assert FUNCTION_ID in ids

    async def test_filter_specs(self, owui_client: Any) -> None:
        """Retrieve the filter by ID and verify its inner specifications/code integrity."""
        filter_func = await owui_client.get_function_by_id(FUNCTION_ID)
        assert filter_func["id"] == FUNCTION_ID
        assert filter_func["name"] == FUNCTION_NAME
        assert "class Filter" in filter_func["content"]
        assert "async def inlet(" in filter_func["content"]
        assert "async def outlet(" in filter_func["content"]

    async def test_valves_spec(self, owui_client: Any) -> None:
        """Verify that the Filter's admin configuration Valves properties are correctly registered."""
        spec = await owui_client.get_function_valves_spec(FUNCTION_ID)
        assert spec is not None
        props = spec.get("properties", {})
        assert "ISOLATE_BY_DEFAULT" in props
        assert "AUTO_LEARN_MEMORIES" in props
        assert "EXTRACTION_MODEL" in props
        assert "EXTRACTION_INTERVAL" in props
        assert "ENABLE_UPDATE_NOTIFICATIONS" in props
        assert "CHECK_PREVIEW_RELEASES" in props

    async def test_valves_update_and_read(self, owui_client: Any) -> None:
        """Test the end-to-end valve update/read cycle in the running Open WebUI container."""
        updated = await owui_client.update_function_valves(
            FUNCTION_ID,
            {
                "ISOLATE_BY_DEFAULT": False,
                "AUTO_LEARN_MEMORIES": False,
                "ENABLE_UPDATE_NOTIFICATIONS": True,
                "CHECK_PREVIEW_RELEASES": False,
            },
        )
        assert updated.get("ISOLATE_BY_DEFAULT") is False
        assert updated.get("AUTO_LEARN_MEMORIES") is False
        assert updated.get("ENABLE_UPDATE_NOTIFICATIONS") is True
        assert updated.get("CHECK_PREVIEW_RELEASES") is False

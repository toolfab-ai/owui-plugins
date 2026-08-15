from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
FUNCTION_ID = "iterative_research"
FUNCTION_NAME = "Iterative Deep Research Agent"


@pytest.fixture
def plugin_source() -> str:
    """Load the compiled plugin source. Lazy loaded to prevent pytest collection errors."""
    path = PLUGIN_DIR / "plugin.py"
    if not path.exists():
        pytest.skip(f"plugin.py not found at {path}. Run build script first.")
    return path.read_text("utf-8")


@pytest.mark.integration
class TestIterativeResearchPipe:
    async def test_upload_pipe(self, owui_client, plugin_source) -> None:
        """Verify the compiled Pipe plugin can be successfully uploaded as an Open WebUI function."""
        # Clean up any stale function registrations to ensure robustness across repeated local runs
        try:
            await owui_client.delete_function(FUNCTION_ID)
        except Exception:
            pass

        pipe = await owui_client.create_function(
            function_id=FUNCTION_ID,
            name=FUNCTION_NAME,
            content=plugin_source,
            description="Autonomous multi-step search, parallel scrape, and cited synthesis agent",
        )
        assert pipe["id"] == FUNCTION_ID
        assert pipe["name"] == FUNCTION_NAME

    async def test_pipe_listed(self, owui_client) -> None:
        """Check if the plugin is successfully listed in Open WebUI's active functions index."""
        functions = await owui_client.get_functions()
        ids = [f["id"] for f in functions]
        assert FUNCTION_ID in ids

    async def test_pipe_specs(self, owui_client) -> None:
        """Retrieve the function by ID and verify its inner specifications/code integrity."""
        pipe = await owui_client.get_function_by_id(FUNCTION_ID)
        assert pipe["id"] == FUNCTION_ID
        assert pipe["name"] == FUNCTION_NAME
        assert "class Pipe" in pipe["content"]
        assert "async def pipe(" in pipe["content"]

    async def test_valves_spec(self, owui_client) -> None:
        """Verify that the Pipe's admin configuration Valves properties are correctly registered."""
        spec = await owui_client.get_function_valves_spec(FUNCTION_ID)
        assert spec is not None
        props = spec.get("properties", {})
        assert "SEARXNG_URL" in props
        assert "TAVILY_API_KEY" in props
        assert "MODEL" in props
        assert "MAX_STEPS" in props
        assert "MAX_PAGES_TO_SCRAPE" in props
        assert "CO_STORM_STEERING" in props

    async def test_valves_update_and_read(self, owui_client) -> None:
        """Test the end-to-end valve update/read cycle in the running Open WebUI container."""
        updated = await owui_client.update_function_valves(
            FUNCTION_ID,
            {
                "SEARXNG_URL": "http://searxng:8080",
                "MAX_STEPS": 4,
                "CO_STORM_STEERING": True,
            },
        )
        assert updated.get("SEARXNG_URL") == "http://searxng:8080"
        assert updated.get("MAX_STEPS") == 4
        assert updated.get("CO_STORM_STEERING") is True

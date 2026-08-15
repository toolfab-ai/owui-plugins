from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
ACTION_ID = "export_chat"
ACTION_NAME = "Export Chat"


@pytest.fixture
def plugin_source() -> str:
    """Load the plugin source. Lazy loaded to prevent pytest collection errors."""
    # For export-chat we could use src/main.py, but for integration we prefer the built artifact if available
    # or the main entry point.
    path = PLUGIN_DIR / "plugin.py"
    if not path.exists():
        path = PLUGIN_DIR / "src" / "main.py"
    return path.read_text("utf-8")


@pytest.mark.integration
class TestExportChatAction:
    async def test_upload_action(self, owui_client, plugin_source):
        action = await owui_client.create_function(
            function_id=ACTION_ID,
            name=ACTION_NAME,
            content=plugin_source,
            description="Export chat messages to PDF, CSV, or Word format",
        )
        assert action["id"] == ACTION_ID
        assert action["name"] == ACTION_NAME

    async def test_action_listed(self, owui_client):
        functions = await owui_client.get_functions()
        ids = [f["id"] for f in functions]
        assert ACTION_ID in ids

    async def test_action_specs(self, owui_client):
        action = await owui_client.get_function_by_id(ACTION_ID)
        assert action["id"] == ACTION_ID
        assert action["name"] == ACTION_NAME
        assert "class Action" in action["content"]
        assert "async def action(" in action["content"]
        assert action["meta"]["description"] == "Export chat messages to PDF, CSV, or Word format"

    async def test_valves_spec(self, owui_client):
        spec = await owui_client.get_function_valves_spec(ACTION_ID)
        assert spec is not None
        props = spec.get("properties", {})
        assert "export_formats" in props
        assert "base_url" in props

    async def test_valves_update_and_read(self, owui_client):
        updated = await owui_client.update_function_valves(
            ACTION_ID,
            {"export_formats": "pdf,csv,word", "base_url": "http://localhost:3000"},
        )
        assert updated.get("export_formats") == "pdf,csv,word"
        assert updated.get("base_url") == "http://localhost:3000"

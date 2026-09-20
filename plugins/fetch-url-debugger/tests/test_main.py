from __future__ import annotations

import os
import socket
import sys
import unittest.mock as mock
from pathlib import Path
from typing import Any, Dict

import pytest

# Use the plugin loader to import the plugin
from tests._plugin_loader import load_plugin

# Dynamically load the plugin module
plugin_module = load_plugin("fetch-url-debugger")
Filter = plugin_module.Filter
emitter_var = plugin_module.emitter_var

PLUGIN_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def plugin_source() -> str:
    """Load the plugin source for integration tests."""
    path = PLUGIN_DIR / "plugin.py"
    if not path.exists():
        pytest.skip(f"plugin.py not found at {path}.")
    return path.read_text("utf-8")


@pytest.fixture
def mock_builtin_tools():
    """Mock open_webui modules to avoid ImportErrors and allow patching."""
    mock_builtin = mock.MagicMock()
    mock_tools_router = mock.MagicMock()
    mock_retrieval_utils = mock.MagicMock()
    mock_utils_tools = mock.MagicMock()

    modules = {
        "open_webui": mock.MagicMock(),
        "open_webui.apps": mock.MagicMock(),
        "open_webui.apps.webui": mock.MagicMock(),
        "open_webui.apps.webui.routers": mock.MagicMock(),
        "open_webui.apps.webui.routers.tools": mock_tools_router,
        "open_webui.tools": mock.MagicMock(),
        "open_webui.tools.builtin": mock_builtin,
        "open_webui.utils": mock.MagicMock(),
        "open_webui.utils.tools": mock_utils_tools,
        "open_webui.retrieval": mock.MagicMock(),
        "open_webui.retrieval.utils": mock_retrieval_utils,
    }

    with mock.patch.dict(sys.modules, modules):
        yield {
            "builtin": mock_builtin,
            "tools_router": mock_tools_router,
            "retrieval_utils": mock_retrieval_utils,
            "utils_tools": mock_utils_tools,
        }


@pytest.fixture
def filter_instance():
    """Provides a fresh instance of the Filter and resets global state."""
    # Reset the global patched flag before each test
    Filter._global_patched = False
    # Clear the ContextVar
    emitter_var.set(None)
    return Filter()


@pytest.fixture
def mock_event_emitter():
    """Provides a mock event emitter."""
    return mock.AsyncMock()


@pytest.mark.unit
class TestFetchUrlDebugger:
    @pytest.mark.asyncio
    async def test_inlet_sets_context_var(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        mock_event_emitter: mock.AsyncMock,
    ):
        """Verify that inlet sets the ContextVar."""
        body: Dict[str, Any] = {}
        await filter_instance.inlet(body, __event_emitter__=mock_event_emitter)

        assert emitter_var.get() == mock_event_emitter

    @pytest.mark.asyncio
    async def test_inlet_respects_verbose_ui(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        mock_event_emitter: mock.AsyncMock,
    ):
        """Verify that inlet respects the verbose_ui toggle."""
        filter_instance.valves.verbose_ui = False
        await filter_instance.inlet({}, __event_emitter__=mock_event_emitter)
        assert mock_event_emitter.call_count == 0

        filter_instance.valves.verbose_ui = True
        await filter_instance.inlet({}, __event_emitter__=mock_event_emitter)
        # Should have at least the heartbeat
        assert mock_event_emitter.call_count > 0
        calls = [call.args[0] for call in mock_event_emitter.call_args_list]
        assert any(
            "🔍 Debugger active. Intercepting retrieval via get_content_from_url..."
            in c["data"]["description"]
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_aggressive_patching_sys_modules(self, filter_instance: Filter):
        """Verify that patching logic searches through sys.modules."""
        # Create a mock module that has a fetch_url function
        mock_mod = mock.MagicMock()

        def fetch_url():
            pass

        mock_mod.fetch_url = fetch_url

        # Mock sys.modules
        with mock.patch.dict(sys.modules, {"dummy_tool_module": mock_mod}):
            await filter_instance.inlet({})

            # Verify the function in the dummy module was patched
            assert getattr(mock_mod.fetch_url, "__is_fetch_url_debugger__", False) is True

    @pytest.mark.asyncio
    async def test_aggressive_patching_get_content_from_url(self, filter_instance: Filter):
        """Verify that patching logic catches modules containing get_content_from_url."""
        mock_mod = mock.MagicMock()

        def get_content_from_url():
            pass

        mock_mod.get_content_from_url = get_content_from_url

        with mock.patch.dict(sys.modules, {"dummy_retrieval_module": mock_mod}):
            await filter_instance.inlet({})
            assert (
                getattr(mock_mod.get_content_from_url, "__is_fetch_url_debugger__", False) is True
            )

    @pytest.mark.asyncio
    async def test_inlet_patches_all_targets(
        self, filter_instance: Filter, mock_builtin_tools: Dict[str, mock.MagicMock]
    ):
        """Verify that inlet patches targeted modules."""
        # Setup targets
        mock_builtin_tools["builtin"].fetch_url = mock.AsyncMock()
        mock_builtin_tools["builtin"].fetch_url.__name__ = "fetch_url"

        mock_builtin_tools["tools_router"].fetch_url = mock.AsyncMock()
        mock_builtin_tools["tools_router"].fetch_url.__name__ = "fetch_url"

        mock_builtin_tools["utils_tools"].fetch_url = mock.AsyncMock()
        mock_builtin_tools["utils_tools"].fetch_url.__name__ = "fetch_url"

        mock_builtin_tools["retrieval_utils"].get_content_from_url = mock.AsyncMock()
        mock_builtin_tools["retrieval_utils"].get_content_from_url.__name__ = "get_content_from_url"

        await filter_instance.inlet({})

        # Verify all are patched
        assert getattr(mock_builtin_tools["builtin"].fetch_url, "__is_fetch_url_debugger__", False)
        assert getattr(
            mock_builtin_tools["tools_router"].fetch_url, "__is_fetch_url_debugger__", False
        )
        assert getattr(
            mock_builtin_tools["utils_tools"].fetch_url, "__is_fetch_url_debugger__", False
        )
        assert getattr(
            mock_builtin_tools["retrieval_utils"].get_content_from_url,
            "__is_fetch_url_debugger__",
            False,
        )

    @pytest.mark.asyncio
    async def test_patch_only_once(
        self, filter_instance: Filter, mock_builtin_tools: Dict[str, mock.MagicMock]
    ):
        """Verify that the patch is only applied once, even across instances."""
        mock_builtin_tools["builtin"].fetch_url = mock.AsyncMock()
        mock_builtin_tools["builtin"].fetch_url.__name__ = "fetch_url"

        # First call
        await filter_instance.inlet({})
        patched_func = mock_builtin_tools["builtin"].fetch_url

        # Second call
        await filter_instance.inlet({})
        assert mock_builtin_tools["builtin"].fetch_url == patched_func

        # Create another instance
        another_filter = Filter()
        await another_filter.inlet({})
        assert mock_builtin_tools["builtin"].fetch_url == patched_func

    @pytest.mark.asyncio
    async def test_wrapped_function_calls_original(
        self, filter_instance: Filter, mock_builtin_tools: Dict[str, mock.MagicMock]
    ):
        """Verify that the wrapped function correctly calls the original function."""
        original = mock.AsyncMock(return_value="result_data")
        original.__name__ = "fetch_url"
        mock_builtin_tools["builtin"].fetch_url = original

        await filter_instance.inlet({})

        # Call the patched function
        result = await mock_builtin_tools["builtin"].fetch_url(
            "http://example.com", some_arg="value"
        )

        assert result == "result_data"
        original.assert_called_once_with("http://example.com", some_arg="value")

    @pytest.mark.asyncio
    async def test_logs_to_stderr(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        capsys: pytest.CaptureFixture,
    ):
        """Verify that the wrapped function logs request details to sys.stderr."""
        original = mock.AsyncMock(return_value="ok")
        original.__name__ = "fetch_url"
        mock_builtin_tools["builtin"].fetch_url = original

        await filter_instance.inlet({})

        # Call patched function
        await mock_builtin_tools["builtin"].fetch_url("http://example.com")

        captured = capsys.readouterr()
        assert "CALLING fetch_url" in captured.err
        assert "URL: http://example.com" in captured.err
        assert "SUCCESS: fetch_url" in captured.err

    @pytest.mark.asyncio
    async def test_dns_precheck(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        capsys: pytest.CaptureFixture,
    ):
        """Verify DNS pre-check behavior by mocking socket.getaddrinfo."""
        original = mock.AsyncMock(return_value="ok")
        original.__name__ = "fetch_url"
        mock_builtin_tools["builtin"].fetch_url = original

        with mock.patch("socket.getaddrinfo") as mock_getaddrinfo:
            # Mock successful DNS resolution
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]

            await filter_instance.inlet({})
            await mock_builtin_tools["builtin"].fetch_url("http://example.com")

            captured = capsys.readouterr()
            assert "DNS: example.com -> ['93.184.216.34']" in captured.err

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception, expected_category",
        [
            (TimeoutError("Connection timed out"), "TIMEOUT"),
            (Exception("SSL error occurred"), "SSL_ERROR"),
            (ConnectionRefusedError("Connection refused"), "CONNECTION_ERROR"),
            (socket.gaierror(-2, "Name or service not known"), "DNS_ERROR"),
            (ValueError("Some other error"), "UNKNOWN_ERROR"),
        ],
    )
    async def test_error_categorization(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        capsys: pytest.CaptureFixture,
        exception: Exception,
        expected_category: str,
    ):
        """Verify error categorization by mocking the original function to raise errors."""
        original = mock.AsyncMock(side_effect=exception)
        original.__name__ = "fetch_url"
        mock_builtin_tools["builtin"].fetch_url = original

        await filter_instance.inlet({})

        with pytest.raises(type(exception)):
            await mock_builtin_tools["builtin"].fetch_url("http://example.com")

        captured = capsys.readouterr()
        assert "FAILED: fetch_url" in captured.err
        assert f"FAILED: fetch_url | {expected_category}" in captured.err
        assert f"| {str(exception)}" in captured.err

    @pytest.mark.asyncio
    async def test_emits_status_events(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        mock_event_emitter: mock.AsyncMock,
    ):
        """Verify that the wrapped function emits UI status events."""
        original = mock.AsyncMock(return_value="ok")
        original.__name__ = "fetch_url"
        mock_builtin_tools["builtin"].fetch_url = original

        # inlet sets the emitter in ContextVar
        await filter_instance.inlet({}, __event_emitter__=mock_event_emitter)

        with mock.patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]

            # Call patched function
            await mock_builtin_tools["builtin"].fetch_url("http://example.com")

            # Check that event emitter was called with expected statuses
            calls = [call.args[0] for call in mock_event_emitter.call_args_list]

            # Should have at least the DNS check and the native call status
            assert any(
                "🌐 Calling fetch_url for http://example.com | DNS: example.com"
                in c["data"]["description"]
                for c in calls
            )
            assert any("✅ fetch_url SUCCESS" in c["data"]["description"] for c in calls)

    @pytest.mark.asyncio
    async def test_emits_error_status_events(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        mock_event_emitter: mock.AsyncMock,
    ):
        """Verify that the wrapped function emits UI status events on failure."""
        exception = TimeoutError("Connection timed out")
        original = mock.AsyncMock(side_effect=exception)
        original.__name__ = "fetch_url"
        mock_builtin_tools["builtin"].fetch_url = original

        await filter_instance.inlet({}, __event_emitter__=mock_event_emitter)

        with pytest.raises(TimeoutError):
            await mock_builtin_tools["builtin"].fetch_url("http://example.com")

        calls = [call.args[0] for call in mock_event_emitter.call_args_list]
        assert any(
            "❌ fetch_url FAILED (TIMEOUT): Connection timed out" in c["data"]["description"]
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_handles_sync_function(
        self,
        filter_instance: Filter,
        mock_builtin_tools: Dict[str, mock.MagicMock],
        capsys: pytest.CaptureFixture,
        mock_event_emitter: mock.AsyncMock,
    ):
        """Verify that it correctly patches and calls a synchronous function."""
        original = mock.MagicMock(return_value="sync_result")
        original.__name__ = "fetch_url"
        mock_builtin_tools["builtin"].fetch_url = original

        await filter_instance.inlet({}, __event_emitter__=mock_event_emitter)

        # In this case, the patched function should be synchronous as well
        result = mock_builtin_tools["builtin"].fetch_url("http://example.com")

        assert result == "sync_result"
        captured = capsys.readouterr()
        assert "CALLING fetch_url (SYNC)" in captured.err
        assert "SUCCESS: fetch_url" in captured.err

        # Check sync emitter was called (async emitter mock called from sync loop)
        calls = [call.args[0] for call in mock_event_emitter.call_args_list]
        assert any(
            "🌐 Calling fetch_url for http://example.com | DNS:" in c["data"]["description"]
            for c in calls
        )


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OWUI_TEST_INTEGRATION"), reason="Integration tests disabled")
class TestFetchUrlDebuggerIntegration:
    """Integration test suite for Fetch URL Debugger."""

    async def test_upload_filter(self, owui_client: Any, plugin_source: str) -> None:
        """Verify the Filter plugin can be successfully uploaded."""
        # Clean up
        try:
            await owui_client.delete_function("fetch_url_debugger")
        except Exception:
            pass

        filter_func = await owui_client.create_function(
            function_id="fetch_url_debugger",
            name="Fetch URL Debugger",
            content=plugin_source,
            description="Monkey-patches fetch_url for debugging",
        )
        assert filter_func["id"] == "fetch_url_debugger"

    async def test_valves_registered(self, owui_client: Any) -> None:
        """Verify Valves are correctly registered."""
        spec = await owui_client.get_function_valves_spec("fetch_url_debugger")
        assert spec is not None
        props = spec.get("properties", {})
        assert "enabled" in props
        assert "priority" in props
        assert "verbose_ui" in props

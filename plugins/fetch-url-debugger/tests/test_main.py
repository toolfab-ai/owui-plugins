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
    """Mock open_webui.tools.builtin to avoid ImportErrors and allow patching."""
    mock_builtin = mock.MagicMock()
    mock_tools = mock.MagicMock()
    mock_open_webui = mock.MagicMock()

    mock_open_webui.tools = mock_tools
    mock_tools.builtin = mock_builtin

    # Crucially, we need to make sure fetch_url doesn't look like it's already patched
    # MagicMocks return another MagicMock for any attribute access, which is truthy.
    # We'll set the specific attribute to False.

    modules = {
        "open_webui": mock_open_webui,
        "open_webui.tools": mock_tools,
        "open_webui.tools.builtin": mock_builtin,
    }

    with mock.patch.dict(sys.modules, modules):
        yield mock_builtin


@pytest.fixture
def filter_instance():
    """Provides a fresh instance of the Filter and resets global state."""
    # Reset the global patched flag before each test
    if hasattr(Filter, "_global_patched"):
        Filter._global_patched = False
    return Filter()


@pytest.fixture
def mock_event_emitter():
    """Provides a mock event emitter."""
    return mock.AsyncMock()


@pytest.mark.unit
class TestFetchUrlDebugger:
    @pytest.mark.asyncio
    async def test_inlet_patches_fetch_url(
        self, filter_instance: Filter, mock_builtin_tools: mock.MagicMock
    ):
        """Verify that calling inlet patches open_webui.tools.builtin.fetch_url."""
        # Setup original fetch_url
        original_fetch_url = mock.AsyncMock(return_value="success")
        # Ensure it doesn't appear already patched
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        # Run inlet
        body: Dict[str, Any] = {}
        await filter_instance.inlet(body)

        # Verify it is patched
        assert mock_builtin_tools.fetch_url != original_fetch_url
        assert getattr(mock_builtin_tools.fetch_url, "__is_fetch_url_debugger__", False) is True

    @pytest.mark.asyncio
    async def test_patch_only_once(
        self, filter_instance: Filter, mock_builtin_tools: mock.MagicMock
    ):
        """Verify that the patch is only applied once, even across instances."""
        original_fetch_url = mock.AsyncMock(return_value="success")
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        # First call
        await filter_instance.inlet({})
        patched_func = mock_builtin_tools.fetch_url

        # Second call
        await filter_instance.inlet({})
        assert mock_builtin_tools.fetch_url == patched_func

        # Create another instance
        another_filter = Filter()
        await another_filter.inlet({})
        assert mock_builtin_tools.fetch_url == patched_func

    @pytest.mark.asyncio
    async def test_wrapped_function_calls_original(
        self, filter_instance: Filter, mock_builtin_tools: mock.MagicMock
    ):
        """Verify that the wrapped function correctly calls the original fetch_url."""
        original_fetch_url = mock.AsyncMock(return_value="result_data")
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        await filter_instance.inlet({})

        # Call the patched function
        result = await mock_builtin_tools.fetch_url("http://example.com", some_arg="value")

        assert result == "result_data"
        original_fetch_url.assert_called_once_with("http://example.com", some_arg="value")

    @pytest.mark.asyncio
    async def test_logs_to_stderr(
        self,
        filter_instance: Filter,
        mock_builtin_tools: mock.MagicMock,
        capsys: pytest.CaptureFixture,
    ):
        """Verify that the wrapped function logs request details to sys.stderr."""
        original_fetch_url = mock.AsyncMock(return_value="ok")
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        await filter_instance.inlet({})

        # Call patched function
        await mock_builtin_tools.fetch_url("http://example.com")

        captured = capsys.readouterr()
        assert "FETCH URL DEBUGGER" in captured.err
        assert "REQUEST INITIATED" in captured.err
        assert "URL: http://example.com" in captured.err
        assert "REQUEST SUCCESSFUL" in captured.err

    @pytest.mark.asyncio
    async def test_dns_precheck(
        self,
        filter_instance: Filter,
        mock_builtin_tools: mock.MagicMock,
        capsys: pytest.CaptureFixture,
    ):
        """Verify DNS pre-check behavior by mocking socket.getaddrinfo."""
        original_fetch_url = mock.AsyncMock(return_value="ok")
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        with mock.patch("socket.getaddrinfo") as mock_getaddrinfo:
            # Mock successful DNS resolution
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]

            await filter_instance.inlet({})
            await mock_builtin_tools.fetch_url("http://example.com")

            captured = capsys.readouterr()
            assert "DNS Check: Resolved example.com to ['93.184.216.34']" in captured.err

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
        mock_builtin_tools: mock.MagicMock,
        capsys: pytest.CaptureFixture,
        exception: Exception,
        expected_category: str,
    ):
        """Verify error categorization by mocking the original function to raise errors."""
        original_fetch_url = mock.AsyncMock(side_effect=exception)
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        await filter_instance.inlet({})

        with pytest.raises(type(exception)):
            await mock_builtin_tools.fetch_url("http://example.com")

        captured = capsys.readouterr()
        assert "REQUEST FAILED" in captured.err
        assert f"CATEGORY: {expected_category}" in captured.err
        assert f"ERROR: {str(exception)}" in captured.err

    @pytest.mark.asyncio
    async def test_emits_status_events(
        self,
        filter_instance: Filter,
        mock_builtin_tools: mock.MagicMock,
        mock_event_emitter: mock.AsyncMock,
    ):
        """Verify that the wrapped function emits UI status events."""
        original_fetch_url = mock.AsyncMock(return_value="ok")
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        await filter_instance.inlet({})

        with mock.patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]

            # Call patched function with event emitter
            await mock_builtin_tools.fetch_url(
                "http://example.com", __event_emitter__=mock_event_emitter
            )

            # Check that event emitter was called with expected statuses
            calls = [call.args[0] for call in mock_event_emitter.call_args_list]

            # Should have at least the DNS check and the native call status
            assert any(
                "DEBUG: DNS Check: Resolved example.com" in c["data"]["description"] for c in calls
            )
            assert any(
                "DEBUG: Calling native fetch_url..." in c["data"]["description"] for c in calls
            )

    @pytest.mark.asyncio
    async def test_emits_error_status_events(
        self,
        filter_instance: Filter,
        mock_builtin_tools: mock.MagicMock,
        mock_event_emitter: mock.AsyncMock,
    ):
        """Verify that the wrapped function emits UI status events on failure."""
        exception = TimeoutError("Connection timed out")
        original_fetch_url = mock.AsyncMock(side_effect=exception)
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        await filter_instance.inlet({})

        with pytest.raises(TimeoutError):
            await mock_builtin_tools.fetch_url(
                "http://example.com", __event_emitter__=mock_event_emitter
            )

        calls = [call.args[0] for call in mock_event_emitter.call_args_list]
        assert any(
            "DEBUG: fetch_url failed (TIMEOUT): Connection timed out" in c["data"]["description"]
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_handles_sync_function(
        self,
        filter_instance: Filter,
        mock_builtin_tools: mock.MagicMock,
        capsys: pytest.CaptureFixture,
    ):
        """Verify that it correctly patches and calls a synchronous fetch_url."""
        original_fetch_url = mock.MagicMock(return_value="sync_result")
        original_fetch_url.__is_fetch_url_debugger__ = False
        mock_builtin_tools.fetch_url = original_fetch_url

        await filter_instance.inlet({})

        # In this case, the patched function should be synchronous as well
        # based on inspect.iscoroutinefunction(original_fetch_url)
        result = mock_builtin_tools.fetch_url("http://example.com")

        assert result == "sync_result"
        captured = capsys.readouterr()
        assert "REQUEST INITIATED (SYNC)" in captured.err
        assert "REQUEST SUCCESSFUL" in captured.err


# ... existing imports ...


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
        assert "ENABLED" in props
        assert "PRIORITY" in props

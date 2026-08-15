# ruff: noqa: E402
"""Unit tests for iterative-research core logic and metadata."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# ========================================================================
# MOCK OPEN_WEBUI DEPENDENCIES
# ========================================================================
sys.modules["open_webui"] = MagicMock()
sys.modules["open_webui.utils"] = MagicMock()
sys.modules["open_webui.utils.chat"] = MagicMock()
sys.modules["open_webui.models"] = MagicMock()
sys.modules["open_webui.models.models"] = MagicMock()
sys.modules["open_webui.models.users"] = MagicMock()

from tests._plugin_loader import load_plugin

mod = load_plugin("iterative-research")
Pipe = mod.Pipe


@pytest.mark.unit
class TestParseJsonCompletions:
    """Test ``_parse_json_completions`` method."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    def test_standard_json(self) -> None:
        raw_json = '{"gaps": ["gap1"], "queries": ["query1"]}'
        result = self.pipe._parse_json_completions(raw_json)
        assert result == {"gaps": ["gap1"], "queries": ["query1"]}

    def test_markdown_codeblock_json(self) -> None:
        raw_md = (
            "Here is the plan:\n"
            "```json\n"
            '{\n  "gaps": ["gap2"],\n  "queries": ["query2"]\n}\n'
            "```\n"
            "Hope this helps!"
        )
        result = self.pipe._parse_json_completions(raw_md)
        assert result == {"gaps": ["gap2"], "queries": ["query2"]}

    def test_curly_braces_only(self) -> None:
        raw_braces = (
            'Some leading text {"gaps": ["gap3"], "queries": ["query3"]} Some trailing text'
        )
        result = self.pipe._parse_json_completions(raw_braces)
        assert result == {"gaps": ["gap3"], "queries": ["query3"]}

    def test_invalid_json_fallback(self) -> None:
        raw_text = (
            "No JSON here, but a list:\n"
            "- gap4\n"
            "Queries:\n"
            "1. Apple Stock Price 2026\n"
            "2. Microsoft Earnings Q2"
        )
        result = self.pipe._parse_json_completions(raw_text)
        assert "gaps" in result
        assert len(result["queries"]) >= 2
        assert "Apple Stock Price 2026" in result["queries"]


@pytest.mark.unit
class TestPipesRegistration:
    """Test registration and meta endpoints."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    def test_pipes_returns_metadata(self) -> None:
        pipes_list = self.pipe.pipes()
        assert len(pipes_list) == 1
        assert pipes_list[0]["id"] == "iterative_research_pipe"
        assert "Iterative" in pipes_list[0]["name"]


@pytest.mark.unit
class TestUpdateMixin:
    """Test ``UpdateMixin`` update check and notification logic."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    def test_get_current_version(self) -> None:
        # Should match the version from the module docstring
        assert self.pipe._get_current_version() == "0.9.1"

    def test_parse_version(self) -> None:
        # Standard stable major.minor.patch:
        assert self.pipe._parse_version("1.2.3") == (1, 2, 3, 4, 0)
        assert self.pipe._parse_version("v2.0.45") == (2, 0, 45, 4, 0)
        # Pre-releases:
        assert self.pipe._parse_version("0.2.0-dev") == (0, 2, 0, 0, 0)
        assert self.pipe._parse_version("0.2.0-beta.1") == (0, 2, 0, 2, 1)
        assert self.pipe._parse_version("0.2.0-beta.2") == (0, 2, 0, 2, 2)
        assert self.pipe._parse_version("0.2.0-rc.1") == (0, 2, 0, 3, 1)
        # Invalid fallbacks:
        assert self.pipe._parse_version("invalid") == (0, 0, 0, 0, 0)
        assert self.pipe._parse_version("") == (0, 0, 0, 0, 0)

    def test_version_comparison_with_pre_releases(self) -> None:
        v_0_1_0_beta_1 = self.pipe._parse_version("0.1.0-beta.1")
        v_0_1_0_beta_2 = self.pipe._parse_version("0.1.0-beta.2")
        v_0_1_0 = self.pipe._parse_version("0.1.0")
        v_0_2_0_beta_1 = self.pipe._parse_version("0.2.0-beta.1")

        assert v_0_1_0_beta_2 > v_0_1_0_beta_1
        assert v_0_1_0 > v_0_1_0_beta_2
        assert v_0_2_0_beta_1 > v_0_1_0

    @pytest.mark.asyncio
    async def test_get_update_notification_no_user(self) -> None:
        # Should return None if user is None
        assert await self.pipe._get_update_notification(None) is None

    @pytest.mark.asyncio
    async def test_get_update_notification_disabled(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = False
        user = {"id": "user1", "role": "admin"}
        assert await self.pipe._get_update_notification(user) is None

    @pytest.mark.asyncio
    async def test_get_update_notification_no_new_version(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        user = {"id": "user1", "role": "admin"}

        mock_releases = [
            {"tag_name": "iterative-research/v0.1.0-beta.1", "prerelease": True},
            {"tag_name": "iterative-research/v0.0.9"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            assert await self.pipe._get_update_notification(user) is None

    @pytest.mark.asyncio
    async def test_get_update_notification_new_version_available_admin(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        user = {"id": "user1", "role": "admin"}

        mock_releases = [
            {"tag_name": "iterative-research/v1.0.0", "html_url": "http://example.com/v1.0.0"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            msg = await self.pipe._get_update_notification(user)
            assert msg is not None
            assert "1.0.0" in msg
            assert "http://example.com/v1.0.0" in msg
            assert "Update the plugin" in msg

    @pytest.mark.asyncio
    async def test_get_update_notification_new_version_available_user(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        user = {"id": "user2", "role": "user"}

        mock_releases = [
            {"tag_name": "iterative-research/v1.0.0"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            msg = await self.pipe._get_update_notification(user)
            assert msg is not None
            assert "Contact your administrator" in msg

    @pytest.mark.asyncio
    async def test_get_update_notification_cache(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        user = {"id": "user1", "role": "admin"}

        mock_releases = [
            {"tag_name": "iterative-research/v1.0.0"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            # First call
            await self.pipe._get_update_notification(user)
            assert mock_get.call_count == 1

            # Second call (should use cache)
            await self.pipe._get_update_notification(user)
            assert mock_get.call_count == 1

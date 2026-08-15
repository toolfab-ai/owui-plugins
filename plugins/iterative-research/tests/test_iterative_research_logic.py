# ruff: noqa: E402
"""Unit tests for iterative-research core logic and metadata."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
        assert self.pipe._get_current_version() == "0.1.0-beta.1"

    def test_is_preview_version(self) -> None:
        assert self.pipe._is_preview_version("0.1.0") is False
        assert self.pipe._is_preview_version("0.2.0-dev") is True
        assert self.pipe._is_preview_version("0.2.0-beta.1") is True
        assert self.pipe._is_preview_version("1.0.0") is False

    def test_parse_version(self) -> None:
        # Standard stable major.minor.patch:
        assert self.pipe._parse_version("1.2.3") == (1, 2, 3, 1)
        assert self.pipe._parse_version("v2.0.45") == (2, 0, 45, 1)
        # Pre-releases have final element 0:
        assert self.pipe._parse_version("0.2.0-dev") == (0, 2, 0, 0)
        assert self.pipe._parse_version("0.2.0-beta.1") == (0, 2, 0, 0)
        # Invalid fallbacks:
        assert self.pipe._parse_version("invalid") == (0, 0, 0, 0)
        assert self.pipe._parse_version("") == (0, 0, 0, 0)

    def test_version_comparison_with_pre_releases(self) -> None:
        v_0_1_0 = self.pipe._parse_version("0.1.0")  # (0, 1, 0, 1)
        v_0_2_0_dev = self.pipe._parse_version("0.2.0-dev")  # (0, 2, 0, 0)
        v_0_2_0 = self.pipe._parse_version("0.2.0")  # (0, 2, 0, 1)

        # 0.2.0-dev is a newer major/minor, so it should be larger than 0.1.0:
        assert v_0_2_0_dev > v_0_1_0
        # 0.2.0 stable is higher priority than 0.2.0 pre-release:
        assert v_0_2_0 > v_0_2_0_dev

    @pytest.mark.asyncio
    async def test_check_for_updates_no_emitter(self) -> None:
        # Should return early and not raise any error if emitter is None
        await self.pipe._check_for_updates(None, None)

    @pytest.mark.asyncio
    async def test_check_for_updates_no_user(self) -> None:
        # Should return early and not notify if user is None
        emitter = AsyncMock()
        await self.pipe._check_for_updates(None, emitter)
        emitter.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_updates_disabled(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = False
        emitter = AsyncMock()
        user = {"id": "user1", "role": "admin"}
        await self.pipe._check_for_updates(user, emitter)
        emitter.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_updates_no_new_version(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        emitter = AsyncMock()
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

            await self.pipe._check_for_updates(user, emitter)
            emitter.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_updates_new_version_available_admin(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        emitter = AsyncMock()
        user = {"id": "user1", "role": "admin"}

        mock_releases = [
            {"tag_name": "iterative-research/v0.2.0"},
            {"tag_name": "iterative-research/v0.1.0"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            await self.pipe._check_for_updates(user, emitter)
            emitter.assert_called_once()
            call_data = emitter.call_args[0][0]
            assert call_data["type"] == "notification"
            assert "0.2.0" in call_data["data"]["content"]
            assert "Please update." in call_data["data"]["content"]

    @pytest.mark.asyncio
    async def test_check_for_updates_new_version_available_user(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        emitter = AsyncMock()
        user = {"id": "user2", "role": "user"}

        mock_releases = [
            {"tag_name": "iterative-research/v0.2.0"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            await self.pipe._check_for_updates(user, emitter)
            emitter.assert_called_once()
            call_data = emitter.call_args[0][0]
            assert call_data["type"] == "notification"
            assert "0.2.0" in call_data["data"]["content"]
            assert "Contact your administrator to get it." in call_data["data"]["content"]

    @pytest.mark.asyncio
    async def test_check_for_updates_already_seen(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        emitter = AsyncMock()
        user = {"id": "user1", "role": "user"}

        mock_releases = [
            {"tag_name": "iterative-research/v0.2.0"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            # First run: notify and save seen
            await self.pipe._check_for_updates(user, emitter)
            assert emitter.call_count == 1

            # Reset emitter mock and call again
            emitter.reset_mock()
            await self.pipe._check_for_updates(user, emitter)
            # Should not notify again!
            emitter.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_updates_cache_avoids_http_call(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        emitter = AsyncMock()
        user1 = {"id": "user1", "role": "user"}
        user2 = {"id": "user2", "role": "user"}

        mock_releases = [
            {"tag_name": "iterative-research/v0.2.0"},
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            # First run: should execute HTTP call
            await self.pipe._check_for_updates(user1, emitter)
            assert mock_get.call_count == 1
            assert emitter.call_count == 1

            # Second run with different user: should NOT call HTTP API (uses cache), but should notify the second user
            emitter.reset_mock()
            mock_get.reset_mock()
            await self.pipe._check_for_updates(user2, emitter)
            mock_get.assert_not_called()
            assert emitter.call_count == 1

    @pytest.mark.asyncio
    async def test_check_for_updates_preview_disabled_by_default(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        self.pipe.valves.CHECK_PREVIEW_RELEASES = False
        emitter = AsyncMock()
        user = {"id": "admin1", "role": "admin"}

        mock_releases = [
            {
                "tag_name": "iterative-research/v0.2.0-dev",
                "prerelease": True,
            },  # Newer but dev/preview
            {"tag_name": "iterative-research/v0.1.0-beta.1", "prerelease": True},  # Same as current
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            await self.pipe._check_for_updates(user, emitter)
            # Should NOT notify since previews are disabled!
            emitter.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_updates_preview_enabled_admin_notified(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        self.pipe.valves.CHECK_PREVIEW_RELEASES = True
        emitter = AsyncMock()
        user = {"id": "admin1", "role": "admin"}

        mock_releases = [
            {
                "tag_name": "iterative-research/v0.2.0-beta.1",
                "prerelease": True,
            },  # Dev/preview version
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            await self.pipe._check_for_updates(user, emitter)
            # Admin should be notified of preview!
            emitter.assert_called_once()
            call_data = emitter.call_args[0][0]
            assert call_data["type"] == "notification"
            assert "0.2.0-beta.1" in call_data["data"]["content"]
            assert "preview version" in call_data["data"]["content"]

    @pytest.mark.asyncio
    async def test_check_for_updates_preview_enabled_user_not_notified(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        self.pipe.valves.CHECK_PREVIEW_RELEASES = True
        emitter = AsyncMock()
        user = {"id": "user1", "role": "user"}

        mock_releases = [
            {
                "tag_name": "iterative-research/v0.2.0-beta.1",
                "prerelease": True,
            },  # Dev/preview version
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            await self.pipe._check_for_updates(user, emitter)
            # Regular user must NOT be notified of preview!
            emitter.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_updates_preview_enabled_user_fallback_to_stable(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        self.pipe.valves.CHECK_PREVIEW_RELEASES = True
        emitter = AsyncMock()
        user = {"id": "user1", "role": "user"}

        mock_releases = [
            {
                "tag_name": "iterative-research/v0.2.0-beta.1",
                "prerelease": True,
            },  # Newest preview version (admin only)
            {
                "tag_name": "iterative-research/v0.1.1",
                "prerelease": False,
            },  # Newer stable version (everyone)
        ]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_releases
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            await self.pipe._check_for_updates(user, emitter)
            # Regular user should skip the preview but fall back to the newer stable version (0.1.1)!
            emitter.assert_called_once()
            call_data = emitter.call_args[0][0]
            assert call_data["type"] == "notification"
            assert "0.1.1" in call_data["data"]["content"]
            assert "Contact your administrator to get it." in call_data["data"]["content"]

    @pytest.mark.asyncio
    async def test_check_for_updates_network_error(self) -> None:
        self.pipe.valves.ENABLE_UPDATE_NOTIFICATIONS = True
        emitter = AsyncMock()
        user = {"id": "user1", "role": "admin"}

        with patch("httpx.AsyncClient.get", side_effect=httpx.HTTPError("Connection failed")):
            # Should not raise exception
            await self.pipe._check_for_updates(user, emitter)
            emitter.assert_not_called()

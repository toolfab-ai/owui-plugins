# ruff: noqa: E402
"""Unit tests for iterative-research search integration."""

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
class TestSearchQueryFallbacks:
    """Test fallback logic in ``_search_query`` when search APIs fail."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    @pytest.mark.asyncio
    async def test_tavily_configured_and_succeeds(self) -> None:
        self.pipe.valves.TAVILY_API_KEY = "tavily_key_123"
        self.pipe.valves.SEARXNG_URL = "http://searxng.local"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Tavily Title",
                    "url": "https://tavily.com/1",
                    "content": "Tavily Content",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await self.pipe._search_query("test query")
            assert len(results) == 1
            assert results[0]["title"] == "Tavily Title"
            assert results[0]["url"] == "https://tavily.com/1"
            assert results[0]["snippet"] == "Tavily Content"

            mock_client.post.assert_called_once()
            mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_tavily_fails_falls_back_to_searxng(self) -> None:
        self.pipe.valves.TAVILY_API_KEY = "tavily_key_123"
        self.pipe.valves.SEARXNG_URL = "http://searxng.local"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = httpx.HTTPError("Tavily unavailable")

        mock_searxng_response = MagicMock()
        mock_searxng_response.status_code = 200
        mock_searxng_response.json.return_value = {
            "results": [
                {
                    "title": "SearXNG Title",
                    "url": "https://searxng.com/2",
                    "content": "SearXNG Content",
                }
            ]
        }
        mock_searxng_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_searxng_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await self.pipe._search_query("test query")
            assert len(results) == 1
            assert results[0]["title"] == "SearXNG Title"
            assert results[0]["url"] == "https://searxng.com/2"
            assert results[0]["snippet"] == "SearXNG Content"

            # Must have called both
            mock_client.post.assert_called_once()
            mock_client.get.assert_called_once_with(
                "http://searxng.local/search",
                params={"q": "test query", "format": "json"},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )

    @pytest.mark.asyncio
    async def test_both_fail_returns_empty_list(self) -> None:
        self.pipe.valves.TAVILY_API_KEY = "tavily_key_123"
        self.pipe.valves.SEARXNG_URL = "http://searxng.local"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = httpx.HTTPError("Tavily down")
        mock_client.get.side_effect = httpx.HTTPError("SearXNG down")

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await self.pipe._search_query("test query")
            assert results == []

# ruff: noqa: E402
"""Unit tests for iterative-research scraper logic."""

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
class TestIsSafeUrl:
    """Test ``_is_safe_url`` SSRF protection method."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    @pytest.mark.asyncio
    async def test_public_url_safe(self) -> None:
        # Standard public websites should be safe
        assert await self.pipe._is_safe_url("https://www.google.com") is True
        assert await self.pipe._is_safe_url("https://example.com/some/path") is True

    @pytest.mark.asyncio
    async def test_localhost_unsafe(self) -> None:
        # Loopback is unsafe
        assert await self.pipe._is_safe_url("http://localhost") is False
        assert await self.pipe._is_safe_url("http://127.0.0.1:8080") is False

    @pytest.mark.asyncio
    async def test_private_subnets_unsafe(self) -> None:
        # RFC1918 networks are unsafe
        assert await self.pipe._is_safe_url("http://10.0.0.1") is False
        assert await self.pipe._is_safe_url("https://192.168.1.1/admin") is False
        assert await self.pipe._is_safe_url("http://172.16.0.1") is False

    @pytest.mark.asyncio
    async def test_malformed_url_unsafe(self) -> None:
        # Malformed URLs or unsupported schemes should be unsafe
        assert await self.pipe._is_safe_url("ftp://ftp.example.com") is False
        assert await self.pipe._is_safe_url("not_a_url") is False


@pytest.mark.unit
class TestScrapeUrl:
    """Test web scraping with BeautifulSoup parsing, timeouts, and headers."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    @pytest.mark.asyncio
    async def test_scrape_url_success(self) -> None:
        html_content = (
            "<html>"
            "<head><title>Test Title</title></head>"
            "<body>"
            "<script>alert(1);</script>"
            "<nav>Menu</nav>"
            "<p>Main body text of the article.</p>"
            "</body>"
            "</html>"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_aiter_text():
            yield html_content

        mock_response.aiter_text = mock_aiter_text
        mock_response.headers = {
            "content-type": "text/html; charset=utf-8",
            "content-length": str(len(html_content)),
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.stream = MagicMock()

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_client.stream.return_value = mock_stream_ctx

        # Use mock getaddrinfo to bypass real DNS / protect against SSRF checks
        with (
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
            patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls,
        ):
            result = await self.pipe._scrape_url("https://example.com")

            assert result is not None
            assert result["url"] == "https://example.com"
            assert result["title"] == "Test Title"
            # Noise elements (script, nav) should have been decomposed
            assert "alert" not in result["content"]
            assert "Menu" not in result["content"]
            assert "Main body text of the article." in result["content"]

            mock_client_cls.assert_called_once_with(timeout=5.0, follow_redirects=False)
            mock_client.stream.assert_called_once()
            _, kwargs = mock_client.stream.call_args
            assert "User-Agent" in kwargs["headers"]

    @pytest.mark.asyncio
    async def test_scrape_url_timeout(self) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.stream = MagicMock()
        mock_client.stream.side_effect = httpx.TimeoutException("Request timed out")

        with (
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await self.pipe._scrape_url("https://example.com")
            assert result is None

    @pytest.mark.asyncio
    async def test_scrape_url_unsafe_rejected(self) -> None:
        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await self.pipe._scrape_url("http://127.0.0.1")
            assert result is None
            mock_client_cls.assert_not_called()

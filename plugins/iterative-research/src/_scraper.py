from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


class ScraperMixin:
    """SSRF protection and web page content scraping utilities."""

    async def _is_safe_url(self, url: str) -> bool:
        """Validate URL to prevent SSRF by checking for private/reserved IP addresses."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            # If hostname is an IP, check it directly
            try:
                ip = ipaddress.ip_address(hostname)
                return not (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_unspecified
                )
            except ValueError:
                pass

            # Resolve domain to IP and check
            loop = asyncio.get_running_loop()
            addr_infos = await loop.run_in_executor(None, socket.getaddrinfo, hostname, None)
            for info in addr_infos:
                ip_str = info[4][0]
                ip = ipaddress.ip_address(ip_str)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_unspecified
                ):
                    return False
            return True
        except Exception as e:
            logger.error("Error validating URL %s: %s", url, e)
            return False

    async def _scrape_url(self, url: str) -> Optional[dict[str, str]]:
        """Scrape a single URL with SSRF protection and parse with BS4."""
        if not await self._is_safe_url(url):
            logger.warning("SSRF Protection: Rejected unsafe URL: %s", url)
            return None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()

                    # Check response Content-Type
                    content_type = response.headers.get("content-type", "").lower()
                    if not ("text/html" in content_type or "text/plain" in content_type):
                        logger.warning(
                            "Rejected URL %s with unsupported content-type: %s", url, content_type
                        )
                        return None

                    # Check Content-Length header if present
                    try:
                        content_length = int(response.headers.get("content-length", 0))
                    except ValueError:
                        content_length = 0

                    max_size = 2 * 1024 * 1024  # 2MB
                    if content_length > max_size:
                        logger.warning(
                            "Rejected URL %s: Content-Length %d exceeds 2MB limit",
                            url,
                            content_length,
                        )
                        return None

                    # Stream-read chunks up to max_size limit
                    chunks = []
                    bytes_read = 0
                    async for chunk in response.aiter_text():
                        chunks.append(chunk)
                        bytes_read += len(chunk.encode("utf-8", errors="ignore"))
                        if bytes_read > max_size:
                            logger.warning(
                                "Truncated content stream for %s because it exceeded 2MB limit", url
                            )
                            break

                    html_text = "".join(chunks)

                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(html_text, "html.parser")

                    # Remove noise elements
                    for script in soup(
                        ["script", "style", "nav", "footer", "header", "aside", "form"]
                    ):
                        script.decompose()

                    # Extract text
                    text = soup.get_text(separator=" ")
                    # Clean up whitespace
                    text = " ".join(text.split())

                    # Truncate to a reasonable length to avoid overwhelming the LLM
                    if len(text) > 8000:
                        text = text[:8000] + "... [truncated]"

                    title = soup.title.string.strip() if soup.title else "No Title"
                    return {"url": url, "title": title, "content": text}
        except Exception as e:
            logger.warning("Failed to scrape URL %s: %s", url, e)
            return None

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

    def _is_safe_url(self, url: str) -> bool:
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
            addr_infos = socket.getaddrinfo(hostname, None)
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
        if not self._is_safe_url(url):
            logger.warning("SSRF Protection: Rejected unsafe URL: %s", url)
            return None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # Parse with BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove noise elements
                for script in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
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

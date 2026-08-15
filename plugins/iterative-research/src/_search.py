import logging

import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


class SearchMixin:
    """Search engine integration for Tavily and SearXNG."""

    async def _search_query(self, query: str) -> list[dict[str, str]]:
        """Run search query against Tavily or SearXNG based on configuration."""
        if not hasattr(self, "valves"):
            return []

        # 1. Try Tavily
        if self.valves.TAVILY_API_KEY:
            try:
                headers = {"Content-Type": "application/json"}
                payload = {
                    "api_key": self.valves.TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.tavily.com/search", json=payload, headers=headers
                    )
                    response.raise_for_status()
                    data = response.json()
                    results = []
                    for r in data.get("results", []):
                        results.append(
                            {
                                "title": r.get("title", "No Title"),
                                "url": r.get("url", ""),
                                "snippet": r.get("content", ""),
                            }
                        )
                    return results
            except Exception as e:
                logger.error("Tavily search failed for query '%s': %s", query, e)

        # 2. Try SearXNG
        if self.valves.SEARXNG_URL:
            try:
                headers = {
                    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{self.valves.SEARXNG_URL.rstrip('/')}/search",
                        params={"q": query, "format": "json"},
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                    results = []
                    for r in data.get("results", []):
                        results.append(
                            {
                                "title": r.get("title", "No Title"),
                                "url": r.get("url", ""),
                                "snippet": r.get("content", ""),
                            }
                        )
                    return results
            except Exception as e:
                logger.error("SearXNG search failed for query '%s': %s", query, e)

        return []

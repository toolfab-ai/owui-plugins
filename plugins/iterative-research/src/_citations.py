from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable


class CitationsMixin:
    """Utilities for emitting citation events to Open WebUI."""

    async def _emit_citation(
        self,
        scraped: dict[str, str],
        emitter: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Emit citation events to Open WebUI for a scraped page."""
        url = scraped.get("url", "")
        title = scraped.get("title", "Untitled")
        content = scraped.get("content", "")
        if not url:
            return
        await emitter(
            {
                "type": "citation",
                "data": {
                    "document": [content[:500]],
                    "metadata": [
                        {
                            "date_accessed": datetime.utcnow().isoformat(),
                            "source": title,
                            "url": url,
                        }
                    ],
                    "source": {"name": title, "url": url},
                },
            }
        )

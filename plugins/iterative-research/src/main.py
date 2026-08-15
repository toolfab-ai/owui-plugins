import asyncio
import logging
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional, Union

try:
    from fastapi import Request
except ImportError:

    class Request:  # type: ignore[no-redef]
        """Fallback for environments without fastapi (such as local testing)."""

        pass


from ._citations import CitationsMixin
from ._llm import LLMMixin
from ._research import ResearchMixin
from ._scraper import ScraperMixin
from ._search import SearchMixin
from ._synthesis import SynthesisMixin
from ._updates import UpdateMixin
from ._valves import Valves

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ========================================================================
# PIPE CLASS
# ========================================================================


class Pipe(
    ScraperMixin,
    SearchMixin,
    LLMMixin,
    CitationsMixin,
    ResearchMixin,
    SynthesisMixin,
    UpdateMixin,
):
    """Iterative Deep Research Agent Pipe."""

    Valves = Valves

    def __init__(self) -> None:
        self.valves = self.Valves()

    def pipes(self) -> list[dict[str, str]]:
        """Register the custom Deep Research model."""
        return [
            {
                "id": "iterative_research_pipe",
                "name": "Iterative Deep Research Agent",
            }
        ]

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: Optional[dict[str, Any]] = None,
        __request__: Optional[Request] = None,
        __event_emitter__: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Main entry point for executing autonomous multi-turn deep research.

        Supports both streaming (returns an AsyncGenerator) and non-streaming
        (returns a compiled string response) dynamically depending on client configuration.
        """
        if __event_emitter__:
            asyncio.create_task(self._check_for_updates(__user__, __event_emitter__))

        stream = body.get("stream", False)
        if stream:
            return self._stream_research(body, __user__, __request__, __event_emitter__)
        else:
            # Consume the generator internally to accumulate the complete response string
            final_report = []
            async for chunk in self._stream_research(
                body, __user__, __request__, __event_emitter__
            ):
                final_report.append(chunk)
            return "".join(final_report)

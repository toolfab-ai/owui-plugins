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
from ._valves import UserValves, Valves

# ---------------------------------------------------------------------------
# Configuration Mapping: key -> (Valves_attr, UserValves_attr)
# ---------------------------------------------------------------------------
_CONFIG_MAP: dict[str, tuple[str, str]] = {
    "max_steps": ("MAX_STEPS", "max_steps"),
    "max_pages_to_scrape": ("MAX_PAGES_TO_SCRAPE", "max_pages_to_scrape"),
    "co_storm_steering": ("CO_STORM_STEERING", "co_storm_steering"),
}

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
    UserValves = UserValves

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

    def _get_config(self, key: str, user_valves: Optional[Union[UserValves, dict]] = None) -> Any:
        """Resolve a single config value: UserValves (if set) > Admin Valves.

        UserValves can be a Pydantic object or a dictionary.
        """
        mapping = _CONFIG_MAP.get(key, (key, key))
        valve_attr, user_attr = mapping

        if user_valves is not None:
            # Handle both dictionary and object formats
            if isinstance(user_valves, dict):
                value = user_valves.get(user_attr)
            else:
                value = getattr(user_valves, user_attr, None)

            if value is not None and str(value).strip().lower() not in ("", "default"):
                admin_val = getattr(self.valves, valve_attr)
                # Type casting based on Admin Valve type
                if isinstance(admin_val, bool):
                    return str(value).strip().lower() in ("true", "1", "yes", "on")
                if isinstance(admin_val, int):
                    try:
                        return int(str(value).strip())
                    except (ValueError, TypeError):
                        return admin_val
                return value

        return getattr(self.valves, valve_attr)

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: Optional[dict[str, Any]] = None,
        __request__: Optional[Request] = None,
        __event_emitter__: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
        __user_valves__: Optional[Union[UserValves, dict]] = None,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Main entry point for executing autonomous multi-turn deep research.

        Supports both streaming (returns an AsyncGenerator) and non-streaming
        (returns a compiled string response) dynamically depending on client configuration.
        """
        # Resolve valves: prefer explicit __user_valves__, fallback to __user__["valves"]
        user_valves = __user_valves__
        if user_valves is None and __user__ and "valves" in __user__:
            user_valves = __user__["valves"]

        stream = body.get("stream", False)
        if stream:
            return self._stream_research(
                body, __user__, __request__, __event_emitter__, user_valves
            )
        else:
            # Consume the generator internally to accumulate the complete response string
            final_report = []
            async for chunk in self._stream_research(
                body, __user__, __request__, __event_emitter__, user_valves
            ):
                final_report.append(chunk)
            return "".join(final_report)

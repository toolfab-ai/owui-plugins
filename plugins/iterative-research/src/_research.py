from __future__ import annotations

import asyncio
import inspect
import logging
import re
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional

try:
    from fastapi import Request
except ImportError:

    class Request:  # type: ignore[no-redef]
        """Fallback for environments without fastapi (such as local testing)."""

        pass


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


class ResearchMixin:
    """Core iterative research loop and strategy planning."""

    async def _stream_research(
        self,
        body: dict[str, Any],
        __user__: Optional[dict[str, Any]] = None,
        __request__: Optional[Request] = None,
        __event_emitter__: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
        __user_valves__: Optional[Any] = None,
    ) -> AsyncGenerator[str, None]:
        """Internal generator for executing the deep research and streaming chunk tokens."""
        messages = body.get("messages", [])
        if not messages:
            yield "No messages provided."
            return

        # Resolve configuration
        max_steps = self._get_config("max_steps", __user_valves__)
        max_pages = self._get_config("max_pages_to_scrape", __user_valves__)
        co_storm = self._get_config("co_storm_steering", __user_valves__)
        tavily_key = self.valves.TAVILY_API_KEY
        searxng_url = self.valves.SEARXNG_URL

        # Find original query (first user message)
        original_query = ""
        for msg in messages:
            if msg.get("role") == "user":
                original_query = msg.get("content", "")
                break

        # Find latest user message (could be steering feedback if messages > 1)
        latest_user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                latest_user_message = msg.get("content", "")
                break

        # Check if this is a continuation of interactive steering
        is_continuation = len(messages) > 1 and co_storm
        steering_feedback = latest_user_message if is_continuation else ""

        # Load user context safely
        user_id = __user__.get("id") if __user__ else None
        user_obj = None
        if user_id:
            # We use noqa: N806 for variable naming since Users is a class name being imported dynamically.
            Users = None  # noqa: N806
            try:
                from open_webui.models.users import Users
            except ImportError:
                try:
                    from open_webui.apps.webui.models.users import Users
                except ImportError:
                    logger.warning("Could not import Users from open_webui")
                    Users = None  # noqa: N806

            if Users is not None:
                try:
                    res = Users.get_user_by_id(user_id)
                    if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                        user_obj = await res
                    else:
                        user_obj = res
                except Exception as e:
                    logger.warning("Could not load user object: %s", e)

        # Warn if no search engine configured
        if not tavily_key and not searxng_url:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": (
                                "Warning: No search engine (Tavily/SearXNG) configured. "
                                "Relying on internal knowledge."
                            ),
                            "done": False,
                        },
                    }
                )

        backend_model = await self._get_backend_model(body)
        scraped_sources: dict[str, dict[str, str]] = {}

        # Check for updates and show notification at the very top of the response
        update_msg = await self._get_update_notification(__user__)
        if update_msg:
            yield f"{update_msg}\n\n"

        start_step = 1
        if is_continuation:
            # Reconstruct scraped sources from history to avoid repeating scrapes
            for msg in messages:
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    found_urls = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", content)
                    for title, url in found_urls:
                        scraped_sources[url] = {
                            "url": url,
                            "title": title,
                            "content": f"Already cited in previous turn: {title}",
                        }
            start_step = 2

        # Multi-turn search and scrape loop
        for step in range(start_step, max_steps + 1):
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Step {step}/{max_steps}: Planning search strategy...",
                            "done": False,
                        },
                    }
                )

            # Summarize current state
            if scraped_sources:
                scraped_summary = "\n".join(
                    [
                        f"- [{info['title']}]({url}) (Length: {len(info['content'])} chars)"
                        for url, info in scraped_sources.items()
                    ]
                )
            else:
                scraped_summary = "None (No pages scraped yet)."

            dt_context = self._get_datetime_context()
            system_prompt = (
                f"{dt_context}"
                "You are an expert autonomous deep research planning agent.\n"
                "Your goal is to formulate a search strategy to answer the user's query.\n"
                "You identify what is already known and specify 'information gaps' that still need researching.\n"
                "Then you generate 1 to 3 targeted, highly effective search queries to find the missing information.\n"
                "If you determine that the currently scraped sources are fully sufficient to answer the user's query comprehensively "
                "without any remaining gaps, return empty lists for both 'gaps' and 'queries' to signal early completion."
            )

            user_prompt = (
                f"User original query: {original_query}\n"
                f"Active research step: {step} of {max_steps}\n"
            )
            if is_continuation and step == start_step:
                user_prompt += f"User intermediate steering feedback: {steering_feedback}\n"
            user_prompt += (
                f"Currently scraped sources:\n{scraped_summary}\n\n"
                "Identify outstanding gaps and generate up to 3 distinct search queries to search the web.\n"
                "If the existing sources are fully sufficient to answer the user's query comprehensively, return empty lists for both 'gaps' and 'queries'.\n"
                "Format your response strictly as a JSON object with keys 'gaps' (list of strings) and 'queries' (list of strings).\n"
                "Example output:\n"
                "```json\n"
                "{\n"
                '  "gaps": ["Need current stock price of Apple", "Need Q3 revenue figure"],\n'
                '  "queries": ["Apple stock price 2026", "Apple Q3 2026 earnings revenue"]\n'
                "}\n"
                "```\n"
                "Provide ONLY the JSON block."
            )

            # Yield intermediate thinking blocks
            yield "<thinking>\n"
            yield f"### Step {step}/{max_steps}: Planning & Formulation\n"

            planning_response = await self._call_llm(
                __request__, user_obj, system_prompt, user_prompt, backend_model
            )
            plan = self._parse_json_completions(planning_response)
            gaps = plan.get("gaps", [])
            queries = plan.get("queries", [])

            if not queries:
                yield "#### All Information Gaps Resolved.\n"
                yield "The agent has determined that the gathered information is fully sufficient. Ending research loop early.\n"
                yield "</thinking>\n\n"
                break

            yield "#### Information Gaps Identified:\n"
            for gap in gaps:
                yield f"- {gap}\n"

            yield "\n#### Generated Web Search Queries:\n"
            for q in queries:
                yield f"- `{q}`\n"
            yield "\n"

            # Execute searches
            all_search_results = []
            if queries:
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Step {step}/{max_steps}: Searching the web...",
                                "done": False,
                            },
                        }
                    )

                for q in queries:
                    yield f"Searching: `{q}`...\n"
                    search_res = await self._search_query(q, __user_valves__)
                    yield f"  Found {len(search_res)} results.\n"
                    all_search_results.extend(search_res)

            # Deduplicate and check SSRF
            unique_results = {}
            for res in all_search_results:
                url = res.get("url")
                if url and url not in scraped_sources and url not in unique_results:
                    if await self._is_safe_url(url):
                        unique_results[url] = res
                    else:
                        yield f"  SSRF check skipped unsafe URL: {url}\n"

            # Perform parallel page scraping
            urls_to_scrape = list(unique_results.keys())[:max_pages]
            if urls_to_scrape:
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": (
                                    f"Step {step}/{max_steps}: Scraping "
                                    f"{len(urls_to_scrape)} pages in parallel..."
                                ),
                                "done": False,
                            },
                        }
                    )

                yield f"\n#### Scraping {len(urls_to_scrape)} pages in parallel:\n"
                for u in urls_to_scrape:
                    yield f"- `{u}`\n"
                yield "\n"

                scrape_tasks = [self._scrape_url(u) for u in urls_to_scrape]
                scraped_res_list = await asyncio.gather(*scrape_tasks)

                for scraped in scraped_res_list:
                    if scraped:
                        u = scraped["url"]
                        scraped_sources[u] = scraped
                        if __event_emitter__:
                            await self._emit_citation(scraped, __event_emitter__)
                        yield (
                            f"Successfully scraped `{scraped['title']}` "
                            f"({len(scraped['content'])} chars)\n"
                        )
            else:
                yield "No new URLs found to scrape in this step.\n"

            yield "</thinking>\n\n"

            # Co-STORM Steering Pause
            if co_storm and step < max_steps:
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": "Pausing for interactive steering feedback...",
                                "done": True,
                            },
                        }
                    )
                yield f"### 📊 Intermediate Research Findings (Step {step}/{max_steps})\n\n"
                yield "I have completed the first turn of research. Here is a summary of the sources gathered so far:\n\n"
                for url, info in scraped_sources.items():
                    yield f"- **[{info['title']}]({url})**  \n"
                    snippet = (
                        info["content"][:300] + "..."
                        if len(info["content"]) > 300
                        else info["content"]
                    )
                    yield f"  *Summary*: {snippet}\n\n"

                yield "---\n\n"
                yield "### 🧭 Human-in-the-Loop Steering\n"
                yield "Please provide feedback on the direction of the research. You can:\n"
                yield "1. Specify particular subtopics to focus on or dig deeper into.\n"
                yield "2. Provide additional keywords or specific questions.\n"
                yield (
                    "3. Type **'continue'** (or leave it blank/reply) to proceed with "
                    "the autonomous plan.\n\n"
                )
                yield (
                    "*The research loop is paused. Awaiting your input to continue "
                    "to the next step.*"
                )
                return

        # Hand over to synthesis
        async for chunk in self._synthesize_report(
            original_query, scraped_sources, __request__, user_obj, __event_emitter__, backend_model
        ):
            yield chunk

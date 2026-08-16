"""
title: Iterative Deep Research Agent
author: toolfab-ai
author_url: https://github.com/toolfab-ai/
version: 0.9.2
requirements: httpx, beautifulsoup4
description: Autonomous multi-turn web search & scraping loops to synthesize detailed cited research-reports.
license: MIT
github: https://github.com/toolfab-ai/owui-plugins
"""

from __future__ import annotations

class Pipe: pass


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



import json
import logging
import re
from datetime import datetime
from typing import Any

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


class LLMMixin:
    """LLM orchestration, model resolution, and response parsing utilities."""

    def _get_datetime_context(self) -> str:
        """Return a standard UTC date-time string for prompt injection."""
        now = datetime.utcnow()
        return f"Current Date: {now.strftime('%Y-%m-%d')} ({now.strftime('%A')}) UTC\n"

    async def _get_backend_model(self, body: dict[str, Any]) -> str:
        """Resolve the best backend model to use for completion."""
        # 1. Check if MODEL is configured in valves
        if hasattr(self, "valves") and self.valves.MODEL:
            return self.valves.MODEL

        # 2. Check if we can find a non-pipe model in the workspace
        # We use noqa: N806 for variable naming since Models is a class name being imported dynamically.
        Models = None  # noqa: N806
        try:
            from open_webui.models.models import Models
        except ImportError:
            try:
                from open_webui.apps.webui.models.models import Models
            except ImportError:
                logger.warning("Could not import Models from open_webui")
                Models = None  # noqa: N806

        if Models is not None:
            try:
                all_models = await Models.get_all_models()
                for m in all_models:
                    m_id = getattr(m, "id", None)
                    if not m_id and isinstance(m, dict):
                        m_id = m.get("id")
                    if (
                        m_id
                        and m_id != "iterative_research"
                        and m_id != "iterative_research_pipe"
                        and "pipe" not in m_id
                    ):
                        return m_id
            except Exception as e:
                logger.warning("Could not list models from Models: %s", e)

        # 3. Fallback to some common default model ID
        return "gpt-4o-mini"

    async def _call_llm(
        self,
        __request__: Request,
        user_obj: Any,
        system_prompt: str,
        user_prompt: str,
        model_id: str,
    ) -> str:
        """Invoke generate_chat_completion with system and user prompts."""
        generate_chat_completion = None
        try:
            from open_webui.utils.chat import generate_chat_completion
        except ImportError:
            try:
                from open_webui.apps.webui.utils.chat import generate_chat_completion
            except ImportError:
                logger.warning("Could not import generate_chat_completion from open_webui")
                generate_chat_completion = None

        if generate_chat_completion is None:
            logger.warning("generate_chat_completion is None, skipping LLM call")
            return "Warning: Chat completion engine not available."

        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        try:
            response = await generate_chat_completion(__request__, payload, user_obj)
            if isinstance(response, str):
                return response
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return response.get("content", str(response))
            return str(response)
        except Exception as e:
            logger.exception("LLM generation failed: %s", e)
            return ""

    def _parse_json_completions(self, text: str) -> dict[str, Any]:
        """Parse JSON response from LLM, handling markdown blocks and partial JSON."""
        # Try to find JSON code block
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            # Try to find any curly brace block
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                text = match.group(1)

        text = text.strip()
        try:
            return json.loads(text)
        except Exception as e:
            logger.warning("Failed to parse JSON: %s, text: %s", e, text)
            # If fallback fails, parse queries manually
            queries = []
            for line in text.split("\n"):
                line = line.strip()
                if (
                    line.startswith("-")
                    or line.startswith("*")
                    or line.startswith("1.")
                    or line.startswith("2.")
                    or line.startswith("3.")
                ):
                    q = re.sub(r"^[-*\d.\s]+", "", line).strip().strip('"')
                    if q:
                        queries.append(q)
            return {"gaps": ["Manual parsing fallback"], "queries": queries[:3]}



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


import logging
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


class SearchMixin:
    """Search engine integration for Tavily and SearXNG."""

    async def _search_query(
        self, query: str, user_valves: Optional[Any] = None
    ) -> list[dict[str, str]]:
        """Run search query against Tavily or SearXNG based on configuration."""
        if not hasattr(self, "valves"):
            return []

        # Resolve keys/URLs (Admin only)
        tavily_key = self.valves.TAVILY_API_KEY
        searxng_url = self.valves.SEARXNG_URL

        # 1. Try Tavily
        if tavily_key:
            try:
                headers = {"Content-Type": "application/json"}
                payload = {
                    "api_key": tavily_key,
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
        if searxng_url:
            try:
                headers = {
                    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{searxng_url.rstrip('/')}/search",
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


from typing import Any, AsyncGenerator, Awaitable, Callable, Optional

try:
    from fastapi import Request
except ImportError:

    class Request:  # type: ignore[no-redef]
        """Fallback for environments without fastapi (such as local testing)."""

        pass


class SynthesisMixin:
    """Synthesis logic for compiling research sources into a final report."""

    async def _synthesize_report(
        self,
        original_query: str,
        scraped_sources: dict[str, dict[str, str]],
        __request__: Optional[Request],
        user_obj: Any,
        __event_emitter__: Optional[Callable[[dict[str, Any]], Awaitable[None]]],
        backend_model: str,
    ) -> AsyncGenerator[str, None]:
        """Final synthesis of all gathered research information into a cited report."""
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Synthesizing final research report...",
                        "done": False,
                    },
                }
            )

        yield "<thinking>\n"
        yield "### Final Synthesis\n"
        yield (
            f"Compiling information from {len(scraped_sources)} sources into "
            "a comprehensive cited report...\n"
        )
        yield "</thinking>\n\n"

        sources_text = ""
        for idx, (url, info) in enumerate(scraped_sources.items(), 1):
            sources_text += (
                f"Source [{idx}]:\nTitle: {info['title']}\nURL: {url}\n"
                f"Content:\n{info['content']}\n\n"
            )

        dt_context = self._get_datetime_context()
        system_prompt = (
            f"{dt_context}"
            "You are an expert research synthesizer. Your goal is to write a comprehensive, "
            "authoritative, highly structured, and professionally formatted research report "
            "based on the provided scraped sources.\n"
            "Include in-text citations like [1], [2], etc., mapping to the respective sources.\n"
            "At the end of your report, provide a clean 'Sources' section with a numbered list "
            "matching the citations."
        )

        user_prompt = (
            f"User Research Query: {original_query}\n\n"
            f"Scraped Context:\n{sources_text}\n\n"
            "Write the comprehensive research report now. Follow the requirements strictly."
        )

        report = await self._call_llm(
            __request__, user_obj, system_prompt, user_prompt, backend_model
        )
        yield report

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Deep Research Report complete!",
                        "done": True,
                    },
                }
            )



import logging

# --- Shared: update_notifier.notifier ---

import logging
import re
import time
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_REPO: str = "toolfab-ai/owui-plugins"
RELEASE_TAG_PREFIX: str = ""
CACHE_EXPIRY_SECONDS: float = 3600.0  # Cache GitHub API responses for 1 hour

ADMIN_UPDATE_MSG: str = (
    "**New version available**: [{plugin_name} {version}]({url}) "
    "Update the plugin for the latest fixes."
)
USER_UPDATE_MSG: str = (
    "**New version available**: {plugin_name}. Contact your administrator to update the plugin."
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ========================================================================
# SHARED UPDATE NOTIFIER MIXIN
# ========================================================================


class UpdateMixin:
    """Mixin for background checking of new releases on GitHub."""

    _GITHUB_REPO: str = GITHUB_REPO
    _RELEASE_TAG_PREFIX: str = RELEASE_TAG_PREFIX
    _CACHE_EXPIRY_SECONDS: float = CACHE_EXPIRY_SECONDS
    _ADMIN_UPDATE_MSG: str = ADMIN_UPDATE_MSG
    _USER_UPDATE_MSG: str = USER_UPDATE_MSG

    def _get_metadata_field(self, field: str) -> Optional[str]:
        """Retrieve a specific field from the module docstring metadata."""
        import inspect
        import sys

        # Try to find the module by its name in sys.modules
        mod_name = self.__class__.__module__
        mod = sys.modules.get(mod_name)
        doc = getattr(mod, "__doc__", None) if mod else None

        if not doc:
            # Fallback: search sys.modules by filename
            try:
                mod_file = inspect.getfile(self.__class__)
                for m in sys.modules.values():
                    if getattr(m, "__file__", None) == mod_file:
                        doc = getattr(m, "__doc__", None)
                        if doc:
                            break
            except Exception:
                pass

        if not doc:
            # Final fallback to globals (works if inlined)
            doc = globals().get("__doc__")

        if doc:
            match = re.search(rf"{field}:\s*([^\n\r]+)", doc)
            if match:
                return match.group(1).strip()
        return None

    def _get_current_version(self) -> str:
        """Retrieve the plugin version from the module docstring."""
        return self._get_metadata_field("version") or "0.1.0"

    def _get_plugin_name(self) -> str:
        """Retrieve the plugin title from the module docstring."""
        return self._get_metadata_field("title") or "Plugin"

    def _parse_version(self, v_str: str) -> tuple[int, int, int, int, int]:
        """Parse version string into a 5-tuple for semver comparison.

        Tuple format: (major, minor, patch, type_weight, pre_release_version)
        Weights: dev=0, alpha=1, beta=2, rc=3, stable=4
        """
        try:
            # Strip any leading 'v'
            v_str = v_str.lstrip("v").lower()

            # Base version (major.minor.patch)
            base_match = re.match(r"^(\d+)\.(\d+)\.(\d+)", v_str)
            if not base_match:
                return (0, 0, 0, 0, 0)

            major, minor, patch = map(int, base_match.groups())

            # Determine type weight and pre-release number
            type_weight = 4  # Default to stable
            pre_num = 0

            if "-" in v_str:
                suffix = v_str.split("-", 1)[1]
                if "dev" in suffix:
                    type_weight = 0
                elif "alpha" in suffix:
                    type_weight = 1
                elif "beta" in suffix:
                    type_weight = 2
                elif "rc" in suffix:
                    type_weight = 3

                # Extract number from suffix (e.g., beta.1 -> 1)
                num_match = re.search(r"(\d+)", suffix)
                if num_match:
                    pre_num = int(num_match.group(1))

            return (major, minor, patch, type_weight, pre_num)
        except Exception as e:
            logger.warning("Failed to parse version string %s: %s", v_str, e)
            return (0, 0, 0, 0, 0)

    async def _get_update_notification(
        self,
        __user__: Optional[dict[str, Any]],
    ) -> Optional[str]:
        """Check for updates and return a formatted Markdown notification if available."""
        if not __user__:
            return None

        # Check if notifications are disabled via valves
        if hasattr(self, "valves") and not getattr(
            self.valves, "ENABLE_UPDATE_NOTIFICATIONS", True
        ):
            return None

        # Lazy initialization of state on the instance
        if not hasattr(self, "_releases_cache"):
            self._releases_cache = None
        if not hasattr(self, "_last_update_check_time"):
            self._last_update_check_time = 0.0

        role = __user__.get("role", "user")
        releases = self._releases_cache
        now = time.time()

        # Check if cache expired or not checked yet
        if not releases or (now - self._last_update_check_time > self._CACHE_EXPIRY_SECONDS):
            url = f"https://api.github.com/repos/{self._GITHUB_REPO}/releases"
            logger.debug("Querying GitHub Releases API for updates: %s", url)
            headers = {
                "User-Agent": "OpenWebUI-Plugin-Update-Checker",
                "Accept": "application/vnd.github+json",
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    releases = response.json()

                    if isinstance(releases, list):
                        self._releases_cache = releases
                        self._last_update_check_time = now
            except Exception as e:
                logger.warning("Failed to check for updates: %s", e)

        if not isinstance(releases, list):
            return None

        check_previews = hasattr(self, "valves") and getattr(
            self.valves, "CHECK_PREVIEW_RELEASES", False
        )

        current_version_str = self._get_current_version()
        current_version = self._parse_version(current_version_str)
        plugin_name = self._get_plugin_name()

        latest_release = None
        latest_version = (0, 0, 0, 0, 0)

        for release in releases:
            tag_name = release.get("tag_name", "")
            if not tag_name:
                continue

            # Check if tag matches our prefix
            if self._RELEASE_TAG_PREFIX and not tag_name.startswith(self._RELEASE_TAG_PREFIX):
                continue

            # Extract version string
            candidate_version_str = tag_name[len(self._RELEASE_TAG_PREFIX) :]
            is_preview = release.get("prerelease", False)

            if is_preview and not check_previews and role != "admin":
                continue

            candidate_version = self._parse_version(candidate_version_str)
            if candidate_version > latest_version:
                latest_version = candidate_version
                latest_release = release

        if not latest_release:
            return None

        latest_tag = latest_release.get("tag_name", "")
        # Extract version part from tag for display (strip prefix)
        display_version = latest_tag[len(self._RELEASE_TAG_PREFIX) :]
        html_url = latest_release.get("html_url", "")

        if latest_version > current_version:
            if role == "admin":
                return self._ADMIN_UPDATE_MSG.format(
                    plugin_name=plugin_name, version=display_version, url=html_url
                )
            else:
                return self._USER_UPDATE_MSG.format(
                    plugin_name=plugin_name, version=display_version
                )

        return None

# --- End Shared ---

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ========================================================================
# UPDATE CHECK MIXIN
# ========================================================================


class UpdateMixin(UpdateMixin):
    """Mixin for background checking of new releases on GitHub."""

    _RELEASE_TAG_PREFIX: str = "iterative-research/"


from pydantic import BaseModel, Field


class Valves(BaseModel):
    """Admin-configurable settings for the Iterative Research Pipe."""

    ENABLE_UPDATE_NOTIFICATIONS: bool = Field(
        default=True,
        description="If enabled, the plugin will check GitHub in the background for new releases and notify the admin.",
    )
    CHECK_PREVIEW_RELEASES: bool = Field(
        default=False,
        description="If enabled, check for preview/dev/pre-release versions on GitHub as well.",
    )
    SEARXNG_URL: str = Field(
        default="",
        description="The base URL of your SearXNG instance (e.g., http://searxng:8080). "
        "Used as a search engine for discovering new information.",
    )
    TAVILY_API_KEY: str = Field(
        default="",
        description="API key for Tavily Search (https://tavily.com). "
        "If provided, Tavily will be used as the primary or fallback search engine.",
    )
    MODEL: str = Field(
        default="",
        description="The internal LLM model ID to use for research planning, gap analysis, "
        "and final synthesis. If left empty, the plugin will attempt to auto-detect "
        "an available model from the workspace.",
    )
    MAX_STEPS: int = Field(
        default=3,
        description="Maximum number of iterative search-and-scraping loops to perform. "
        "Higher values lead to deeper research but take more time.",
        ge=1,
        le=10,
    )
    MAX_PAGES_TO_SCRAPE: int = Field(
        default=3,
        description="Maximum number of new web pages to scrape and analyze in each research step.",
        ge=1,
        le=10,
    )
    CO_STORM_STEERING: bool = Field(
        default=False,
        description="If enabled, the agent will pause after the first research step to "
        "allow the user to provide interactive steering feedback (Co-STORM style).",
    )


class UserValves(BaseModel):
    """Per-user settings for the Iterative Research Pipe."""

    max_steps: str = Field(
        default="default",
        description="Maximum iterative search steps (e.g., 5). Variants: 1-10. Use 'default' to inherit admin setting.",
    )
    max_pages_to_scrape: str = Field(
        default="default",
        description="Max pages to scrape per iteration (e.g., 5). Variants: 1-10. Use 'default' to inherit admin setting.",
    )
    co_storm_steering: str = Field(
        default="default",
        description="Enable Co-STORM steering pause (e.g., true). Variants: true, false. Use 'default' to inherit admin setting.",
    )


import logging
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional, Union

try:
    from fastapi import Request
except ImportError:

    class Request:  # type: ignore[no-redef]
        """Fallback for environments without fastapi (such as local testing)."""

        pass



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

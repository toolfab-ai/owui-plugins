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
        if not report or not report.strip():
            yield (
                f"> ⚠️ **Error**: Final synthesis failed due to an empty response "
                f"from model '{backend_model}'.\n"
            )
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": (
                                f"Critical Error: Final synthesis failed due to an empty "
                                f"response from model '{backend_model}'."
                            ),
                            "done": True,
                        },
                    }
                )
            return

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

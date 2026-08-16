from __future__ import annotations

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
        """Resolve the best backend model to use for completion.

        Returns "" if no model is configured.
        """
        if hasattr(self, "valves") and self.valves.MODEL:
            return self.valves.MODEL
        return ""

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

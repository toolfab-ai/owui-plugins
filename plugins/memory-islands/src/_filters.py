from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from open_webui.models.chats import Chats
except ImportError:
    try:
        from open_webui.apps.webui.models.chats import Chats
    except ImportError:
        Chats = None  # noqa: N806

try:
    from open_webui.models.users import Users
except ImportError:
    try:
        from open_webui.apps.webui.models.users import Users
    except ImportError:
        Users = None  # noqa: N806


# ---------------------------------------------------------------------------
# Extraction throttle (best-effort, module-level)
# ---------------------------------------------------------------------------
# The Filter instance is a singleton in Open WebUI, so request-scoped state must
# NOT live on ``self``. This per-folder exchange counter is a deliberate
# best-effort throttle used to gate EXTRACTION_INTERVAL.
_EXCHANGE_COUNTS: Dict[str, int] = {}
_COUNTER_LOCK: threading.Lock = threading.Lock()

_EXTRACTION_TIMEOUT_SECONDS: int = 60


def _should_extract(folder_id: str, interval: int) -> bool:
    """Return True when extraction should run for ``folder_id`` after this exchange.

    Best-effort throttle: extraction runs on every ``interval``-th exchange for the
    folder (default 1 = every exchange).
    """
    step: int = max(1, interval)
    with _COUNTER_LOCK:
        count: int = _EXCHANGE_COUNTS.get(folder_id, 0) + 1
        _EXCHANGE_COUNTS[folder_id] = count
        return count % step == 0


class FilterMixin:
    """Filter hooks: inlet, outlet, folder resolution and LLM fact extraction."""

    def __init__(self) -> None:
        self._learning_tasks: set[asyncio.Task] = set()

    async def _resolve_folder(
        self, body: Dict[str, Any], user_id: Optional[str] = None
    ) -> Optional[str]:
        """Resolve the active folder_id: prefer the payload metadata, fall back to the Chats model.

        OWUI's ``/api/chat/completions`` handler pops ``folder_id`` and ``chat_id`` out of the
        top-level form_data and re-injects them into ``body["metadata"]`` (keys
        ``metadata.folder_id``, ``metadata.chat_id``, ``metadata.user_id``). The top-level
        ``body.get("folder_id")`` / ``body.get("chat_id")`` are therefore always None inside
        ``inlet``. We read from ``metadata`` first, then fall back to any legacy top-level
        keys for older OWUI versions, and finally try the Chats model.
        """
        metadata: Dict[str, Any] = body.get("metadata") or {}

        # 1. Modern OWUI carries folder_id inside the payload metadata.
        folder_id: Optional[str] = metadata.get("folder_id") or body.get("folder_id")
        if folder_id:
            return folder_id

        # 2. Legacy fallback through the Chats model.
        chat_id: Optional[str] = metadata.get("chat_id") or body.get("chat_id")
        if not chat_id or Chats is None or not user_id:
            return None
        try:
            res = Chats.get_chat_folder_id(chat_id, user_id)
            if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                return await res
            return res
        except Exception:
            logger.exception("Failed to resolve folder_id via Chats model.")
            return None

    def _resolve_extraction_model(self, body: Dict[str, Any]) -> str:
        """Resolve the model id for extraction: EXTRACTION_MODEL valve, else the chat's model."""
        configured: str = (self.valves.EXTRACTION_MODEL or "").strip()
        if configured:
            return configured
        return str(body.get("model") or "").strip()

    async def _resolve_user_obj(self, user_id: Optional[str]) -> Any:
        """Resolve the user object for LLM calls via the resilient Users import."""
        if not user_id or Users is None:
            return None
        try:
            res = Users.get_user_by_id(user_id)
            if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                return await res
            return res
        except Exception:
            logger.exception("Failed to resolve user object for fact extraction.")
            return None

    def _build_extraction_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """Build the extraction prompt content from the last user and assistant messages."""
        last_user: str = ""
        last_assistant: str = ""
        for msg in messages:
            role: str = msg.get("role", "")
            content: str = msg.get("content", "")
            if role == "user":
                last_user = content
            elif role == "assistant":
                last_assistant = content
        parts: List[str] = []
        if last_user:
            parts.append(f"User: {last_user}")
        if last_assistant:
            parts.append(f"Assistant: {last_assistant}")
        return "\n".join(parts)

    def _extract_response_text(self, response: Any) -> str:
        """Extract plain text content from a ``generate_chat_completion`` response."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return response.get("content", str(response))
        return str(response)

    def _parse_extraction_response(self, text: str) -> List[str]:
        """Strictly parse the LLM extraction output into a list of fact strings.

        Handles ```json fences and partial JSON. ``<NONE>`` or invalid JSON yields no
        facts (with a warning). Non-string entries are discarded.
        """
        stripped: str = (text or "").strip()
        if not stripped or stripped.upper() == "<NONE>":
            return []

        # Strip ```json ... ``` fences.
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()

        # Fall back to the largest JSON array block when the model wraps output in prose.
        if not stripped.startswith("["):
            match = re.search(r"(\[.*\])", stripped, re.DOTALL)
            if match:
                stripped = match.group(1).strip()

        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse JSON from LLM extraction output")
            return []

        if not isinstance(data, list):
            logger.warning("LLM extraction output is not a JSON array; ignoring")
            return []

        facts: List[str] = []
        for entry in data:
            if isinstance(entry, str):
                cleaned: str = entry.strip()
                if cleaned:
                    facts.append(cleaned)
            else:
                logger.warning("Discarding non-string fact entry from extraction output")
        return facts

    async def _extract_facts_with_llm(
        self,
        folder_id: str,
        body: Dict[str, Any],
        user_id: Optional[str],
        __request__: Any,
    ) -> None:
        """Extract facts from the last exchange via the internal OWUI LLM engine.

        Runs as a background task so a slow or failing LLM call never blocks the
        chat pipeline. Uses the consolidated LLM error-handling pattern: resilient
        imports, availability checks, ``logger.exception`` on failure, safe default.
        """
        try:
            messages: List[Dict[str, Any]] = body.get("messages", [])
            exchange: str = self._build_extraction_prompt(messages)
            if not exchange:
                logger.info("No extractable exchange for folder %s; skipping.", folder_id)
                return

            # Resilient import of the internal generation engine (same mechanism
            # OWUI uses for title generation).
            generate_chat_completion: Any = None
            try:
                from open_webui.utils.chat import generate_chat_completion
            except ImportError:
                try:
                    from open_webui.apps.webui.utils.chat import generate_chat_completion
                except ImportError:
                    logger.warning("Could not import generate_chat_completion from open_webui")
                    generate_chat_completion = None

            if generate_chat_completion is None:
                logger.warning("generate_chat_completion is None, skipping fact extraction")
                return

            model_id: str = self._resolve_extraction_model(body)
            if not model_id:
                logger.warning("No extraction model resolved; skipping fact extraction.")
                return

            user_obj: Any = await self._resolve_user_obj(user_id)

            system_prompt: str = (
                "Extract facts worth remembering from the last exchange. "
                "Return ONLY a JSON array of strings, or <NONE> if there is "
                "nothing worth remembering."
            )
            payload: Dict[str, Any] = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": exchange},
                ],
                "temperature": 0.2,
                "stream": False,
            }
            try:
                response: Any = await asyncio.wait_for(
                    generate_chat_completion(__request__, payload, user_obj),
                    timeout=_EXTRACTION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning("Fact extraction timed out; skipping.")
                return
            except Exception:
                logger.exception("LLM generation failed during fact extraction")
                return

            response_text: str = self._extract_response_text(response)
            parsed_facts: List[str] = self._parse_extraction_response(response_text)
            if not parsed_facts:
                logger.info("No facts extracted for folder %s.", folder_id)
                return
            self._merge_and_store_facts(folder_id, parsed_facts)
            logger.info("Stored %d extracted facts for folder %s.", len(parsed_facts), folder_id)
        except Exception:
            logger.exception("Failed during memory learning.")

    def _format_injection(self, facts: List[str]) -> str:
        """Format the system message content for fact-only injection."""
        parts: List[str] = ["[Memory Island Active]"]
        for fact in facts:
            parts.append(f"- {fact}")
        return "\n".join(parts)

    async def inlet(
        self,
        body: Dict[str, Any],
        __user__: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve folder context and inject scoped learned facts as a system message."""
        try:
            if __user__ and self.valves.ENABLE_UPDATE_NOTIFICATIONS:
                try:
                    update_msg: Optional[str] = await self._get_update_notification(__user__)
                    if update_msg:
                        messages = body.get("messages", [])
                        messages.insert(0, {"role": "system", "content": update_msg})
                        body["messages"] = messages
                except Exception:
                    logger.exception("Failed to check for updates.")

            folder_id: Optional[str] = await self._resolve_folder(body, (__user__ or {}).get("id"))
            messages: List[Dict[str, Any]] = body.get("messages", [])

            # enforce isolation
            if not folder_id and self.valves.ISOLATE_BY_DEFAULT:
                return body

            facts: List[str] = self._load_folder_data(folder_id)
            if facts:
                injection_content: str = self._format_injection(facts)
                logger.info(
                    "Memory Island context injected for folder %s:\n%s",
                    folder_id,
                    injection_content,
                )
                system_msg: Dict[str, Any] = {
                    "role": "system",
                    "content": injection_content,
                }
                messages.insert(0, system_msg)
                body["messages"] = messages
        except Exception:
            logger.exception("Error in Memory Islands inlet.")
        return body

    async def outlet(
        self,
        body: Dict[str, Any],
        __user__: Optional[Dict[str, Any]] = None,
        __request__: Any = None,
    ) -> Dict[str, Any]:
        """After a response, optionally schedule background LLM fact extraction.

        OWUI's ``outlet_filter_handler`` passes ``__user__`` as an extra param when the
        handler declares it (see ``get_filter_params`` in ``open_webui/utils/filter.py``
        and the ``__user__`` entry in the outlet ``extra_params`` in
        ``open_webui/utils/middleware.py``). The outlet ``body`` carries a top-level
        ``chat_id`` but no ``metadata``/``folder_id``, so auto-learning relies on the
        user id to resolve the folder via the Chats model. ``__user__`` is optional to
        stay backward compatible with callers that do not supply it.
        """
        try:
            if not self.valves.AUTO_LEARN_MEMORIES:
                return body
            folder_id: Optional[str] = await self._resolve_folder(body, (__user__ or {}).get("id"))
            if not folder_id:
                return body
            if not _should_extract(folder_id, self.valves.EXTRACTION_INTERVAL):
                return body

            task = asyncio.create_task(
                self._extract_facts_with_llm(
                    folder_id, body, (__user__ or {}).get("id"), __request__
                )
            )
            self._learning_tasks.add(task)
            task.add_done_callback(self._learning_tasks.discard)
        except Exception:
            logger.exception("Error in Memory Islands outlet.")
        return body

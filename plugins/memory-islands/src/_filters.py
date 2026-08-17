from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from open_webui.models.chats import Chats
except ImportError:
    try:
        from open_webui.apps.webui.models.chats import Chats
    except ImportError:
        Chats = None  # noqa: N806


class FilterMixin:
    """Filter hooks: inlet, outlet, folder resolution and memory learning."""

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

    async def _learn_memories(self, folder_id: str, body: Dict[str, Any]) -> None:
        """Extract new facts from the latest exchange and store them."""
        try:
            messages: List[Dict[str, Any]] = body.get("messages", [])
            if not messages:
                return
            last = messages[-1]
            content: str = last.get("content", "")
            new_facts: List[str] = []
            for line in content.splitlines():
                if line.startswith("I ") or line.startswith("The user"):
                    new_facts.append(line.strip())
            if not new_facts:
                return
            self._merge_and_store_facts(folder_id, "", new_facts)
        except Exception:
            logger.exception("Failed during memory learning.")

    def _format_injection(self, guidelines: str, facts: List[str]) -> str:
        """Format system message content for injection."""
        parts: List[str] = ["[Memory Island Active]"]
        if guidelines:
            parts.append(guidelines)
        for fact in facts:
            parts.append(f"- {fact}")
        return "\n".join(parts)

    async def inlet(
        self,
        body: Dict[str, Any],
        __user__: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve folder context, handle slash commands, and inject scoped guidelines and memories."""
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

            # Handle slash commands
            if messages:
                last_msg = messages[-1]
                content: str = last_msg.get("content", "").strip()
                if content.startswith("/island-"):
                    if self._handle_command(body, last_msg, messages, folder_id, content):
                        return body

            # enforce isolation
            if not folder_id and self.valves.ISOLATE_BY_DEFAULT:
                return body

            guidelines, facts = self._load_folder_data(folder_id)
            if guidelines or facts:
                system_msg: Dict[str, Any] = {
                    "role": "system",
                    "content": self._format_injection(guidelines, facts),
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
    ) -> Dict[str, Any]:
        """After response, optionally extract new memories asynchronously.

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

            task = asyncio.create_task(self._learn_memories(folder_id, body))
            self._learning_tasks.add(task)
            task.add_done_callback(self._learning_tasks.discard)
        except Exception:
            logger.exception("Error in Memory Islands outlet.")
        return body

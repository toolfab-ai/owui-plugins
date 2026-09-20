from __future__ import annotations

import json
import logging
import os
import platform
import sqlite3
import time
import uuid
import zipfile
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ._updates import UpdateMixin
from ._valves import Valves

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Helpers
# ---------------------------------------------------------------------------


def _get_owui_data_dir() -> str:
    """Get the Open WebUI data directory from environment or default paths."""
    data_dir = os.environ.get("OPEN_WEBUI_DATA_DIR", "")
    if data_dir:
        return data_dir
    home = os.path.expanduser("~")
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", home), "open-webui", "data")
    if platform.system() == "Darwin":
        return os.path.join(home, "Library", "Application Support", "open-webui", "data")
    return os.path.join(home, ".local", "share", "open-webui", "data")


def _get_db_path() -> str:
    """Get the path to the webui.db file."""
    data_dir = _get_owui_data_dir()
    # Check if webui.db is in data_dir/data/webui.db or directly in data_dir
    paths = [
        os.path.join(data_dir, "data", "webui.db"),
        os.path.join(data_dir, "webui.db"),
    ]
    for p in paths:
        if os.path.isfile(p):
            return p
    return paths[0]


# ========================================================================
# TOOLS CLASS
# ========================================================================


class Tools(UpdateMixin):
    """Tools for importing chat history from external platforms."""

    def __init__(self) -> None:
        self.valves = Valves()

    async def import_chatgpt_export(
        self,
        file_id: str,
        __user__: Dict[str, Any],
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> str:
        """
        Import a ChatGPT export (ZIP or conversations.json) into Open WebUI.

        :param file_id: The UUID of the uploaded file in Open WebUI.
        :return: A summary message of the import process.
        """
        user_id = __user__.get("id", "")
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Starting ChatGPT import...", "done": False},
                }
            )

        db_path = _get_db_path()
        if not os.path.isfile(db_path):
            return f"Error: Database not found at {db_path}"

        try:
            # 1. Retrieve file path from DB
            file_path = self._get_file_path(db_path, file_id)
            if not file_path:
                return f"Error: File with ID {file_id} not found in database."

            if not os.path.isfile(file_path):
                return f"Error: File not found on disk at {file_path}"

            # 2. Extract and Load conversations.json
            conversations = self._load_conversations(file_path)
            if not conversations:
                return "Error: Could not find conversations.json in the provided file."

            imported_count = 0
            error_count = 0

            for conv in conversations:
                try:
                    chat_data = self._map_chatgpt_to_owui(conv)
                    if chat_data:
                        self._insert_chat(db_path, user_id, chat_data)
                        imported_count += 1
                except Exception:
                    logger.exception(f"Failed to import conversation: {conv.get('title')}")
                    error_count += 1

            summary = f"Successfully imported {imported_count} chats."
            if error_count > 0:
                summary += f" Encountered errors in {error_count} chats."

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": summary, "done": True},
                    }
                )

            return summary

        except Exception as e:
            logger.exception("Import process failed")
            error_msg = f"Import failed: {str(e)}"
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": error_msg, "done": True},
                    }
                )
            return error_msg

    def _get_file_path(self, db_path: str, file_id: str) -> Optional[str]:
        """Get the absolute file path from the file table."""
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute("SELECT path FROM file WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def _load_conversations(self, file_path: str) -> List[Dict[str, Any]]:
        """Load conversations.json from a ZIP or raw JSON file."""
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, "r") as z:
                # ChatGPT export ZIP usually contains conversations.json
                if "conversations.json" in z.namelist():
                    with z.open("conversations.json") as f:
                        return json.load(f)
                # Try to find any JSON file that looks like conversations
                for name in z.namelist():
                    if name.endswith(".json") and "conversations" in name.lower():
                        with z.open(name) as f:
                            return json.load(f)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _map_chatgpt_to_owui(self, conv: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a ChatGPT conversation object to the Open WebUI chat format."""
        mapping = conv.get("mapping", {})
        if not mapping:
            return None

        title = conv.get("title", "Untitled Chat")
        create_time = conv.get("create_time", time.time())
        update_time = conv.get("update_time", time.time())

        owui_messages: List[Dict[str, Any]] = []
        history_messages: Dict[str, Dict[str, Any]] = {}

        for node_id, node in mapping.items():
            msg_obj = node.get("message")
            if not msg_obj:
                continue

            author = msg_obj.get("author", {})
            role = author.get("role")
            if role not in ["user", "assistant", "system"]:
                if role == "tool":
                    role = "assistant"
                else:
                    continue

            content_obj = msg_obj.get("content", {})
            parts = content_obj.get("parts", [])
            content = ""
            if parts:
                content = "\n".join([str(p) for p in parts if isinstance(p, (str, int, float))])

            if not content.strip() and role != "system":
                continue

            msg_id = msg_obj.get("id", node_id)
            parent_id = node.get("parent")

            history_messages[msg_id] = {
                "id": msg_id,
                "role": role,
                "content": content,
                "parentId": parent_id,
                "timestamp": msg_obj.get("create_time", create_time),
            }

        if not history_messages:
            return None

        current_node_id = conv.get("current_node")
        active_path: List[str] = []
        curr = current_node_id
        while curr and curr in mapping:
            active_path.append(curr)
            curr = mapping[curr].get("parent")
        active_path.reverse()

        for msg_id in active_path:
            if msg_id in history_messages:
                owui_messages.append(history_messages[msg_id])

        return {
            "title": title,
            "models": [self.valves.DEFAULT_MODEL],
            "messages": owui_messages,
            "history": {
                "messages": history_messages,
                "currentId": current_node_id,
            },
            "timestamp": create_time,
            "updated_at": update_time,
        }

    def _insert_chat(self, db_path: str, user_id: str, chat_data: Dict[str, Any]) -> None:
        """Insert the mapped chat into the database."""
        chat_id = str(uuid.uuid4())
        title = chat_data.get("title", "Imported Chat")
        now = int(time.time())
        created_at = int(chat_data.get("timestamp", now))
        updated_at = int(chat_data.get("updated_at", now))

        chat_json = json.dumps(
            {
                "id": chat_id,
                "title": title,
                "models": chat_data.get("models", []),
                "messages": chat_data.get("messages", []),
                "history": chat_data.get("history", {}),
                "timestamp": created_at,
            }
        )

        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """INSERT INTO chat (id, user_id, title, chat, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (chat_id, user_id, title, chat_json, created_at, updated_at),
            )
            conn.commit()
        finally:
            conn.close()

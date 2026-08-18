from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def _resolve_data_dir() -> Path:
    """Resolve the Open WebUI data directory with the following precedence:

    1. ``DATA_DIR`` env var if explicitly set.
    2. ``open_webui.env.DATA_DIR`` (the framework-resolved value, e.g.
       ``/app/backend/data`` in the official Docker image) if importable and truthy.
    3. Fall back to ``~/.openwebui``.
    """
    raw_env = os.getenv("DATA_DIR")
    if raw_env:
        return Path(raw_env)

    try:
        from open_webui.env import DATA_DIR as owui_data_dir  # noqa: N811
    except ImportError:
        owui_data_dir = ""

    if owui_data_dir:
        return Path(owui_data_dir)

    return Path.home() / ".openwebui"


def _utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class DatabaseMixin:
    """SQLite persistence for folder-scoped learned facts (schema v2)."""

    _MAX_FACTS: int = 200

    def _init_databases(self) -> None:
        """Initialize the plugin-local sqlite database under a stable DATA_DIR.

        Schema v2 is created fresh. If a legacy v1 ``memories`` table carrying a
        ``guidelines`` column is detected, it is dropped and recreated with the v2
        schema (no production users exist, so no migration is implemented).
        """
        data_dir = _resolve_data_dir()
        plugin_data_dir = data_dir / "memory-islands"
        plugin_data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path: Path = plugin_data_dir / "folder_memories.db"
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            columns = conn.execute("PRAGMA table_info(memories)").fetchall()
            if any(col[1] == "guidelines" for col in columns):
                logger.info(
                    "Detected legacy v1 memories table; dropping and recreating with schema v2."
                )
                conn.execute("DROP TABLE memories")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    folder_id TEXT PRIMARY KEY,
                    facts TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to initialize memories database.")
        finally:
            if conn is not None:
                conn.close()

    def _load_folder_data(self, folder_id: Optional[str]) -> List[str]:
        """Load the learned facts for a folder from the local DB (schema v2)."""
        facts: List[str] = []
        if not folder_id:
            return facts
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            cursor = conn.execute("SELECT facts FROM memories WHERE folder_id=?", (folder_id,))
            row = cursor.fetchone()
            if row:
                facts = json.loads(row[0]) if row[0] else []
        except (sqlite3.Error, json.JSONDecodeError):
            logger.exception("Failed to load folder memories.")
        finally:
            if conn is not None:
                conn.close()
        return facts

    def _persist_facts(self, folder_id: str, facts: List[str]) -> None:
        """Upsert a folder's fact list and refresh its ``updated_at`` timestamp."""
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.execute(
                "INSERT OR REPLACE INTO memories (folder_id, facts, updated_at) VALUES (?, ?, ?)",
                (folder_id, json.dumps(facts), _utc_now_iso()),
            )
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to store folder memories.")
        finally:
            if conn is not None:
                conn.close()

    def _merge_and_store_facts(self, folder_id: str, new_facts: List[str]) -> None:
        """Merge new facts with existing ones, deduplicate preserving order, cap, persist."""
        existing_facts: List[str] = self._load_folder_data(folder_id)
        combined: List[str] = list(dict.fromkeys(existing_facts + new_facts))[: self._MAX_FACTS]
        self._persist_facts(folder_id, combined)

    def _add_fact(self, folder_id: str, fact: str) -> List[str]:
        """Add a single fact: trim, reject empty, deduplicate, cap, persist.

        Returns the new fact list.
        """
        cleaned: str = fact.strip()
        if not cleaned:
            return self._load_folder_data(folder_id)
        existing_facts: List[str] = self._load_folder_data(folder_id)
        combined: List[str] = list(dict.fromkeys(existing_facts + [cleaned]))[: self._MAX_FACTS]
        self._persist_facts(folder_id, combined)
        return combined

    def _delete_fact(self, folder_id: str, fact: str) -> List[str]:
        """Remove the exact matching fact, persist, and refresh ``updated_at``.

        Returns the new fact list.
        """
        existing_facts: List[str] = self._load_folder_data(folder_id)
        if fact not in existing_facts:
            return existing_facts
        combined: List[str] = [f for f in existing_facts if f != fact]
        self._persist_facts(folder_id, combined)
        return combined

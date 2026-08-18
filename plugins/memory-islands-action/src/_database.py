from __future__ import annotations

import json
import logging
import os
import sqlite3
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


class DatabaseMixin:
    """SQLite persistence for READING folder-scoped learned facts (schema v2).

    The Manager Action only READS the shared ``folder_memories.db``. Writes are
    owned by the Memory Islands Filter via the internal panel-command channel
    (``@memory add:`` / ``@memory delete:``); those helpers intentionally live
    only in the Filter, so every OWUI Function stays standalone.
    """

    def _init_databases(self) -> None:
        """Initialize the shared plugin-local sqlite database under a stable DATA_DIR.

        Ensures the schema v2 ``memories`` table exists. If a legacy v1 table
        carrying a ``guidelines`` column is detected, it is dropped and recreated
        with the v2 schema (no production users exist, so no migration is
        implemented and legacy data is not carried over — the native folder
        System Prompt replaces guidelines).
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
        """Load the learned facts for a folder from the shared DB (schema v2)."""
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

    def _is_db_readable(self) -> bool:
        """Return True when the shared database can be queried.

        ``_load_folder_data`` mirrors the Filter and swallows sqlite3 errors into
        an empty list, so this lightweight probe lets the panel render a distinct
        error state when the DB is locked or unreadable instead of silently
        showing the empty state.
        """
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            return True
        except sqlite3.Error:
            logger.exception("Failed to access memories database.")
            return False
        finally:
            if conn is not None:
                conn.close()

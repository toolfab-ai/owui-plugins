from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseMixin:
    """SQLite persistence for folder-scoped guidelines and memories."""

    _MAX_FACTS: int = 200

    def _init_databases(self) -> None:
        """Initialize the plugin-local sqlite database under a stable DATA_DIR."""
        data_dir = Path(os.getenv("DATA_DIR") or (Path.home() / ".openwebui"))
        plugin_data_dir = data_dir / "memory-islands"
        plugin_data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path: Path = plugin_data_dir / "folder_memories.db"
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    folder_id TEXT PRIMARY KEY,
                    guidelines TEXT,
                    facts TEXT
                )
                """
            )
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to initialize memories database.")
        finally:
            if conn is not None:
                conn.close()

    def _load_folder_data(self, folder_id: Optional[str]) -> Tuple[str, List[str]]:
        """Load guidelines and facts for a given folder from local DB."""
        guidelines: str = ""
        facts: List[str] = []
        if not folder_id:
            return guidelines, facts
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            cursor = conn.execute(
                "SELECT guidelines, facts FROM memories WHERE folder_id=?", (folder_id,)
            )
            row = cursor.fetchone()
            if row:
                guidelines = row[0] or ""
                facts = json.loads(row[1]) if row[1] else []
        except (sqlite3.Error, json.JSONDecodeError):
            logger.exception("Failed to load folder memories.")
        finally:
            if conn is not None:
                conn.close()
        return guidelines, facts

    def _save_guidelines(self, folder_id: str, guidelines: str) -> None:
        """Save custom guidelines for the folder, preserving existing facts."""
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            cur = conn.execute("SELECT facts FROM memories WHERE folder_id=?", (folder_id,))
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE memories SET guidelines=? WHERE folder_id=?",
                    (guidelines, folder_id),
                )
            else:
                conn.execute(
                    "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
                    (folder_id, guidelines, "[]"),
                )
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to save folder guidelines.")
        finally:
            if conn is not None:
                conn.close()

    def _clear_guidelines(self, folder_id: str) -> None:
        """Clear the guidelines for a folder, preserving facts."""
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            cur = conn.execute("SELECT facts FROM memories WHERE folder_id=?", (folder_id,))
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE memories SET guidelines=? WHERE folder_id=?",
                    ("", folder_id),
                )
            else:
                conn.execute(
                    "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
                    (folder_id, "", "[]"),
                )
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to clear folder guidelines.")
        finally:
            if conn is not None:
                conn.close()

    def _clear_facts(self, folder_id: str) -> None:
        """Clear all learned facts for a folder, preserving guidelines."""
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            cur = conn.execute("SELECT guidelines FROM memories WHERE folder_id=?", (folder_id,))
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE memories SET facts=? WHERE folder_id=?",
                    ("[]", folder_id),
                )
            else:
                conn.execute(
                    "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
                    (folder_id, "", "[]"),
                )
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to clear folder facts.")
        finally:
            if conn is not None:
                conn.close()

    def _merge_and_store_facts(self, folder_id: str, guidelines: str, new_facts: List[str]) -> None:
        """Merge new facts with existing, deduplicate preserving order, cap length, and persist."""
        existing_guidelines, existing_facts = self._load_folder_data(folder_id)
        combined: List[str] = list(dict.fromkeys(existing_facts + new_facts))[: self._MAX_FACTS]
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.execute(
                "INSERT OR REPLACE INTO memories(folder_id, guidelines, facts) VALUES (?, ?, ?)",
                (folder_id, existing_guidelines or guidelines, json.dumps(combined)),
            )
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to store folder memories.")
        finally:
            if conn is not None:
                conn.close()

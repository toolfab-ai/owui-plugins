"""Unit tests for Memory Islands filter plugin — no container needed."""

import builtins
import json
import logging
import sqlite3
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests._plugin_loader import load_plugin

# Load the memory-islands plugin dynamically
mod = load_plugin("memory-islands")

pytestmark = pytest.mark.unit


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Fixture providing the plugin's temporary database path under DATA_DIR."""
    return tmp_path / "memory-islands" / "folder_memories.db"


@pytest.fixture
def filter_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Fixture providing a Filter plugin instance using a clean temporary database."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _plugin = mod.Filter()
    yield _plugin


@pytest.fixture(autouse=True)
def _reset_extraction_counters() -> None:
    """Reset the module-level EXTRACTION_INTERVAL counters before every test."""
    mod._EXCHANGE_COUNTS.clear()
    yield


def _mock_chat_module(response_text: str = "") -> tuple[MagicMock, MagicMock]:
    """Build a fake ``open_webui.utils.chat`` module for the resilient LLM import."""
    mock_chat = MagicMock()
    mock_gen = AsyncMock(return_value=response_text)
    mock_chat.generate_chat_completion = mock_gen
    return mock_chat, mock_gen


def _patch_chat_import(mock_chat: MagicMock) -> None:
    """Inject fake open_webui modules so the in-function LLM import resolves."""
    return patch.dict(
        sys.modules,
        {
            "open_webui": MagicMock(),
            "open_webui.utils": MagicMock(),
            "open_webui.utils.chat": mock_chat,
        },
    )


# ========================================================================
# DATA DIR RESOLUTION
# ========================================================================


@pytest.mark.unit
class TestDataDirResolution:
    """Tests for the ``_resolve_data_dir`` helper."""

    def test_resolve_data_dir_honours_explicit_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify an explicitly set DATA_DIR env var wins over every other source."""
        monkeypatch.setenv("DATA_DIR", "/custom/data")
        assert mod._resolve_data_dir() == Path("/custom/data")

    def test_resolve_data_dir_falls_back_to_home_when_import_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify fallback to ~/.openwebui when DATA_DIR is unset and open_webui import fails."""
        monkeypatch.delenv("DATA_DIR", raising=False)
        real_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "open_webui.env":
                raise ImportError("open_webui not available")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert mod._resolve_data_dir() == Path.home() / ".openwebui"

    def test_resolve_data_dir_uses_framework_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify framework-resolved open_webui.env.DATA_DIR is used when env var is unset."""
        monkeypatch.delenv("DATA_DIR", raising=False)
        fake_env = types.SimpleNamespace(DATA_DIR="/fake/owui/data")
        real_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "open_webui.env":
                return fake_env
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert mod._resolve_data_dir() == Path("/fake/owui/data")


# ========================================================================
# DATABASE INITIALIZATION
# ========================================================================


@pytest.mark.unit
class TestDatabaseInitialization:
    """Tests the database initialization logic inside ``_init_databases``."""

    def test_init_databases_creates_schema(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that initializing the filter plugin creates the v2 memories table."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        _plugin = mod.Filter()
        temp_db = tmp_path / "memory-islands" / "folder_memories.db"
        # Verify the file was created
        assert temp_db.exists()

        # Retrieve database schema
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("PRAGMA table_info(memories)")
        columns = cursor.fetchall()
        conn.close()

        # Schema columns: (cid, name, type, notnull, dflt_value, pk)
        assert len(columns) == 3
        col_names = [col[1] for col in columns]
        assert col_names == ["folder_id", "facts", "updated_at"]

        # Verify primary key is folder_id
        folder_id_col = [col for col in columns if col[1] == "folder_id"][0]
        assert folder_id_col[5] == 1  # 1 denotes PRIMARY KEY

    def test_init_databases_drops_legacy_v1_table(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify a legacy v1 table with a guidelines column is dropped and recreated as v2."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        temp_db = tmp_path / "memory-islands" / "folder_memories.db"
        temp_db.parent.mkdir(parents=True, exist_ok=True)

        # Simulate a legacy v1 database with a guidelines column and data.
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "CREATE TABLE memories (folder_id TEXT PRIMARY KEY, guidelines TEXT, facts TEXT)"
        )
        conn.execute(
            "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
            ("folder-legacy", "Old guidelines", json.dumps(["Old fact"])),
        )
        conn.commit()
        conn.close()

        with caplog.at_level(logging.INFO):
            _plugin = mod.Filter()

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("PRAGMA table_info(memories)")
        col_names = [col[1] for col in cursor.fetchall()]
        rows = conn.execute("SELECT * FROM memories").fetchall()
        conn.close()

        assert col_names == ["folder_id", "facts", "updated_at"]
        assert rows == []  # legacy data is not carried over
        assert any("legacy v1 memories table" in record.message for record in caplog.records)

    def test_init_databases_handles_sqlite_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that sqlite3 errors during database initialization are handled gracefully and logged."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        with (
            patch("sqlite3.connect", side_effect=sqlite3.Error("Failed to connect")),
            caplog.at_level(logging.ERROR),
        ):
            # Instantiating the Filter class should not raise an exception
            _plugin = mod.Filter()
            assert _plugin is not None
            # Check log for expected error message
            assert any(
                "Failed to initialize memories database" in record.message
                for record in caplog.records
            )


# ========================================================================
# FOLDER RESOLUTION
# ========================================================================


@pytest.mark.unit
class TestFolderResolution:
    """Tests for resolving folder ID from the filter payload or the Chats model.

    IMPORTANT: These tests use the REAL Open WebUI payload shape. OWUI's
    ``/api/chat/completions`` handler pops ``folder_id`` and ``chat_id`` out of the
    top-level form_data and re-injects them into ``body["metadata"]`` (keys
    ``metadata.folder_id``, ``metadata.chat_id``, ``metadata.user_id``). Therefore a
    filter's ``inlet(body, __user__)`` never sees top-level ``folder_id``/``chat_id`` —
    they are None. All payloads below reflect that reality.
    """

    async def test_resolve_folder_from_metadata_folder_id(self, filter_plugin: Any) -> None:
        """Verify folder_id is read from ``body["metadata"]["folder_id"]`` when present.

        Regression: before the fix the plugin only looked at the (always None) top-level
        ``body.get("folder_id")``, so a chat inside a folder was treated as Global Workspace.
        """
        body = {
            "metadata": {
                "user_id": "user-1",
                "chat_id": "chat-xyz",
                "folder_id": "test-folder-123",
            },
            "messages": [],
        }
        folder_id = await filter_plugin._resolve_folder(body)
        assert folder_id == "test-folder-123"

    async def test_resolve_folder_prefers_metadata_folder_id_over_top_level(
        self, filter_plugin: Any
    ) -> None:
        """Verify metadata.folder_id wins even if a legacy top-level key is present."""
        body = {
            "folder_id": "top-level-folder",
            "metadata": {"chat_id": "chat-xyz", "folder_id": "metadata-folder"},
        }
        folder_id = await filter_plugin._resolve_folder(body)
        assert folder_id == "metadata-folder"

    async def test_resolve_folder_metadata_folder_id_empty_falls_back_to_chats(
        self, filter_plugin: Any
    ) -> None:
        """Verify an empty metadata.folder_id triggers the Chats-model fallback."""
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id.return_value = "folder-from-chats"
        with patch.object(mod, "Chats", mock_chats):
            body = {
                "metadata": {"user_id": "user-1", "chat_id": "chat-xyz", "folder_id": ""},
            }
            folder_id = await filter_plugin._resolve_folder(body, user_id="user-1")

        assert folder_id == "folder-from-chats"
        mock_chats.get_chat_folder_id.assert_called_once_with("chat-xyz", "user-1")

    async def test_resolve_folder_via_chats_model_using_metadata_chat_id(
        self, filter_plugin: Any
    ) -> None:
        """Verify the Chats-model fallback uses ``body["metadata"]["chat_id"]``.

        Regression: before the fix the plugin read ``body.get("chat_id")`` which is None in
        the real payload (OWUI pops it into metadata), so the fallback never ran.
        """
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id.return_value = "folder-from-chats"
        with patch.object(mod, "Chats", mock_chats):
            body = {
                "metadata": {"user_id": "user-1", "chat_id": "chat-xyz", "folder_id": None},
            }
            folder_id = await filter_plugin._resolve_folder(body, user_id="user-1")

        assert folder_id == "folder-from-chats"
        mock_chats.get_chat_folder_id.assert_called_once_with("chat-xyz", "user-1")

    async def test_resolve_folder_no_metadata_returns_none(self, filter_plugin: Any) -> None:
        """Verify _resolve_folder returns None when no metadata/chat/folder info exists."""
        body = {"messages": []}
        folder_id = await filter_plugin._resolve_folder(body, user_id="user-1")
        assert folder_id is None

    async def test_resolve_folder_global_workspace_returns_none(self, filter_plugin: Any) -> None:
        """Global-workspace chat: metadata present but folder_id and chat_id empty -> None."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "", "folder_id": None},
        }
        folder_id = await filter_plugin._resolve_folder(body, user_id="user-1")
        assert folder_id is None

    async def test_resolve_folder_chats_model_error(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify errors from the Chats model are captured gracefully and logged."""
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id.side_effect = RuntimeError("Chats lookup failed")

        with (
            patch.object(mod, "Chats", mock_chats),
            caplog.at_level(logging.ERROR),
        ):
            body = {
                "metadata": {"user_id": "user-1", "chat_id": "chat-xyz", "folder_id": None},
            }
            folder_id = await filter_plugin._resolve_folder(body, user_id="user-1")

        assert folder_id is None
        assert any(
            "Failed to resolve folder_id via Chats model" in record.message
            for record in caplog.records
        )

    async def test_resolve_folder_chats_model_async_fallback(self, filter_plugin: Any) -> None:
        """Verify the dynamic await handles an async ``Chats.get_chat_folder_id``.

        ``Chats.get_chat_folder_id`` is ``async`` in OWUI v0.10+, so
        ``_resolve_folder`` must await the returned coroutine instead of treating
        it as a plain value.
        """
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id = AsyncMock(return_value="folder-from-async-chats")
        with patch.object(mod, "Chats", mock_chats):
            body = {
                "metadata": {"user_id": "user-1", "chat_id": "chat-xyz", "folder_id": None},
            }
            folder_id = await filter_plugin._resolve_folder(body, user_id="user-1")

        assert folder_id == "folder-from-async-chats"
        mock_chats.get_chat_folder_id.assert_called_once_with("chat-xyz", "user-1")

    async def test_resolve_folder_chats_import_failure_returns_none(
        self, filter_plugin: Any
    ) -> None:
        """Verify a missing Chats model (import failure) degrades gracefully.

        When the ``open_webui`` imports fail at module load, ``Chats`` is ``None``.
        ``_resolve_folder`` must return ``None`` without raising even when a valid
        ``metadata.chat_id`` and ``user_id`` are present.
        """
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-xyz", "folder_id": None},
        }
        with patch.object(mod, "Chats", None):
            folder_id = await filter_plugin._resolve_folder(body, user_id="user-1")

        assert folder_id is None


# ========================================================================
# DATA LOADING
# ========================================================================


class TestDataLoading:
    """Tests loading folder facts from the local database (schema v2)."""

    def test_load_folder_data_existing(self, filter_plugin: Any, temp_db_path: Path) -> None:
        """Verify loading existing facts successfully."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute(
            "INSERT INTO memories (folder_id, facts, updated_at) VALUES (?, ?, ?)",
            (
                "folder-abc",
                json.dumps(["User is a doctor", "User works in NYC"]),
                "2026-08-18T00:00:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        facts = filter_plugin._load_folder_data("folder-abc")
        assert facts == ["User is a doctor", "User works in NYC"]

    def test_load_folder_data_missing_record(self, filter_plugin: Any) -> None:
        """Verify _load_folder_data returns [] if no record exists for folder_id."""
        facts = filter_plugin._load_folder_data("non-existent-folder")
        assert facts == []

    def test_load_folder_data_db_error(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify DB errors inside _load_folder_data are caught and logged."""
        with (
            patch("sqlite3.connect", side_effect=sqlite3.Error("Disk full")),
            caplog.at_level(logging.ERROR),
        ):
            facts = filter_plugin._load_folder_data("folder-abc")

        assert facts == []
        assert any("Failed to load folder memories" in record.message for record in caplog.records)


# ========================================================================
# FACT CRUD HELPERS
# ========================================================================


class TestFactCrud:
    """Tests for _merge_and_store_facts, _add_fact, and _delete_fact."""

    def test_merge_and_store_facts_dedup_preserves_order(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify merging deduplicates while preserving insertion order."""
        filter_plugin._merge_and_store_facts("folder-merge", ["a", "b", "a", "c", "b"])
        facts = filter_plugin._load_folder_data("folder-merge")
        assert facts == ["a", "b", "c"]

    def test_merge_and_store_facts_appends_to_existing(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify merging appends new facts to already stored ones."""
        filter_plugin._merge_and_store_facts("folder-merge", ["existing"])
        filter_plugin._merge_and_store_facts("folder-merge", ["new", "existing"])
        facts = filter_plugin._load_folder_data("folder-merge")
        assert facts == ["existing", "new"]

    def test_merge_and_store_facts_caps_at_200(self, filter_plugin: Any) -> None:
        """Verify the merged fact list is capped at 200 entries."""
        filter_plugin._merge_and_store_facts("folder-cap", [f"fact-{i}" for i in range(205)])
        facts = filter_plugin._load_folder_data("folder-cap")
        assert len(facts) == 200
        assert facts[0] == "fact-0"
        assert facts[-1] == "fact-199"

    def test_add_fact_trims_and_stores(self, filter_plugin: Any) -> None:
        """Verify _add_fact trims whitespace and returns the new list."""
        result = filter_plugin._add_fact("folder-add", "  User likes hiking  ")
        assert result == ["User likes hiking"]

    def test_add_fact_rejects_empty(self, filter_plugin: Any, temp_db_path: Path) -> None:
        """Verify empty/whitespace facts are rejected without writes."""
        result = filter_plugin._add_fact("folder-add", "   ")
        assert result == []
        conn = sqlite3.connect(temp_db_path)
        row = conn.execute("SELECT * FROM memories WHERE folder_id=?", ("folder-add",)).fetchone()
        conn.close()
        assert row is None

    def test_add_fact_dedups(self, filter_plugin: Any) -> None:
        """Verify adding a duplicate fact does not create a second entry."""
        filter_plugin._add_fact("folder-add", "same fact")
        result = filter_plugin._add_fact("folder-add", "same fact")
        assert result == ["same fact"]

    def test_add_fact_caps_at_200(self, filter_plugin: Any) -> None:
        """Verify _add_fact caps the stored list at 200 entries."""
        for i in range(205):
            filter_plugin._add_fact("folder-cap", f"fact-{i}")
        facts = filter_plugin._load_folder_data("folder-cap")
        assert len(facts) == 200

    def test_delete_fact_removes_exact_match(self, filter_plugin: Any) -> None:
        """Verify _delete_fact removes the exact matching fact."""
        filter_plugin._add_fact("folder-del", "fact one")
        filter_plugin._add_fact("folder-del", "fact two")
        result = filter_plugin._delete_fact("folder-del", "fact one")
        assert result == ["fact two"]

    def test_delete_fact_no_match_returns_unchanged(self, filter_plugin: Any) -> None:
        """Verify deleting a non-existent fact leaves the list unchanged."""
        filter_plugin._add_fact("folder-del", "fact one")
        result = filter_plugin._delete_fact("folder-del", "missing")
        assert result == ["fact one"]

    def test_updated_at_is_set_on_persist(self, filter_plugin: Any, temp_db_path: Path) -> None:
        """Verify writes set an ISO 8601 updated_at timestamp."""
        filter_plugin._add_fact("folder-ts", "fact")
        conn = sqlite3.connect(temp_db_path)
        row = conn.execute(
            "SELECT updated_at FROM memories WHERE folder_id=?", ("folder-ts",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] != ""


# ========================================================================
# INLET GATING
# ========================================================================


class TestInletGating:
    """Tests injecting folder facts as a system prompt at inlet (facts only, no guidelines)."""

    @pytest.mark.asyncio
    async def test_inlet_injects_facts_only(self, filter_plugin: Any) -> None:
        """Verify stored facts are prepended as a [Memory Island Active] system message."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": "folder-abc"},
            "messages": [{"role": "user", "content": "Explain photosynthesis."}],
        }

        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(
                filter_plugin,
                "_load_folder_data",
                return_value=["User is 8 years old", "Likes science"],
            ),
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"

        content = messages[0]["content"]
        assert "[Memory Island Active]" in content
        assert "- User is 8 years old" in content
        assert "- Likes science" in content
        # No guidelines are injected in v0.2.0.
        assert "guidelines" not in content.lower()

        assert messages[1] == {"role": "user", "content": "Explain photosynthesis."}

    @pytest.mark.asyncio
    async def test_inlet_no_injection_when_no_facts(self, filter_plugin: Any) -> None:
        """Verify inlet returns the body unmodified when the folder has no facts."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": "folder-abc"},
            "messages": [{"role": "user", "content": "Hello"}],
        }

        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(filter_plugin, "_load_folder_data", return_value=[]),
        ):
            result = await filter_plugin.inlet(body)

        assert result == body
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_inlet_no_folder_and_isolate_by_default(self, filter_plugin: Any) -> None:
        """Verify no modification happens if no folder is resolved and ISOLATE_BY_DEFAULT is active."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": None},
            "messages": [{"role": "user", "content": "Hello"}],
        }
        filter_plugin.valves.ISOLATE_BY_DEFAULT = True

        with patch.object(filter_plugin, "_resolve_folder", new=AsyncMock(return_value=None)):
            result = await filter_plugin.inlet(body)

        assert result == body
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_inlet_exception_logged_and_handled(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify that any unhandled exception in inlet is logged and returns unmodified body."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": None},
            "messages": [{"role": "user", "content": "Hello"}],
        }

        with (
            patch.object(
                filter_plugin,
                "_resolve_folder",
                new=AsyncMock(side_effect=ValueError("Unexpected crash")),
            ),
            caplog.at_level(logging.ERROR),
        ):
            result = await filter_plugin.inlet(body)

        assert result == body
        assert any("Error in Memory Islands inlet" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_inlet_logs_info_when_context_injected(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify an INFO log records the injected context banner, facts, and folder id."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": "folder-abc"},
            "messages": [{"role": "user", "content": "Explain photosynthesis."}],
        }

        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(
                filter_plugin,
                "_load_folder_data",
                return_value=["User prefers concise answers"],
            ),
            caplog.at_level(logging.INFO),
        ):
            result = await filter_plugin.inlet(body)

        # Sanity check: context was actually injected into the payload.
        assert result["messages"][0]["role"] == "system"

        injection_records = [
            record
            for record in caplog.records
            if "Memory Island context injected" in record.message
        ]
        assert len(injection_records) == 1
        assert injection_records[0].levelno == logging.INFO
        message = injection_records[0].message
        assert "folder-abc" in message
        assert "[Memory Island Active]\n- User prefers concise answers" in message

    @pytest.mark.asyncio
    async def test_inlet_no_folder_data_emits_no_info_log(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify no INFO injection log is emitted when the folder has no facts."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": "folder-abc"},
            "messages": [{"role": "user", "content": "Hello"}],
        }

        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(filter_plugin, "_load_folder_data", return_value=[]),
            caplog.at_level(logging.INFO),
        ):
            result = await filter_plugin.inlet(body)

        assert result == body
        assert len(result["messages"]) == 1
        assert not any(
            "Memory Island context injected" in record.message for record in caplog.records
        )


# ========================================================================
# PANEL-COMMAND CHANNEL (FR-011)
# ========================================================================


class TestPanelCommandChannel:
    """Tests for the internal panel-command channel handled in the inlet.

    The Memory Islands Manager Action panel posts ``@memory add:`` /
    ``@memory delete:`` commands into the chat; the Filter inlet intercepts the
    LAST user message, executes the DB operation for the resolved folder, and
    rewrites the message into a system instruction so the assistant replies with
    a concise confirmation. Malformed or outside-folder commands are rewritten
    into a polite explanation with no DB write; normal messages pass through.
    """

    def _body(self, content: str, folder_id: Optional[str] = "folder-abc") -> Dict[str, Any]:
        """Build a realistic inlet payload with a single user message."""
        return {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": folder_id},
            "messages": [{"role": "user", "content": content}],
        }

    # ------------------------------------------------------------------
    # Command parsing
    # ------------------------------------------------------------------

    def test_parse_panel_command_normal_message(self, filter_plugin: Any) -> None:
        """Verify a normal message yields None from the parser (untouched)."""
        assert filter_plugin._parse_panel_command("Explain photosynthesis.") is None

    def test_parse_panel_command_add(self, filter_plugin: Any) -> None:
        """Verify '@memory add: <fact>' parses to ('add', payload)."""
        assert filter_plugin._parse_panel_command("@memory add: User likes hiking") == (
            "add",
            "User likes hiking",
        )

    def test_parse_panel_command_delete(self, filter_plugin: Any) -> None:
        """Verify '@memory delete: <fact>' parses to ('delete', payload)."""
        assert filter_plugin._parse_panel_command("@memory delete: User likes hiking") == (
            "delete",
            "User likes hiking",
        )

    def test_parse_panel_command_prefix_case_insensitive(self, filter_plugin: Any) -> None:
        """Verify the '@memory' prefix and action are matched case-insensitively."""
        assert filter_plugin._parse_panel_command("@MEMORY ADD: fact") == ("add", "fact")
        assert filter_plugin._parse_panel_command("@Memory DeLeTe: fact") == ("delete", "fact")

    def test_parse_panel_command_whitespace_is_trimmed(self, filter_plugin: Any) -> None:
        """Verify surrounding whitespace is trimmed from command and payload."""
        assert filter_plugin._parse_panel_command("  @memory add:  fact  ") == ("add", "fact")

    def test_parse_panel_command_malformed_variants(self, filter_plugin: Any) -> None:
        """Verify malformed '@memory' variants return ('invalid', '')."""
        assert filter_plugin._parse_panel_command("@memory") == ("invalid", "")
        assert filter_plugin._parse_panel_command("@memory add") == ("invalid", "")
        assert filter_plugin._parse_panel_command("@memory add:") == ("invalid", "")
        assert filter_plugin._parse_panel_command("@memory delete:   ") == ("invalid", "")
        assert filter_plugin._parse_panel_command("@memory wat: thing") == ("invalid", "")
        assert filter_plugin._parse_panel_command("@memory : thing") == ("invalid", "")

    def test_last_user_message_returns_last_only(self, filter_plugin: Any) -> None:
        """Verify _last_user_message returns the final user message only."""
        messages = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "second"},
        ]
        last = filter_plugin._last_user_message(messages)
        assert last == {"role": "user", "content": "second"}

    # ------------------------------------------------------------------
    # Add / delete through the inlet
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_add_command_stores_fact(self, filter_plugin: Any) -> None:
        """Verify '@memory add: <fact>' stores the fact and rewrites a confirmation."""
        body = self._body("@memory add: User likes hiking")
        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
        ):
            result = await filter_plugin.inlet(body)

        assert filter_plugin._load_folder_data("folder-abc") == ["User likes hiking"]
        last = result["messages"][-1]
        assert last["role"] == "system"
        assert last["content"] == "Reply with exactly: ✅ Fact added: User likes hiking"

    @pytest.mark.asyncio
    async def test_delete_command_removes_exact_fact(self, filter_plugin: Any) -> None:
        """Verify '@memory delete: <fact>' removes the exact fact and rewrites a confirmation."""
        filter_plugin._add_fact("folder-abc", "User likes hiking")
        filter_plugin._add_fact("folder-abc", "User likes coffee")
        body = self._body("@memory delete: User likes hiking")
        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
        ):
            result = await filter_plugin.inlet(body)

        assert filter_plugin._load_folder_data("folder-abc") == ["User likes coffee"]
        last = result["messages"][-1]
        assert last["role"] == "system"
        assert last["content"] == "Reply with exactly: ✅ Fact deleted: User likes hiking"

    @pytest.mark.asyncio
    async def test_add_command_logs_folder_id(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify panel-command execution is logged with the folder id (observability)."""
        body = self._body("@memory add: User likes hiking")
        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            caplog.at_level(logging.INFO),
        ):
            await filter_plugin.inlet(body)

        assert any(
            "Panel command executed: add fact for folder folder-abc" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_add_command_prefix_is_case_insensitive(self, filter_plugin: Any) -> None:
        """Verify an uppercased '@memory' prefix still executes the command."""
        body = self._body("@MEMORY ADD: User likes hiking")
        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
        ):
            result = await filter_plugin.inlet(body)

        assert filter_plugin._load_folder_data("folder-abc") == ["User likes hiking"]
        assert "✅ Fact added: User likes hiking" in result["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_command_matching_uses_last_user_message_only(self, filter_plugin: Any) -> None:
        """Verify only the LAST user message is matched for panel commands."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-abc", "folder_id": "folder-abc"},
            "messages": [
                {"role": "user", "content": "@memory add: Older fact"},
                {"role": "assistant", "content": "Noted!"},
                {"role": "user", "content": "Continue please"},
            ],
        }
        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(filter_plugin, "_load_folder_data", return_value=[]),
        ):
            result = await filter_plugin.inlet(body)

        # The earlier '@memory' message must not have been executed or rewritten.
        assert filter_plugin._load_folder_data("folder-abc") == []
        assert result["messages"] == [
            {"role": "user", "content": "@memory add: Older fact"},
            {"role": "assistant", "content": "Noted!"},
            {"role": "user", "content": "Continue please"},
        ]

    # ------------------------------------------------------------------
    # Malformed / outside-folder: explanation, no DB write
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_malformed_command_explains_and_no_db_write(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify a malformed '@memory' command produces an explanation and no DB write."""
        body = self._body("@memory wat: nonsense")
        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
        ):
            result = await filter_plugin.inlet(body)

        last = result["messages"][-1]
        assert last["role"] == "system"
        assert "not understood" in last["content"]
        assert "no memory was changed" in last["content"]

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute("SELECT * FROM memories WHERE folder_id=?", ("folder-abc",)).fetchone()
        conn.close()
        assert row is None

    @pytest.mark.asyncio
    async def test_add_command_empty_payload_is_malformed(self, filter_plugin: Any) -> None:
        """Verify '@memory add:' with no payload is malformed (no DB write)."""
        body = self._body("@memory add:")
        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
        ):
            result = await filter_plugin.inlet(body)

        assert filter_plugin._load_folder_data("folder-abc") == []
        assert "not understood" in result["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_command_outside_folder_explains_and_no_write(self, filter_plugin: Any) -> None:
        """Verify an '@memory' message outside a folder explains and never writes the DB."""
        body = self._body("@memory add: User likes hiking", folder_id=None)
        with patch.object(filter_plugin, "_resolve_folder", new=AsyncMock(return_value=None)):
            result = await filter_plugin.inlet(body)

        # ISOLATE_BY_DEFAULT is on, but the command channel still rewrites the message.
        last = result["messages"][-1]
        assert last["role"] == "system"
        assert "inside a folder" in last["content"]
        assert "no memory was changed" in last["content"]
        assert not any(
            "@memory add: User likes hiking" in str(msg.get("content"))
            for msg in result["messages"]
        )

    # ------------------------------------------------------------------
    # Normal messages pass through
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_normal_message_passes_through_untouched(self, filter_plugin: Any) -> None:
        """Verify a message without the '@memory' prefix is untouched by the command channel."""
        body = self._body("Explain photosynthesis.")
        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(filter_plugin, "_load_folder_data", return_value=[]),
        ):
            result = await filter_plugin.inlet(body)

        assert result == body
        assert result["messages"] == [{"role": "user", "content": "Explain photosynthesis."}]

    @pytest.mark.asyncio
    async def test_message_mentioning_memory_without_prefix_passes_through(
        self, filter_plugin: Any
    ) -> None:
        """Verify '@memory' embedded in a normal sentence is not treated as a command."""
        body = self._body("Tell me about the @memory system, please.")
        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(filter_plugin, "_load_folder_data", return_value=[]),
        ):
            result = await filter_plugin.inlet(body)

        assert result == body
        assert result["messages"] == [
            {"role": "user", "content": "Tell me about the @memory system, please."}
        ]


# ========================================================================
# EXTRACTION PARSING
# ========================================================================


class TestExtractionParsing:
    """Tests for the strict ``_parse_extraction_response`` contract."""

    def test_parse_valid_json_array(self, filter_plugin: Any) -> None:
        """Verify a plain JSON array of strings parses to facts."""
        result = filter_plugin._parse_extraction_response('["User likes tea", "Lives in Berlin"]')
        assert result == ["User likes tea", "Lives in Berlin"]

    def test_parse_json_fence(self, filter_plugin: Any) -> None:
        """Verify ```json code fences are stripped before parsing."""
        result = filter_plugin._parse_extraction_response('```json\n["User likes tea"]\n```')
        assert result == ["User likes tea"]

    def test_parse_partial_json_around_prose(self, filter_plugin: Any) -> None:
        """Verify JSON wrapped in prose is still recovered from the array block."""
        result = filter_plugin._parse_extraction_response('Here are the facts: ["User likes tea"]')
        assert result == ["User likes tea"]

    def test_parse_none_returns_no_facts(self, filter_plugin: Any) -> None:
        """Verify <NONE> yields no facts."""
        assert filter_plugin._parse_extraction_response("<NONE>") == []
        assert filter_plugin._parse_extraction_response("<none>") == []

    def test_parse_invalid_json_returns_no_facts(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify invalid JSON yields no facts and logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = filter_plugin._parse_extraction_response("not json at all")
        assert result == []
        assert any("Failed to parse JSON" in record.message for record in caplog.records)

    def test_parse_rejects_non_string_entries(self, filter_plugin: Any) -> None:
        """Verify non-string entries are discarded, keeping only strings."""
        result = filter_plugin._parse_extraction_response('["ok", 42, {"bad": 1}, null, "also"]')
        assert result == ["ok", "also"]

    def test_parse_non_array_object_returns_no_facts(self, filter_plugin: Any) -> None:
        """Verify a JSON object (not an array) yields no facts."""
        result = filter_plugin._parse_extraction_response('{"fact": "User likes tea"}')
        assert result == []


# ========================================================================
# LLM FACT EXTRACTION
# ========================================================================


class TestLLMFactExtraction:
    """Tests for the background ``_extract_facts_with_llm`` task."""

    def _body(self) -> Dict[str, Any]:
        return {
            "model": "chat-model",
            "messages": [
                {"role": "user", "content": "I love hiking."},
                {"role": "assistant", "content": "Noted!"},
            ],
        }

    @pytest.mark.asyncio
    async def test_extract_valid_json_stores_facts(self, filter_plugin: Any) -> None:
        """Verify valid JSON output is parsed and stored via _merge_and_store_facts."""
        mock_chat, mock_gen = _mock_chat_module('["User loves hiking", "User prefers trails"]')
        with (
            _patch_chat_import(mock_chat),
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
        ):
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)

        mock_merge.assert_called_once_with(
            "folder-abc", ["User loves hiking", "User prefers trails"]
        )
        # The payload must use the chat's model and the documented settings.
        payload = mock_gen.call_args[0][1]
        assert payload["model"] == "chat-model"
        assert payload["temperature"] == 0.2
        assert payload["stream"] is False

    @pytest.mark.asyncio
    async def test_extract_json_fence_stores_facts(self, filter_plugin: Any) -> None:
        """Verify a ```json fence response is still parsed and stored."""
        mock_chat, _ = _mock_chat_module('```json\n["Fenced fact"]\n```')
        with (
            _patch_chat_import(mock_chat),
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
        ):
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)
        mock_merge.assert_called_once_with("folder-abc", ["Fenced fact"])

    @pytest.mark.asyncio
    async def test_extract_none_stores_nothing(self, filter_plugin: Any) -> None:
        """Verify <NONE> yields no facts and no merge call."""
        mock_chat, _ = _mock_chat_module("<NONE>")
        with (
            _patch_chat_import(mock_chat),
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
        ):
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)
        mock_merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_invalid_json_stores_nothing(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify invalid JSON is logged and nothing is stored."""
        mock_chat, _ = _mock_chat_module("this is not json")
        with (
            _patch_chat_import(mock_chat),
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
            caplog.at_level(logging.WARNING),
        ):
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)
        mock_merge.assert_not_called()
        assert any("Failed to parse JSON" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_extract_rejects_non_string_entries(self, filter_plugin: Any) -> None:
        """Verify non-string entries in the array are discarded before storage."""
        mock_chat, _ = _mock_chat_module('["good", 42, {"bad": 1}, "also good"]')
        with (
            _patch_chat_import(mock_chat),
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
        ):
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)
        mock_merge.assert_called_once_with("folder-abc", ["good", "also good"])

    @pytest.mark.asyncio
    async def test_extract_uses_explicit_extraction_model(self, filter_plugin: Any) -> None:
        """Verify EXTRACTION_MODEL overrides the chat's model in the LLM payload."""
        filter_plugin.valves.EXTRACTION_MODEL = "extraction-model"
        mock_chat, mock_gen = _mock_chat_module('["Fact"]')
        with (
            _patch_chat_import(mock_chat),
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
        ):
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)
        payload = mock_gen.call_args[0][1]
        assert payload["model"] == "extraction-model"
        mock_merge.assert_called_once_with("folder-abc", ["Fact"])

    @pytest.mark.asyncio
    async def test_extract_generation_failure_handled(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify an LLM failure is logged via logger.exception and nothing is stored."""
        mock_chat = MagicMock()
        mock_chat.generate_chat_completion = AsyncMock(side_effect=RuntimeError("boom"))
        with (
            _patch_chat_import(mock_chat),
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
            caplog.at_level(logging.ERROR),
        ):
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)
        mock_merge.assert_not_called()
        assert any(
            "LLM generation failed during fact extraction" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_extract_import_failure_skips(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify a missing generate_chat_completion import skips extraction gracefully."""
        with (
            patch.object(filter_plugin, "_merge_and_store_facts") as mock_merge,
            caplog.at_level(logging.WARNING),
        ):
            # No open_webui mocks injected: both import attempts fail.
            await filter_plugin._extract_facts_with_llm("folder-abc", self._body(), "user-1", None)
        mock_merge.assert_not_called()
        assert any("generate_chat_completion" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_resolve_user_obj_uses_users_model(self, filter_plugin: Any) -> None:
        """Verify user object resolution uses Users.get_user_by_id with dynamic await."""
        mock_users = MagicMock()
        mock_users.get_user_by_id.return_value = {"id": "user-1"}
        with patch.object(mod, "Users", mock_users):
            user_obj = await filter_plugin._resolve_user_obj("user-1")
        assert user_obj == {"id": "user-1"}
        mock_users.get_user_by_id.assert_called_once_with("user-1")

    @pytest.mark.asyncio
    async def test_resolve_user_obj_awaits_async_users(self, filter_plugin: Any) -> None:
        """Verify an async Users.get_user_by_id is awaited dynamically."""
        mock_users = MagicMock()
        mock_users.get_user_by_id = AsyncMock(return_value={"id": "user-1"})
        with patch.object(mod, "Users", mock_users):
            user_obj = await filter_plugin._resolve_user_obj("user-1")
        assert user_obj == {"id": "user-1"}


# ========================================================================
# MODEL RESOLUTION
# ========================================================================


class TestExtractionModelResolution:
    """Tests for the EXTRACTION_MODEL fallback chain."""

    def test_explicit_model_wins(self, filter_plugin: Any) -> None:
        """Verify EXTRACTION_MODEL is preferred when set."""
        filter_plugin.valves.EXTRACTION_MODEL = "extraction-model"
        body: Dict[str, Any] = {"model": "chat-model"}
        assert filter_plugin._resolve_extraction_model(body) == "extraction-model"

    def test_empty_model_falls_back_to_chat_model(self, filter_plugin: Any) -> None:
        """Verify an empty EXTRACTION_MODEL falls back to the chat's model id."""
        filter_plugin.valves.EXTRACTION_MODEL = ""
        body: Dict[str, Any] = {"model": "chat-model"}
        assert filter_plugin._resolve_extraction_model(body) == "chat-model"

    def test_missing_chat_model_returns_empty(self, filter_plugin: Any) -> None:
        """Verify no model anywhere resolves to an empty string (skips extraction)."""
        filter_plugin.valves.EXTRACTION_MODEL = ""
        body: Dict[str, Any] = {}
        assert filter_plugin._resolve_extraction_model(body) == ""


# ========================================================================
# EXTRACTION INTERVAL GATING
# ========================================================================


class TestExtractionIntervalGating:
    """Tests for the EXTRACTION_INTERVAL throttle and outlet scheduling."""

    def test_should_extract_default_interval(self) -> None:
        """Verify interval=1 schedules extraction on every exchange."""
        assert mod._should_extract("folder-a", 1) is True
        assert mod._should_extract("folder-a", 1) is True
        assert mod._should_extract("folder-a", 1) is True

    def test_should_extract_every_n(self) -> None:
        """Verify interval=N schedules extraction only every Nth exchange (M mod N == 0)."""
        assert mod._should_extract("folder-b", 3) is False
        assert mod._should_extract("folder-b", 3) is False
        assert mod._should_extract("folder-b", 3) is True
        assert mod._should_extract("folder-b", 3) is False

    def test_should_extract_isolation_per_folder(self) -> None:
        """Verify counters are keyed per folder."""
        assert mod._should_extract("folder-x", 2) is False
        assert mod._should_extract("folder-x", 2) is True  # 2 % 2 == 0
        assert mod._should_extract("folder-y", 2) is False  # unaffected by folder-x

    @pytest.mark.asyncio
    async def test_outlet_disabled_auto_learn(self, filter_plugin: Any) -> None:
        """Verify no learning or resolution is performed if AUTO_LEARN_MEMORIES is disabled."""
        filter_plugin.valves.AUTO_LEARN_MEMORIES = False
        body = {"chat_id": "chat-abc"}

        with patch.object(filter_plugin, "_resolve_folder") as mock_resolve:
            result = await filter_plugin.outlet(body)

        assert result == body
        mock_resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_outlet_no_resolved_folder(self, filter_plugin: Any) -> None:
        """Verify outlet exits early if chat has no active folder_id."""
        filter_plugin.valves.AUTO_LEARN_MEMORIES = True
        body = {"chat_id": "chat-abc"}

        with (
            patch.object(filter_plugin, "_resolve_folder", new=AsyncMock(return_value=None)),
            patch("asyncio.create_task") as mock_create_task,
        ):
            result = await filter_plugin.outlet(body)

        assert result == body
        mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_outlet_resolves_folder_via_chats_model(self, filter_plugin: Any) -> None:
        """Verify outlet auto-learning resolves a folder chat via the Chats model.

        The OWUI outlet body carries a top-level ``chat_id`` but no ``metadata``,
        ``folder_id`` or ``user_id``. The user id only arrives through the ``__user__``
        reserved arg, which the framework passes when the handler declares it. Without
        it, ``_resolve_folder`` cannot query ``Chats.get_chat_folder_id`` and auto-learning
        silently no-ops for folder chats.
        """
        filter_plugin.valves.AUTO_LEARN_MEMORIES = True
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id.return_value = "folder-from-outlet"
        body = {"chat_id": "chat-xyz", "messages": []}

        with (
            patch.object(mod, "Chats", mock_chats),
            patch("asyncio.create_task") as mock_create_task,
        ):
            result = await filter_plugin.outlet(body, __user__={"id": "user-1"})

        assert result == body
        mock_chats.get_chat_folder_id.assert_called_once_with("chat-xyz", "user-1")
        mock_create_task.assert_called_once()
        coro = mock_create_task.call_args[0][0]
        coro.close()

    @pytest.mark.asyncio
    async def test_outlet_forwards_user_id_to_resolve_folder(self, filter_plugin: Any) -> None:
        """Verify outlet passes the resolved user id into _resolve_folder (and None by default)."""
        filter_plugin.valves.AUTO_LEARN_MEMORIES = True
        body = {"chat_id": "chat-abc"}

        # With __user__ the id is forwarded.
        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value=None)
        ) as mock_resolve:
            await filter_plugin.outlet(body, __user__={"id": "user-42"})
        mock_resolve.assert_called_once_with(body, "user-42")

        # Backward compatibility: without __user__ the resolver gets None.
        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value=None)
        ) as mock_resolve:
            await filter_plugin.outlet(body)
        mock_resolve.assert_called_once_with(body, None)

    @pytest.mark.asyncio
    async def test_outlet_no_user_id_skips_chats_lookup(self, filter_plugin: Any) -> None:
        """Verify auto-learning does not resolve via Chats when __user__ has no id."""
        filter_plugin.valves.AUTO_LEARN_MEMORIES = True
        mock_chats = MagicMock()
        body = {"chat_id": "chat-xyz", "messages": []}

        with (
            patch.object(mod, "Chats", mock_chats),
            patch("asyncio.create_task") as mock_create_task,
        ):
            result = await filter_plugin.outlet(body, __user__={})

        assert result == body
        mock_chats.get_chat_folder_id.assert_not_called()
        mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_outlet_schedules_async_extraction(self, filter_plugin: Any) -> None:
        """Verify outlet schedules the LLM extraction task asynchronously."""
        filter_plugin.valves.AUTO_LEARN_MEMORIES = True
        body = {"chat_id": "chat-abc"}

        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch("asyncio.create_task") as mock_create_task,
        ):
            result = await filter_plugin.outlet(body)

        assert result == body
        mock_create_task.assert_called_once()
        coro = mock_create_task.call_args[0][0]
        assert coro.__name__ == "_extract_facts_with_llm"
        # Close coroutine explicitly to avoid "coroutine was never awaited" python warning
        coro.close()

    @pytest.mark.asyncio
    async def test_outlet_respects_extraction_interval(self, filter_plugin: Any) -> None:
        """Verify extraction is scheduled only when the interval allows it."""
        filter_plugin.valves.AUTO_LEARN_MEMORIES = True
        filter_plugin.valves.EXTRACTION_INTERVAL = 3
        body = {"chat_id": "chat-abc"}

        with (
            patch.object(
                filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch("asyncio.create_task") as mock_create_task,
        ):
            # Exchange 1 of 3 (1 mod 3 != 0) -> skip
            await filter_plugin.outlet(body)
            assert mock_create_task.call_count == 0

            # Exchange 2 of 3 (2 mod 3 != 0) -> skip
            await filter_plugin.outlet(body)
            assert mock_create_task.call_count == 0

            # Exchange 3 of 3 (3 mod 3 == 0) -> schedule
            await filter_plugin.outlet(body)
            assert mock_create_task.call_count == 1

        for call in mock_create_task.call_args_list:
            coro = call.args[0]
            assert coro.__name__ == "_extract_facts_with_llm"
            coro.close()

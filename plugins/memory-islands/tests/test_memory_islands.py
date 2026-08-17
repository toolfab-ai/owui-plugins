"""Unit tests for Memory Islands filter plugin — no container needed."""

import builtins
import json
import logging
import sqlite3
import types
from pathlib import Path
from typing import Any, Dict
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
        """Verify that initializing the filter plugin creates the memories table with the correct schema."""
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
        assert "folder_id" in col_names
        assert "guidelines" in col_names
        assert "facts" in col_names

        # Verify primary key is folder_id
        folder_id_col = [col for col in columns if col[1] == "folder_id"][0]
        assert folder_id_col[5] == 1  # 1 denotes PRIMARY KEY

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


# ========================================================================
# DATA LOADING
# ========================================================================


class TestDataLoading:
    """Tests loading folder guidelines and facts from local database."""

    def test_load_folder_data_existing(self, filter_plugin: Any, temp_db_path: Path) -> None:
        """Verify loading existing guidelines and facts successfully."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute(
            "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
            (
                "folder-abc",
                "Be professional.",
                json.dumps(["User is a doctor", "User works in NYC"]),
            ),
        )
        conn.commit()
        conn.close()

        guidelines, facts = filter_plugin._load_folder_data("folder-abc")
        assert guidelines == "Be professional."
        assert facts == ["User is a doctor", "User works in NYC"]

    def test_load_folder_data_missing_record(self, filter_plugin: Any) -> None:
        """Verify _load_folder_data returns defaults if no record exists for folder_id."""
        guidelines, facts = filter_plugin._load_folder_data("non-existent-folder")
        assert guidelines == ""
        assert facts == []

    def test_load_folder_data_db_error(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify DB errors inside _load_folder_data are caught and logged."""
        with (
            patch("sqlite3.connect", side_effect=sqlite3.Error("Disk full")),
            caplog.at_level(logging.ERROR),
        ):
            guidelines, facts = filter_plugin._load_folder_data("folder-abc")

        assert guidelines == ""
        assert facts == []
        assert any("Failed to load folder memories" in record.message for record in caplog.records)


# ========================================================================
# INLET GATING
# ========================================================================


class TestInletGating:
    """Tests injecting folder guidelines/memories as system prompt at inlet."""

    @pytest.mark.asyncio
    async def test_inlet_success_injects_prompt(self, filter_plugin: Any) -> None:
        """Verify active folder guidelines and facts are successfully prepended as system message."""
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
                return_value=("Be extremely detailed.", ["User is 8 years old", "Likes science"]),
            ),
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"

        content = messages[0]["content"]
        assert "[Memory Island Active]" in content
        assert "Be extremely detailed." in content
        assert "- User is 8 years old" in content
        assert "- Likes science" in content

        assert messages[1] == {"role": "user", "content": "Explain photosynthesis."}

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


# ========================================================================
# OUTLET AND MEMORY LEARNING
# ========================================================================


class TestMemoryLearning:
    """Tests the extraction and learning of memories from assistant replies."""

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
    async def test_outlet_schedules_async_learning(self, filter_plugin: Any) -> None:
        """Verify outlet correctly schedules memory extraction task asynchronously."""
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
        assert coro.__name__ == "_learn_memories"
        # Close coroutine explicitly to avoid "coroutine was never awaited" python warning
        coro.close()

    @pytest.mark.asyncio
    async def test_learn_memories_empty_messages(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify _learn_memories handles empty message bodies without DB side-effects."""
        body: Dict[str, Any] = {"messages": []}
        await filter_plugin._learn_memories("folder-abc", body)

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute("SELECT * FROM memories").fetchone()
        conn.close()
        assert row is None

    @pytest.mark.asyncio
    async def test_learn_memories_no_learnable_statements(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify assistant replies containing no statements starting with 'I ' or 'The user' are ignored."""
        body = {
            "messages": [
                {"role": "user", "content": "Tell me a joke."},
                {
                    "role": "assistant",
                    "content": "Why did the chicken cross the road?\nTo get to the other side!",
                },
            ]
        }
        await filter_plugin._learn_memories("folder-abc", body)

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute("SELECT * FROM memories").fetchone()
        conn.close()
        assert row is None

    @pytest.mark.asyncio
    async def test_learn_memories_creates_new_facts_in_db(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify learnable facts are extracted from assistant response and stored in a new folder memory record."""
        body = {
            "messages": [
                {"role": "user", "content": "My thoughts on cooking?"},
                {
                    "role": "assistant",
                    "content": "I noticed you like cooking Italian.\nThe user prefers olive oil.\nWait, actually I think you prefer basil too.",
                },
            ]
        }
        await filter_plugin._learn_memories("folder-abc", body)

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute(
            "SELECT guidelines, facts FROM memories WHERE folder_id=?", ("folder-abc",)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == ""  # Guidelines default to empty string
        facts = json.loads(row[1])
        assert facts == [
            "I noticed you like cooking Italian.",
            "The user prefers olive oil.",
        ]

    @pytest.mark.asyncio
    async def test_learn_memories_appends_to_existing_facts(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify new facts are appended to already existing facts in the folder's memories."""
        # Insert pre-existing guidelines and facts
        conn = sqlite3.connect(temp_db_path)
        conn.execute(
            "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
            ("folder-abc", "Be polite.", json.dumps(["I know you love tennis."])),
        )
        conn.commit()
        conn.close()

        body = {
            "messages": [
                {"role": "user", "content": "I also like badminton."},
                {
                    "role": "assistant",
                    "content": "The user mentioned loving badminton.\nI will keep that in mind.",
                },
            ]
        }
        await filter_plugin._learn_memories("folder-abc", body)

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute(
            "SELECT guidelines, facts FROM memories WHERE folder_id=?", ("folder-abc",)
        ).fetchone()
        conn.close()

        assert row is not None
        # Guidelines are preserved when appending new facts
        assert row[0] == "Be polite."
        facts = json.loads(row[1])
        assert facts == [
            "I know you love tennis.",
            "The user mentioned loving badminton.",
            "I will keep that in mind.",
        ]

    @pytest.mark.asyncio
    async def test_learn_memories_db_exception_handled(
        self, filter_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify that any exceptions thrown during memory persistence are handled and logged."""
        body = {
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "I like books."},
            ]
        }

        with (
            patch("sqlite3.connect", side_effect=sqlite3.Error("Connection lost")),
            caplog.at_level(logging.ERROR),
        ):
            # This should not raise an exception to the caller
            await filter_plugin._learn_memories("folder-abc", body)

        assert any("Failed to store folder memories" in record.message for record in caplog.records)


# ========================================================================
# SLASH COMMANDS
# ========================================================================


class TestSlashCommands:
    """Tests for Memory Islands /island- slash commands handled inside inlet."""

    @pytest.mark.asyncio
    async def test_command_outside_folder_redirects_and_informs(self, filter_plugin: Any) -> None:
        """Verify executing a command outside a folder redirects role to system and informs about Global Workspace.

        Uses the realistic OWUI payload: no top-level chat_id/folder_id; the chat lives in
        the Global Workspace so metadata.folder_id is None and _resolve_folder returns None.
        """
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-outside", "folder_id": None},
            "messages": [{"role": "user", "content": "/island-help"}],
        }

        with patch.object(filter_plugin, "_resolve_folder", new=AsyncMock(return_value=None)):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "outside of any folder" in messages[-1]["content"]
        assert "Global Workspace" in messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_command_in_folder_not_treated_as_global_workspace(
        self, filter_plugin: Any
    ) -> None:
        """REGRESSION: a chat inside a folder must NOT be treated as Global Workspace.

        The bug: OWUI pops folder_id/chat_id into body["metadata"]; the plugin read the
        top-level keys which are always None, so _resolve_folder returned None even for a
        chat inside a folder, wrongly triggering the "outside folder" guidance. This test
        asserts that with metadata.folder_id present, the command handler runs the
        folder-specific logic instead.
        """
        body = {
            "metadata": {
                "user_id": "user-1",
                "chat_id": "chat-inside",
                "folder_id": "project-alpha-folder",
            },
            "messages": [
                {"role": "user", "content": "/island-guidelines Be extremely professional."}
            ],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="project-alpha-folder")
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        # Must NOT contain the "outside folder" guidance
        assert "outside of any folder" not in messages[-1]["content"]
        assert "Global Workspace" not in messages[-1]["content"]
        # Folder-specific handling happened instead
        assert "updated the folder guidelines" in messages[-1]["content"]
        assert "Be extremely professional." in messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_help_inside_folder(self, filter_plugin: Any) -> None:
        """Verify /island-help inside a folder returns the detailed markdown system instruction helper message."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-inside", "folder_id": "folder-123"},
            "messages": [{"role": "user", "content": "/island-help"}],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-123")
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "requested help" in messages[-1]["content"]
        assert "beautifully formatted markdown guide" in messages[-1]["content"]
        assert "`/island-guidelines <text>`" in messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_guidelines_with_argument_updates_and_confirms(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify /island-guidelines with an argument updates guidelines and sets confirmation."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-inside", "folder_id": "folder-123"},
            "messages": [
                {"role": "user", "content": "/island-guidelines Be extremely professional."}
            ],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-123")
        ):
            result = await filter_plugin.inlet(body)

        # Check return message
        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "updated the folder guidelines" in messages[-1]["content"]
        assert "Be extremely professional." in messages[-1]["content"]

        # Check DB
        conn = sqlite3.connect(temp_db_path)
        row = conn.execute(
            "SELECT guidelines FROM memories WHERE folder_id=?", ("folder-123",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "Be extremely professional."

    @pytest.mark.asyncio
    async def test_guidelines_without_argument_prompts_usage(self, filter_plugin: Any) -> None:
        """Verify /island-guidelines without an argument prompts for usage."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-inside", "folder_id": "folder-123"},
            "messages": [{"role": "user", "content": "/island-guidelines"}],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-123")
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "without providing any rules text" in messages[-1]["content"]
        assert "politely explain how to use it" in messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_status_inside_folder(self, filter_plugin: Any, temp_db_path: Path) -> None:
        """Verify /island-status inside a folder returns current guidelines and learned facts."""
        # Insert guidelines and facts
        conn = sqlite3.connect(temp_db_path)
        conn.execute(
            "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
            ("folder-123", "Write code carefully.", json.dumps(["Likes Python", "Hates Java"])),
        )
        conn.commit()
        conn.close()

        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-inside", "folder_id": "folder-123"},
            "messages": [{"role": "user", "content": "/island-status"}],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-123")
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "status of the current folder's" in messages[-1]["content"]
        assert "Write code carefully." in messages[-1]["content"]
        assert "- Likes Python" in messages[-1]["content"]
        assert "- Hates Java" in messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_clear_facts_resets_facts(self, filter_plugin: Any, temp_db_path: Path) -> None:
        """Verify /island-clear-facts calls _clear_facts and resets facts to '[]'."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute(
            "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
            ("folder-123", "Write code carefully.", json.dumps(["Likes Python"])),
        )
        conn.commit()
        conn.close()

        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-inside", "folder_id": "folder-123"},
            "messages": [{"role": "user", "content": "/island-clear-facts"}],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-123")
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "cleared all auto-learned facts/memories" in messages[-1]["content"]

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute(
            "SELECT guidelines, facts FROM memories WHERE folder_id=?", ("folder-123",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "Write code carefully."
        assert row[1] == "[]"

    @pytest.mark.asyncio
    async def test_clear_guidelines_resets_guidelines(
        self, filter_plugin: Any, temp_db_path: Path
    ) -> None:
        """Verify /island-clear-guidelines calls _clear_guidelines and resets guidelines to ''."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute(
            "INSERT INTO memories (folder_id, guidelines, facts) VALUES (?, ?, ?)",
            ("folder-123", "Write code carefully.", json.dumps(["Likes Python"])),
        )
        conn.commit()
        conn.close()

        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-inside", "folder_id": "folder-123"},
            "messages": [{"role": "user", "content": "/island-clear-guidelines"}],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-123")
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "cleared the custom folder guidelines" in messages[-1]["content"]

        conn = sqlite3.connect(temp_db_path)
        row = conn.execute(
            "SELECT guidelines, facts FROM memories WHERE folder_id=?", ("folder-123",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == ""
        assert json.loads(row[1]) == ["Likes Python"]

    @pytest.mark.asyncio
    async def test_unknown_command_returns_polite_error(self, filter_plugin: Any) -> None:
        """Verify unknown commands return polite error suggesting /island-help."""
        body = {
            "metadata": {"user_id": "user-1", "chat_id": "chat-inside", "folder_id": "folder-123"},
            "messages": [{"role": "user", "content": "/island-foo"}],
        }

        with patch.object(
            filter_plugin, "_resolve_folder", new=AsyncMock(return_value="folder-123")
        ):
            result = await filter_plugin.inlet(body)

        messages = result["messages"]
        assert len(messages) == 1
        assert messages[-1]["role"] == "system"
        assert "unknown command: '/island-foo'" in messages[-1]["content"]
        assert "suggest typing `/island-help`" in messages[-1]["content"]

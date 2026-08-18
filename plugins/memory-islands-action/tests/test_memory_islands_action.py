"""Unit tests for Memory Islands Manager Action plugin — no container needed."""

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

# Load the memory-islands-action plugin dynamically (built plugin.py, or src/main.py).
mod = load_plugin("memory-islands-action")

pytestmark = pytest.mark.unit


class _FakeHTMLResponse:
    """Minimal stand-in for ``fastapi.responses.HTMLResponse`` used in tests.

    ``fastapi`` is not installed in the repo's dev environment; OWUI provides it
    at runtime, so tests inject this fake via ``sys.modules``.
    """

    def __init__(
        self,
        content: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.content = content
        self.headers: Dict[str, str] = headers or {}
        self.status_code: int = 200


def _patch_fastapi() -> Any:
    """Return a context manager that fakes the ``fastapi.responses`` module."""
    fake_responses = types.SimpleNamespace(HTMLResponse=_FakeHTMLResponse)
    fake_fastapi = types.SimpleNamespace(responses=fake_responses)
    return patch.dict(
        sys.modules,
        {
            "fastapi": fake_fastapi,
            "fastapi.responses": fake_responses,
        },
    )


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Fixture providing the plugin's temporary database path under DATA_DIR."""
    return tmp_path / "memory-islands" / "folder_memories.db"


@pytest.fixture
def action_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Fixture providing an Action plugin instance using a clean temporary database."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _plugin = mod.Action()
    yield _plugin


@pytest.fixture
def action_no_updates(action_plugin: Any) -> Any:
    """Action instance with update notifications disabled (no GitHub API in tests)."""
    action_plugin.valves.ENABLE_UPDATE_NOTIFICATIONS = False
    return action_plugin


# ========================================================================
# DATA DIR RESOLUTION
# ========================================================================


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
# DATABASE INITIALIZATION (shared schema v2, read-only)
# ========================================================================


class TestDatabaseInitialization:
    """Tests for the shared ``folder_memories.db`` initialization (schema v2)."""

    def test_init_databases_creates_schema(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify initializing the Action plugin creates the v2 memories table."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        _plugin = mod.Action()
        temp_db = tmp_path / "memory-islands" / "folder_memories.db"
        assert temp_db.exists()

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("PRAGMA table_info(memories)")
        columns = cursor.fetchall()
        conn.close()

        # Schema columns: (cid, name, type, notnull, dflt_value, pk)
        assert len(columns) == 3
        col_names = [col[1] for col in columns]
        assert col_names == ["folder_id", "facts", "updated_at"]

        folder_id_col = [col for col in columns if col[1] == "folder_id"][0]
        assert folder_id_col[5] == 1  # 1 denotes PRIMARY KEY

    def test_init_databases_drops_legacy_v1_table(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify a legacy v1 table with a guidelines column is dropped and recreated as v2."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        temp_db = tmp_path / "memory-islands" / "folder_memories.db"
        temp_db.parent.mkdir(parents=True, exist_ok=True)

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
            _plugin = mod.Action()

        conn = sqlite3.connect(temp_db)
        col_names = [col[1] for col in conn.execute("PRAGMA table_info(memories)").fetchall()]
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
        """Verify sqlite3 errors during initialization are handled gracefully and logged."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        with (
            patch("sqlite3.connect", side_effect=sqlite3.Error("Failed to connect")),
            caplog.at_level(logging.ERROR),
        ):
            _plugin = mod.Action()
            assert _plugin is not None
            assert any(
                "Failed to initialize memories database" in record.message
                for record in caplog.records
            )


# ========================================================================
# DATABASE READ HELPERS
# ========================================================================


class TestDatabaseReadHelpers:
    """Tests reading folder facts from the shared database (schema v2)."""

    def test_load_folder_data_existing(self, action_plugin: Any, temp_db_path: Path) -> None:
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

        facts = action_plugin._load_folder_data("folder-abc")
        assert facts == ["User is a doctor", "User works in NYC"]

    def test_load_folder_data_missing_record(self, action_plugin: Any) -> None:
        """Verify _load_folder_data returns [] if no record exists for folder_id."""
        assert action_plugin._load_folder_data("non-existent-folder") == []

    def test_load_folder_data_empty_folder_id(self, action_plugin: Any) -> None:
        """Verify _load_folder_data returns [] when folder_id is falsy."""
        assert action_plugin._load_folder_data(None) == []
        assert action_plugin._load_folder_data("") == []

    def test_load_folder_data_db_error(
        self, action_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify DB errors inside _load_folder_data are caught and logged."""
        with (
            patch("sqlite3.connect", side_effect=sqlite3.Error("Disk full")),
            caplog.at_level(logging.ERROR),
        ):
            facts = action_plugin._load_folder_data("folder-abc")

        assert facts == []
        assert any("Failed to load folder memories" in record.message for record in caplog.records)

    def test_is_db_readable_true(self, action_plugin: Any) -> None:
        """Verify a healthy database is reported readable."""
        assert action_plugin._is_db_readable() is True

    def test_is_db_readable_false_on_error(
        self, action_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify a locked/unreadable database is detected for the panel error state."""
        with (
            patch("sqlite3.connect", side_effect=sqlite3.Error("Disk full")),
            caplog.at_level(logging.ERROR),
        ):
            assert action_plugin._is_db_readable() is False
        assert any(
            "Failed to access memories database" in record.message for record in caplog.records
        )


# ========================================================================
# FOLDER RESOLUTION
# ========================================================================


class TestFolderResolution:
    """Tests for resolving the active folder from __metadata__ + __user__ via Chats."""

    async def test_resolve_folder_from_metadata_folder_id(self, action_plugin: Any) -> None:
        """Verify folder_id is read from __metadata__['folder_id'] when present."""
        folder_id = await action_plugin._resolve_folder(
            {"chat_id": "chat-xyz", "folder_id": "test-folder-123"}, {}, "user-1"
        )
        assert folder_id == "test-folder-123"

    async def test_resolve_folder_prefers_metadata_folder_id_over_body(
        self, action_plugin: Any
    ) -> None:
        """Verify metadata.folder_id wins even if a legacy top-level key is present."""
        folder_id = await action_plugin._resolve_folder(
            {"folder_id": "metadata-folder"}, {"folder_id": "top-level-folder"}, "user-1"
        )
        assert folder_id == "metadata-folder"

    async def test_resolve_folder_via_chats_model_using_metadata_chat_id(
        self, action_plugin: Any
    ) -> None:
        """Verify the Chats-model fallback uses __metadata__['chat_id']."""
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id.return_value = "folder-from-chats"
        with patch.object(mod, "Chats", mock_chats):
            folder_id = await action_plugin._resolve_folder(
                {"chat_id": "chat-xyz", "folder_id": None}, {}, "user-1"
            )

        assert folder_id == "folder-from-chats"
        mock_chats.get_chat_folder_id.assert_called_once_with("chat-xyz", "user-1")

    async def test_resolve_folder_chats_model_async_fallback(self, action_plugin: Any) -> None:
        """Verify the dynamic await handles an async Chats.get_chat_folder_id."""
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id = AsyncMock(return_value="folder-from-async-chats")
        with patch.object(mod, "Chats", mock_chats):
            folder_id = await action_plugin._resolve_folder({"chat_id": "chat-xyz"}, {}, "user-1")

        assert folder_id == "folder-from-async-chats"
        mock_chats.get_chat_folder_id.assert_called_once_with("chat-xyz", "user-1")

    async def test_resolve_folder_chats_model_error(
        self, action_plugin: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify errors from the Chats model are captured gracefully and logged."""
        mock_chats = MagicMock()
        mock_chats.get_chat_folder_id.side_effect = RuntimeError("Chats lookup failed")

        with (
            patch.object(mod, "Chats", mock_chats),
            caplog.at_level(logging.ERROR),
        ):
            folder_id = await action_plugin._resolve_folder(
                {"chat_id": "chat-xyz", "folder_id": None}, {}, "user-1"
            )

        assert folder_id is None
        assert any(
            "Failed to resolve folder_id via Chats model" in record.message
            for record in caplog.records
        )

    async def test_resolve_folder_chats_import_failure_returns_none(
        self, action_plugin: Any
    ) -> None:
        """Verify a missing Chats model (import failure) degrades gracefully."""
        with patch.object(mod, "Chats", None):
            folder_id = await action_plugin._resolve_folder(
                {"chat_id": "chat-xyz", "folder_id": None}, {}, "user-1"
            )

        assert folder_id is None

    async def test_resolve_folder_no_metadata_returns_none(self, action_plugin: Any) -> None:
        """Verify _resolve_folder returns None when no metadata/chat/folder info exists."""
        assert await action_plugin._resolve_folder({}, {}, "user-1") is None
        assert await action_plugin._resolve_folder(None, {}, None) is None


# ========================================================================
# COMMAND BUILDING + LOCAL VALIDATION
# ========================================================================


class TestCommandBuilding:
    """Tests for the exact '@memory add:' / '@memory delete:' protocol payloads."""

    def test_build_add_command_exact_payload(self, action_plugin: Any) -> None:
        """Verify add produces the exact '@memory add: <fact>' payload."""
        assert action_plugin._build_add_command("User likes hiking") == (
            "@memory add: User likes hiking"
        )

    def test_build_add_command_trims_whitespace(self, action_plugin: Any) -> None:
        """Verify add trims surrounding whitespace before building the command."""
        assert action_plugin._build_add_command("  User likes hiking  ") == (
            "@memory add: User likes hiking"
        )

    def test_build_add_command_empty_rejected(self, action_plugin: Any) -> None:
        """Verify empty/whitespace submissions never produce a command to post."""
        assert action_plugin._build_add_command("") is None
        assert action_plugin._build_add_command("   ") is None
        assert action_plugin._build_add_command(None) is None

    def test_build_delete_command_exact_payload(self, action_plugin: Any) -> None:
        """Verify delete produces the exact '@memory delete: <fact>' payload."""
        assert action_plugin._build_delete_command("User likes hiking") == (
            "@memory delete: User likes hiking"
        )

    def test_build_delete_command_trims_whitespace(self, action_plugin: Any) -> None:
        """Verify delete trims surrounding whitespace before building the command."""
        assert action_plugin._build_delete_command("  User likes hiking  ") == (
            "@memory delete: User likes hiking"
        )

    def test_build_delete_command_empty_rejected(self, action_plugin: Any) -> None:
        """Verify an empty delete target is never posted."""
        assert action_plugin._build_delete_command("") is None
        assert action_plugin._build_delete_command("   ") is None

    def test_validate_fact_returns_trimmed(self, action_plugin: Any) -> None:
        """Verify _validate_fact trims whitespace and returns the cleaned fact."""
        assert action_plugin._validate_fact("  hello  ") == "hello"

    def test_validate_fact_rejects_empty(self, action_plugin: Any) -> None:
        """Verify _validate_fact returns None for empty/whitespace input."""
        assert action_plugin._validate_fact("") is None
        assert action_plugin._validate_fact("   ") is None
        assert action_plugin._validate_fact(None) is None


# ========================================================================
# PANEL HTML RENDERING
# ========================================================================


class TestPanelHtml:
    """Tests for the Rich UI panel HTML (facts, delete buttons, escaping, states)."""

    def test_panel_html_includes_facts_and_delete_buttons(self, action_plugin: Any) -> None:
        """Verify each stored fact is listed with a delete button carrying the exact fact."""
        html_doc = action_plugin._render_panel_html(
            "folder-abc", ["User likes hiking", "User works in NYC"]
        )
        assert '<span class="fact-text">User likes hiking</span>' in html_doc
        assert '<span class="fact-text">User works in NYC</span>' in html_doc
        assert 'class="delete-btn" data-fact="User likes hiking"' in html_doc
        assert 'class="delete-btn" data-fact="User works in NYC"' in html_doc

    def test_panel_html_escapes_fact_content(self, action_plugin: Any) -> None:
        """Verify fact content is HTML-escaped on render (stored-XSS protection)."""
        malicious = '<script>alert("x")</script> & more'
        html_doc = action_plugin._render_panel_html("folder-abc", [malicious])
        # The raw payload must not appear in the document.
        assert "<script>alert" not in html_doc
        # The escaped payload is rendered inside the fact span and the delete data-fact.
        expected_escaped = "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; more"
        assert f'<span class="fact-text">{expected_escaped}</span>' in html_doc
        assert f'data-fact="{expected_escaped}"' in html_doc

    def test_panel_html_empty_state(self, action_plugin: Any) -> None:
        """Verify the panel shows an empty state plus the add form for an empty folder."""
        html_doc = action_plugin._render_panel_html("folder-abc", [])
        assert "No facts stored for this folder yet" in html_doc
        assert 'id="add-form"' in html_doc
        assert 'id="fact-input"' in html_doc

    def test_panel_html_outside_folder_state(self, action_plugin: Any) -> None:
        """Verify chats outside a folder render a friendly notice with no add form."""
        html_doc = action_plugin._render_panel_html(None, [])
        assert "No active folder" in html_doc
        assert 'id="add-form"' not in html_doc
        assert "Memory Islands memories are scoped to folders" in html_doc

    def test_panel_html_error_state(self, action_plugin: Any) -> None:
        """Verify a DB error renders the error state (banner + add form, no fake empty state)."""
        html_doc = action_plugin._render_panel_html("folder-abc", [], error=True)
        assert "Could not read the folder memory database" in html_doc
        assert 'id="add-form"' in html_doc
        assert "No facts stored" not in html_doc

    def test_panel_html_reports_height_via_postmessage(self, action_plugin: Any) -> None:
        """Verify the panel reports its height to the parent frame (Rich UI reference)."""
        html_doc = action_plugin._render_panel_html("folder-abc", ["fact"])
        assert "iframe:height" in html_doc
        assert "ResizeObserver" in html_doc

    def test_panel_html_posts_commands_with_protocol_prefixes(self, action_plugin: Any) -> None:
        """Verify the panel JS posts the exact protocol commands via input:prompt:submit."""
        html_doc = action_plugin._render_panel_html("folder-abc", ["fact"])
        assert "input:prompt:submit" in html_doc
        assert "postCommand('@memory add: ' + fact);" in html_doc
        assert "postCommand('@memory delete: ' + btn.dataset.fact);" in html_doc

    def test_panel_html_placeholders_replaced(self, action_plugin: Any) -> None:
        """Verify all template placeholders are substituted in the final document."""
        html_doc = action_plugin._render_panel_html("folder-abc", ["fact"])
        assert "{{MAIN_CONTENT}}" not in html_doc
        assert "{{ADD_CMD_PREFIX}}" not in html_doc
        assert "{{DELETE_CMD_PREFIX}}" not in html_doc

    def test_panel_html_local_validation_toast_present(self, action_plugin: Any) -> None:
        """Verify the panel contains the local empty-input validation toast JS."""
        html_doc = action_plugin._render_panel_html("folder-abc", ["fact"])
        assert "Please enter a fact to add." in html_doc
        assert "showToast" in html_doc


# ========================================================================
# VALVES
# ========================================================================


class TestValves:
    """Tests for the Action's admin Valves."""

    def test_defaults(self) -> None:
        valves = mod.Action.Valves()
        assert valves.ENABLE_UPDATE_NOTIFICATIONS is True
        assert valves.CHECK_PREVIEW_RELEASES is False


# ========================================================================
# ACTION HANDLER
# ========================================================================


class TestActionHandler:
    """Tests for the ``action()`` entry point (HTMLResponse + status toasts)."""

    async def test_action_outside_folder_renders_notice(self, action_no_updates: Any) -> None:
        """Verify a chat outside any folder renders the notice and emits a toast."""
        emitter = AsyncMock()
        with (
            patch.object(action_no_updates, "_resolve_folder", new=AsyncMock(return_value=None)),
            _patch_fastapi(),
        ):
            result = await action_no_updates.action(
                body={},
                __user__={"id": "user-1"},
                __event_emitter__=emitter,
                __metadata__={"chat_id": "chat-xyz"},
            )

        assert isinstance(result, _FakeHTMLResponse)
        assert result.headers.get("Content-Disposition") == "inline"
        assert "No active folder" in result.content
        descriptions = [call.args[0]["data"]["description"] for call in emitter.await_args_list]
        assert any("No active folder" in desc for desc in descriptions)

    async def test_action_in_folder_renders_facts(self, action_no_updates: Any) -> None:
        """Verify an active folder renders the stored facts with delete buttons."""
        with (
            patch.object(
                action_no_updates, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(action_no_updates, "_is_db_readable", return_value=True),
            patch.object(
                action_no_updates,
                "_load_folder_data",
                return_value=["User likes hiking", "User likes coffee"],
            ),
            _patch_fastapi(),
        ):
            result = await action_no_updates.action(
                body={},
                __user__={"id": "user-1"},
                __metadata__={"chat_id": "chat-xyz"},
            )

        assert isinstance(result, _FakeHTMLResponse)
        assert result.headers.get("Content-Disposition") == "inline"
        assert "User likes hiking" in result.content
        assert "User likes coffee" in result.content
        assert 'class="delete-btn"' in result.content

    async def test_action_db_error_renders_error_state(self, action_no_updates: Any) -> None:
        """Verify a locked/unreadable DB renders the panel error state."""
        with (
            patch.object(
                action_no_updates, "_resolve_folder", new=AsyncMock(return_value="folder-abc")
            ),
            patch.object(action_no_updates, "_is_db_readable", return_value=False),
            _patch_fastapi(),
        ):
            result = await action_no_updates.action(
                body={},
                __user__={"id": "user-1"},
                __metadata__={"chat_id": "chat-xyz"},
            )

        assert isinstance(result, _FakeHTMLResponse)
        assert "Could not read the folder memory database" in result.content

    async def test_action_no_event_emitter_still_renders(self, action_no_updates: Any) -> None:
        """Verify action() works without an event emitter (defensive)."""
        with (
            patch.object(action_no_updates, "_resolve_folder", new=AsyncMock(return_value=None)),
            _patch_fastapi(),
        ):
            result = await action_no_updates.action(
                body={},
                __user__={"id": "user-1"},
                __metadata__={"chat_id": "chat-xyz"},
            )

        assert isinstance(result, _FakeHTMLResponse)
        assert "No active folder" in result.content

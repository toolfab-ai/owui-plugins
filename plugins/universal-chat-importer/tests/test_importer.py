import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Adding repo root to sys.path to find tests._plugin_loader
repo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

from tests._plugin_loader import load_plugin  # noqa: E402

mod = load_plugin("universal-chat-importer")


class TestMapChatgptToOwui:
    def test_basic_mapping(self):
        conv = {
            "title": "Test Chat",
            "create_time": 1000,
            "update_time": 2000,
            "mapping": {
                "node1": {
                    "message": {
                        "id": "node1",
                        "author": {"role": "user"},
                        "content": {"parts": ["hello"]},
                        "create_time": 1000,
                    },
                    "parent": None,
                },
                "node2": {
                    "message": {
                        "id": "node2",
                        "author": {"role": "assistant"},
                        "content": {"parts": ["hi"]},
                        "create_time": 1100,
                    },
                    "parent": "node1",
                },
            },
            "current_node": "node2",
        }
        tools = mod.Tools()
        chat_data = tools._map_chatgpt_to_owui(conv)

        assert chat_data["title"] == "Test Chat"
        assert len(chat_data["messages"]) == 2
        assert chat_data["messages"][0]["content"] == "hello"
        assert chat_data["messages"][1]["content"] == "hi"
        assert chat_data["history"]["currentId"] == "node2"

    def test_skip_invalid_roles(self):
        conv = {
            "mapping": {
                "node1": {
                    "message": {
                        "id": "node1",
                        "author": {"role": "invalid"},
                        "content": {"parts": ["hello"]},
                    }
                }
            },
            "current_node": "node1",
        }
        tools = mod.Tools()
        chat_data = tools._map_chatgpt_to_owui(conv)
        assert chat_data is None


class TestImportChatgptExport:
    @pytest.mark.asyncio
    async def test_file_not_found_in_db(self):
        tools = mod.Tools()
        with patch.object(tools, "_get_file_path", return_value=None):
            with patch("os.path.isfile", return_value=True):  # For DB path check
                result = await tools.import_chatgpt_export("fake_id", {"id": "user1"})
        assert "not found in database" in result

    @pytest.mark.asyncio
    async def test_full_flow_mocked(self, tmp_path):
        db_file = tmp_path / "webui.db"
        # Mock DB setup
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE file (id TEXT, path TEXT)")
        conn.execute(
            "CREATE TABLE chat (id TEXT, user_id TEXT, title TEXT, chat TEXT, created_at INTEGER, updated_at INTEGER)"
        )
        conn.execute("INSERT INTO file VALUES (?, ?)", ("file1", "/path/to/conv.json"))
        conn.commit()
        conn.close()

        tools = mod.Tools()
        conv_data = [
            {
                "title": "Imported Chat",
                "mapping": {
                    "n1": {
                        "message": {
                            "id": "n1",
                            "author": {"role": "user"},
                            "content": {"parts": ["test"]},
                        }
                    }
                },
                "current_node": "n1",
            }
        ]

        with patch("os.path.isfile", return_value=True):
            with patch.object(mod, "_get_db_path", return_value=str(db_file)):
                with patch.object(tools, "_load_conversations", return_value=conv_data):
                    result = await tools.import_chatgpt_export("file1", {"id": "user1"})

        assert "Successfully imported 1 chats" in result

        # Verify DB insertion
        conn = sqlite3.connect(str(db_file))
        cursor = conn.execute("SELECT title, user_id FROM chat")
        row = cursor.fetchone()
        assert row[0] == "Imported Chat"
        assert row[1] == "user1"
        conn.close()

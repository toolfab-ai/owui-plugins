import sqlite3
import sys
import zipfile
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

    def test_complex_branching(self):
        """Test a chat with multiple branches to ensure active_path reconstruction correctly follows current_node."""
        conv = {
            "title": "Branched Chat",
            "mapping": {
                "n1": {
                    "message": {
                        "id": "n1",
                        "author": {"role": "user"},
                        "content": {"parts": ["start"]},
                    },
                    "parent": None,
                },
                "n2a": {
                    "message": {
                        "id": "n2a",
                        "author": {"role": "assistant"},
                        "content": {"parts": ["branch A"]},
                    },
                    "parent": "n1",
                },
                "n2b": {
                    "message": {
                        "id": "n2b",
                        "author": {"role": "assistant"},
                        "content": {"parts": ["branch B"]},
                    },
                    "parent": "n1",
                },
                "n3b": {
                    "message": {
                        "id": "n3b",
                        "author": {"role": "user"},
                        "content": {"parts": ["continue B"]},
                    },
                    "parent": "n2b",
                },
            },
            "current_node": "n3b",
        }
        tools = mod.Tools()
        chat_data = tools._map_chatgpt_to_owui(conv)

        assert len(chat_data["messages"]) == 3
        assert chat_data["messages"][0]["content"] == "start"
        assert chat_data["messages"][1]["content"] == "branch B"
        assert chat_data["messages"][2]["content"] == "continue B"
        # Branch A should still be in history but not in messages
        assert "n2a" in chat_data["history"]["messages"]
        assert chat_data["history"]["messages"]["n2a"]["content"] == "branch A"

    def test_empty_messages(self):
        """Ensure messages with no content (or only whitespace) are skipped, but system messages are kept."""
        conv = {
            "mapping": {
                "sys": {
                    "message": {
                        "id": "sys",
                        "author": {"role": "system"},
                        "content": {"parts": [""]},
                    },
                    "parent": None,
                },
                "user1": {
                    "message": {
                        "id": "user1",
                        "author": {"role": "user"},
                        "content": {"parts": ["   "]},
                    },
                    "parent": "sys",
                },
                "user2": {
                    "message": {
                        "id": "user2",
                        "author": {"role": "user"},
                        "content": {"parts": ["real content"]},
                    },
                    "parent": "user1",
                },
            },
            "current_node": "user2",
        }
        tools = mod.Tools()
        chat_data = tools._map_chatgpt_to_owui(conv)

        # Expected: sys (kept even if empty), user1 (skipped), user2 (kept)
        # However, looking at the code:
        # if not content and role != "system":
        #     continue
        # user1 has "   ", which stripped is empty? Wait, code says:
        # content = "\n".join([str(p) for p in parts if isinstance(p, (str, int, float))])
        # So "   " stays "   ". If we want to skip whitespace, we need to check .strip()
        # Let's check the code implementation again.
        # Line 209: if not content and role != "system": continue

        assert len(chat_data["messages"]) == 2
        assert chat_data["messages"][0]["id"] == "sys"
        assert chat_data["messages"][1]["id"] == "user2"


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

    @pytest.mark.asyncio
    async def test_corrupted_zip(self, tmp_path):
        """Verify that a non-ZIP file provided as a ZIP handled gracefully."""
        corrupted_file = tmp_path / "corrupted.zip"
        corrupted_file.write_text("not a zip content")

        tools = mod.Tools()
        # _load_conversations returns [] for non-zip if it fails to parse as JSON either
        # Since it's not a zip, it tries to open it as a text file and json.load it.
        # If it's not valid JSON, it will raise json.JSONDecodeError.
        # The import_chatgpt_export catches exceptions.

        with patch.object(tools, "_get_file_path", return_value=str(corrupted_file)):
            with patch("os.path.isfile", return_value=True):
                with patch.object(mod, "_get_db_path", return_value="fake.db"):
                    result = await tools.import_chatgpt_export("file1", {"id": "user1"})

        assert "Import failed" in result

    @pytest.mark.asyncio
    async def test_missing_conversations_json(self, tmp_path):
        """Verify behavior when a ZIP doesn't contain the expected file."""
        zip_file = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("readme.txt", "nothing here")

        tools = mod.Tools()
        with patch.object(tools, "_get_file_path", return_value=str(zip_file)):
            with patch("os.path.isfile", return_value=True):
                with patch.object(mod, "_get_db_path", return_value="fake.db"):
                    result = await tools.import_chatgpt_export("file1", {"id": "user1"})

        assert "Error: Could not find conversations.json" in result

    @pytest.mark.asyncio
    async def test_large_export(self, tmp_path):
        """Mock an export with a large number of chats (e.g. 50) and verify they are all imported."""
        db_file = tmp_path / "webui_large.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE file (id TEXT, path TEXT)")
        conn.execute(
            "CREATE TABLE chat (id TEXT, user_id TEXT, title TEXT, chat TEXT, created_at INTEGER, updated_at INTEGER)"
        )
        conn.execute("INSERT INTO file VALUES (?, ?)", ("file_large", "large.zip"))
        conn.commit()
        conn.close()

        num_chats = 50
        conv_data = []
        for i in range(num_chats):
            conv_data.append(
                {
                    "title": f"Chat {i}",
                    "mapping": {
                        "n": {
                            "message": {
                                "id": "n",
                                "author": {"role": "user"},
                                "content": {"parts": [f"msg {i}"]},
                            }
                        }
                    },
                    "current_node": "n",
                }
            )

        tools = mod.Tools()
        with patch("os.path.isfile", return_value=True):
            with patch.object(mod, "_get_db_path", return_value=str(db_file)):
                with patch.object(tools, "_load_conversations", return_value=conv_data):
                    result = await tools.import_chatgpt_export("file_large", {"id": "user1"})

        assert f"Successfully imported {num_chats} chats" in result
        conn = sqlite3.connect(str(db_file))
        count = conn.execute("SELECT COUNT(*) FROM chat").fetchone()[0]
        assert count == num_chats
        conn.close()

    @pytest.mark.asyncio
    async def test_database_failures(self, tmp_path):
        """Verify that if one chat fails to insert, the rest continue."""
        db_file = tmp_path / "webui_partial.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE file (id TEXT, path TEXT)")
        conn.execute(
            "CREATE TABLE chat (id TEXT, user_id TEXT, title TEXT, chat TEXT, created_at INTEGER, updated_at INTEGER)"
        )
        conn.execute("INSERT INTO file VALUES (?, ?)", ("file_fail", "fail.zip"))
        conn.commit()
        conn.close()

        conv_data = [
            {
                "title": "Chat 1 (Success)",
                "mapping": {
                    "n1": {"message": {"author": {"role": "user"}, "content": {"parts": ["1"]}}}
                },
                "current_node": "n1",
            },
            {
                "title": "Chat 2 (Fail)",
                "mapping": {
                    "n2": {"message": {"author": {"role": "user"}, "content": {"parts": ["2"]}}}
                },
                "current_node": "n2",
            },
            {
                "title": "Chat 3 (Success)",
                "mapping": {
                    "n3": {"message": {"author": {"role": "user"}, "content": {"parts": ["3"]}}}
                },
                "current_node": "n3",
            },
        ]

        tools = mod.Tools()
        original_insert = tools._insert_chat

        def mocked_insert(db, user, data):
            if data["title"] == "Chat 2 (Fail)":
                raise Exception("DB Error")
            return original_insert(db, user, data)

        with patch("os.path.isfile", return_value=True):
            with patch.object(mod, "_get_db_path", return_value=str(db_file)):
                with patch.object(tools, "_load_conversations", return_value=conv_data):
                    with patch.object(tools, "_insert_chat", side_effect=mocked_insert):
                        result = await tools.import_chatgpt_export("file_fail", {"id": "user1"})

        assert "Successfully imported 2 chats" in result
        assert "Encountered errors in 1 chats" in result

        conn = sqlite3.connect(str(db_file))
        titles = [row[0] for row in conn.execute("SELECT title FROM chat").fetchall()]
        assert "Chat 1 (Success)" in titles
        assert "Chat 3 (Success)" in titles
        assert "Chat 2 (Fail)" not in titles
        conn.close()

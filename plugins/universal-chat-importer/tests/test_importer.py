import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests._plugin_loader import load_plugin

# Load the plugin
importer_mod = load_plugin("universal-chat-importer")


@pytest.mark.unit
class TestUniversalChatImporter:
    def setup_method(self):
        self.tools = importer_mod.Tools()
        self.user = {"id": "user-123", "role": "admin"}
        self.event_emitter = AsyncMock()

    @patch("universal_chat_importer.sqlite3.connect")
    @patch("universal_chat_importer.os.path.isfile")
    @patch("universal_chat_importer.zipfile.is_zipfile")
    @patch("universal_chat_importer.zipfile.ZipFile")
    @pytest.mark.asyncio
    async def test_large_import_progress_events(
        self, mock_zip, mock_is_zip, mock_isfile, mock_connect
    ):
        """
        Verify that a large import (200 chats) correctly aggregates multiple JSON files
        and emits progress events every 50 chats.
        """
        # Setup mocks
        mock_isfile.return_value = True
        mock_is_zip.return_value = True

        # Mock DB response for file path
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = mock_conn.execute.return_value
        mock_cursor.fetchone.return_value = ["/path/to/export.zip"]

        # Generate 200 mock chats
        chats = []
        for i in range(200):
            chats.append(
                {
                    "title": f"Chat {i}",
                    "create_time": 1600000000 + i,
                    "mapping": {
                        "node1": {
                            "message": {
                                "id": f"msg_{i}",
                                "author": {"role": "user"},
                                "content": {"parts": [f"Hello {i}"]},
                                "create_time": 1600000000 + i,
                            }
                        }
                    },
                    "current_node": "node1",
                }
            )

        # Mock ZIP content: two files with 100 chats each
        file1_content = json.dumps(chats[:100]).encode("utf-8")
        file2_content = json.dumps(chats[100:]).encode("utf-8")

        mock_zip_obj = mock_zip.return_value.__enter__.return_value
        mock_zip_obj.namelist.return_value = ["conversations.json", "conversations_part2.json"]

        def open_side_effect(name):
            if name == "conversations.json":
                return io.BytesIO(file1_content)
            elif name == "conversations_part2.json":
                return io.BytesIO(file2_content)
            return None

        mock_zip_obj.open.side_effect = open_side_effect

        # Run import
        result = await self.tools.import_chatgpt_export(
            ["file-uuid"], self.user, self.event_emitter
        )

        # Verify result
        assert "Successfully imported 200 chats" in result

        # Verify progress events: every 50 chats + start + end = 4 + 1 + 1 = 6 calls
        # 1. Starting...
        # 2. Importing... (50/200)
        # 3. Importing... (100/200)
        # 4. Importing... (150/200)
        # 5. Importing... (200/200)
        # 6. Successfully... (done=True)

        assert self.event_emitter.call_count == 6

        # Check specific calls
        calls = self.event_emitter.call_args_list
        assert calls[0][0][0]["data"]["description"] == "Starting ChatGPT import..."
        assert "50/200" in calls[1][0][0]["data"]["description"]
        assert "100/200" in calls[2][0][0]["data"]["description"]
        assert "150/200" in calls[3][0][0]["data"]["description"]
        assert "200/200" in calls[4][0][0]["data"]["description"]
        assert "Successfully imported 200 chats" in calls[5][0][0]["data"]["description"]
        assert calls[5][0][0]["data"]["done"] is True

    @patch("universal_chat_importer.sqlite3.connect")
    @patch("universal_chat_importer.os.path.isfile")
    @patch("universal_chat_importer.zipfile.is_zipfile")
    @patch("universal_chat_importer.zipfile.ZipFile")
    @pytest.mark.asyncio
    async def test_malformed_chat_does_not_stop_import(
        self, mock_zip, mock_is_zip, mock_isfile, mock_connect
    ):
        """
        Verify that a single malformed chat doesn't stop the whole import.
        """
        mock_isfile.return_value = True
        mock_is_zip.return_value = True

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = mock_conn.execute.return_value
        mock_cursor.fetchone.return_value = ["/path/to/export.zip"]

        # 3 chats, one malformed (mapping is None will cause error in loop)
        chats = [
            {
                "title": "Good 1",
                "mapping": {
                    "n": {"message": {"author": {"role": "user"}, "content": {"parts": ["hi"]}}}
                },
                "current_node": "n",
            },
            {
                "title": "Bad",
                "mapping": True,  # Will cause AttributeError when .items() is called
            },
            {
                "title": "Good 2",
                "mapping": {
                    "n": {"message": {"author": {"role": "user"}, "content": {"parts": ["hi"]}}}
                },
                "current_node": "n",
            },
        ]

        mock_zip_obj = mock_zip.return_value.__enter__.return_value
        mock_zip_obj.namelist.return_value = ["conversations.json"]
        mock_zip_obj.open.return_value = io.BytesIO(json.dumps(chats).encode("utf-8"))

        result = await self.tools.import_chatgpt_export(
            ["file-uuid"], self.user, self.event_emitter
        )

        assert "Successfully imported 2 chat" in result
        assert "Encountered errors in 1 chat" in result

        # Total chats processed should be 3, but only 2 imported
        assert self.event_emitter.call_count == 2  # Start and End (no 50-chat increments)

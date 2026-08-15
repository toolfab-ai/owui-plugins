"""Unit tests for export-chat plugin — no container needed."""

import io
import json
import os
import sqlite3
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests._plugin_loader import load_plugin

mod = load_plugin("export-chat")


class TestExtractOutputText:
    """``_extract_output_text`` — extracts text from a message output list."""

    def test_empty_list(self):
        assert mod._extract_output_text([]) == ""

    def test_non_dict_items_skipped(self):
        assert mod._extract_output_text(["hello", 42, None]) == ""

    def test_wrong_type_field_skipped(self):
        item = {"type": "not_message", "content": [{"type": "output_text", "text": "x"}]}
        assert mod._extract_output_text([item]) == ""

    def test_missing_content(self):
        item = {"type": "message"}
        assert mod._extract_output_text([item]) == ""

    def test_content_not_list(self):
        item = {"type": "message", "content": "plain string"}
        assert mod._extract_output_text([item]) == ""

    def test_non_dict_parts_skipped(self):
        item = {"type": "message", "content": ["hello", 123, None]}
        assert mod._extract_output_text([item]) == ""

    def test_missing_type_in_part(self):
        item = {"type": "message", "content": [{"text": "hello"}]}
        assert mod._extract_output_text([item]) == ""

    def test_output_text_type_extracted(self):
        item = {"type": "message", "content": [{"type": "output_text", "text": "hello"}]}
        assert mod._extract_output_text([item]) == "hello"

    def test_output_text_empty_string_skipped(self):
        item = {
            "type": "message",
            "content": [
                {"type": "output_text", "text": "hello"},
                {"type": "output_text", "text": ""},
            ],
        }
        assert mod._extract_output_text([item]) == "hello"

    def test_multiple_messages_concatenated(self):
        items = [
            {"type": "message", "content": [{"type": "output_text", "text": "first"}]},
            {"type": "message", "content": [{"type": "output_text", "text": "second"}]},
        ]
        assert mod._extract_output_text(items) == "first\nsecond"

    def test_mixed_part_types_only_output_text(self):
        item = {
            "type": "message",
            "content": [
                {"type": "output_text", "text": "visible"},
                {"type": "image", "text": "image_data"},
            ],
        }
        assert mod._extract_output_text([item]) == "visible"

    def test_all_parts_empty(self):
        item = {
            "type": "message",
            "content": [
                {"type": "output_text", "text": ""},
                {"type": "output_text", "text": ""},
            ],
        }
        assert mod._extract_output_text([item]) == ""


class TestGetMsgText:
    """``_get_msg_text`` — extracts text from a message dict with DB fallback."""

    def test_direct_content(self):
        assert mod._get_msg_text({"content": "hello world"}) == "hello world"

    def test_empty_string_content_returns_empty(self):
        assert mod._get_msg_text({"content": ""}) == ""

    def test_output_list_provided(self):
        msg = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "from output"}],
                }
            ]
        }
        assert mod._get_msg_text(msg) == "from output"

    def test_no_content_no_output(self):
        assert mod._get_msg_text({}) == ""

    def test_output_not_list(self):
        msg = {"output": "not a list"}
        assert mod._get_msg_text(msg) == ""

    def test_db_fallback_with_chat_id_and_id(self, tmp_path):
        msg = {"id": "msg-1", "content": ""}
        payload = json.dumps(
            [{"type": "message", "content": [{"type": "output_text", "text": "db text"}]}]
        )
        db_file = tmp_path / "test.db"
        with patch.object(mod, "_DB_PATH", str(db_file)):
            conn = sqlite3.connect(str(db_file))
            conn.execute("CREATE TABLE chat_message (id TEXT, output TEXT)")
            conn.execute("INSERT INTO chat_message VALUES (?, ?)", ("test-chat-msg-1", payload))
            conn.commit()
            conn.close()
            result = mod._get_msg_text(msg, chat_id="test-chat")
        assert result == "db text"

    def test_db_fallback_no_chat_id(self):
        msg = {"id": "msg-1", "content": ""}
        assert mod._get_msg_text(msg) == ""

    def test_db_fallback_lookup_failure_returns_empty(self):
        msg = {"id": "msg-1", "content": ""}
        with patch.object(mod, "_DB_PATH", "/nonexistent/path/db.db"):
            assert mod._get_msg_text(msg, chat_id="test-chat") == ""


class TestGetOwiDataDir:
    """``_get_owui_data_dir`` — resolves data directory."""

    def test_env_var_set(self):
        with patch.dict(os.environ, {"OPEN_WEBUI_DATA_DIR": "/custom/data"}):
            assert mod._get_owui_data_dir() == "/custom/data"

    def test_env_var_empty_uses_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("platform.system", return_value="Linux"):
                home = os.path.expanduser("~")
                expected = os.path.join(
                    home, "Library", "Application Support", "open-webui", "data"
                )
                result = mod._get_owui_data_dir()
            assert result == expected

    def test_windows_path(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("platform.system", return_value="Windows"):
                home = os.path.expanduser("~")
                expected = os.path.join(os.environ.get("APPDATA", home), "open-webui", "data")
                result = mod._get_owui_data_dir()
            assert result == expected


class TestGetOwiUploadsDir:
    """``_get_owui_uploads_dir`` — resolves uploads directory."""

    def test_env_var_set(self):
        with patch.dict(os.environ, {"OPEN_WEBUI_DATA_DIR": "/custom/data"}):
            assert mod._get_owui_uploads_dir() == "/custom/data/data/uploads"

    def test_env_var_empty_uses_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("platform.system", return_value="Linux"):
                home = os.path.expanduser("~")
                expected = os.path.join(
                    home, "Library", "Application Support", "open-webui", "data", "uploads"
                )
                result = mod._get_owui_uploads_dir()
            assert result == expected


class TestFindFont:
    """``_find_font`` — locates a Unicode TTF font for PDF rendering."""

    def test_font_found_at_known_path(self):
        with patch("os.path.isfile", return_value=True):
            result = mod._find_font()
        assert result == "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    def test_font_not_found_returns_empty_string(self):
        with patch("os.path.isfile", return_value=False):
            with patch("glob.glob", return_value=[]):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = Exception("fc-match not found")
                    with patch("sys.stderr", new_callable=io.StringIO):
                        result = mod._find_font()
        assert result == ""

    def test_fc_match_succeeds(self):
        mock_result = MagicMock()
        mock_result.stdout.strip.return_value = "/usr/share/fonts/dejavu.ttf"

        def isfile_result(path):
            return path == "/usr/share/fonts/dejavu.ttf"

        with patch("os.path.isfile", side_effect=isfile_result):
            with patch("subprocess.run", return_value=mock_result):
                result = mod._find_font()
        assert result == "/usr/share/fonts/dejavu.ttf"

    def test_fc_match_nonexistent_file_falls_through(self):
        mock_result = MagicMock()
        mock_result.stdout.strip.return_value = "/nonexistent/font.ttf"
        with patch("os.path.isfile", return_value=False):
            with patch("subprocess.run", return_value=mock_result):
                with patch("glob.glob", return_value=[]):
                    with patch("sys.stderr", new_callable=io.StringIO):
                        result = mod._find_font()
        assert result == ""

    def test_font_found_in_glob_search(self):
        with patch("os.path.isfile", return_value=False):
            with patch("subprocess.run", side_effect=Exception):
                with patch("glob.glob", return_value=["/usr/share/fonts/DejaVuSans.ttf"]):
                    result = mod._find_font()
        assert result == "/usr/share/fonts/DejaVuSans.ttf"


class TestValves:
    """``Action.Valves`` — pydantic model for plugin configuration."""

    def test_defaults(self):
        valves = mod.Action.Valves()
        assert valves.export_formats == "pdf"
        assert valves.base_url is None

    def test_custom_formats(self):
        valves = mod.Action.Valves(export_formats="csv,word")
        assert valves.export_formats == "csv,word"

    def test_custom_base_url(self):
        valves = mod.Action.Valves(base_url="https://example.com")
        assert valves.base_url == "https://example.com"

    def test_all_fields_custom(self):
        valves = mod.Action.Valves(export_formats="pdf,csv", base_url="http://localhost:8080")
        assert valves.export_formats == "pdf,csv"
        assert valves.base_url == "http://localhost:8080"


class TestResolveFormats:
    """``Action._resolve_formats`` — parses comma-separated format string."""

    def test_defaults_to_pdf(self):
        action = mod.Action()
        assert action._resolve_formats() == ["pdf"]

    def test_single_format(self):
        action = mod.Action()
        action.valves.export_formats = "csv"
        assert action._resolve_formats() == ["csv"]

    def test_multiple_formats(self):
        action = mod.Action()
        action.valves.export_formats = "pdf, csv, word"
        assert action._resolve_formats() == ["pdf", "csv", "word"]

    def test_whitespace_stripped(self):
        action = mod.Action()
        action.valves.export_formats = "  pdf  ,  csv  "
        assert action._resolve_formats() == ["pdf", "csv"]

    def test_lowercased(self):
        action = mod.Action()
        action.valves.export_formats = "PDF, CSV"
        assert action._resolve_formats() == ["pdf", "csv"]

    def test_empty_string_after_strip(self):
        action = mod.Action()
        action.valves.export_formats = ",,"
        assert action._resolve_formats() == []

    def test_mixed_empty_and_valid(self):
        action = mod.Action()
        action.valves.export_formats = "pdf,,csv,"
        assert action._resolve_formats() == ["pdf", "csv"]


class TestSaveAndLink:
    """``Action._save_and_link`` — saves bytes to disk/DB and returns URL."""

    @pytest.mark.asyncio
    async def test_save_pdf_success(self, tmp_path):
        action = mod.Action()
        action.valves.base_url = "http://localhost:3000"
        file_bytes = b"fake pdf content"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                url, name = await action._save_and_link(file_bytes, "chat_export.pdf")
        assert name == "chat_export.pdf"
        assert url is not None
        assert url.startswith("http://localhost:3000")

    @pytest.mark.asyncio
    async def test_save_csv_success(self, tmp_path):
        action = mod.Action()
        action.valves.base_url = "http://localhost:3000"
        file_bytes = b"Role,Message\nuser,hello"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                url, name = await action._save_and_link(file_bytes, "chat_export.csv")
        assert name == "chat_export.csv"
        assert url is not None

    @pytest.mark.asyncio
    async def test_save_and_link_stores_in_db(self, tmp_path):
        action = mod.Action()
        action.valves.base_url = "http://localhost:3000"
        file_bytes = b"fake content"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                await action._save_and_link(file_bytes, "chat_export.pdf")
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                cursor = conn.execute(
                    "SELECT filename, hash, meta FROM file WHERE filename = 'chat_export.pdf'"
                )
                row = cursor.fetchone()
                conn.close()
        assert row is not None
        assert row[0] == "chat_export.pdf"
        assert len(row[1]) == 16

    @pytest.mark.asyncio
    async def test_save_fallback_to_base64_on_error(self, tmp_path):
        action = mod.Action()
        action.valves.base_url = "http://localhost:3000"
        file_bytes = b"fake pdf content"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "nonexistent.db")):
                with patch("builtins.open", side_effect=PermissionError("permission denied")):
                    url, name = await action._save_and_link(file_bytes, "chat_export.pdf")
        assert name == "chat_export.pdf"
        assert url.startswith("data:application/pdf;base64,")

    @pytest.mark.asyncio
    async def test_base_url_from_request_header(self, tmp_path):
        action = mod.Action()
        mock_request = MagicMock()
        mock_request.headers = {"host": "myhost.example.com"}
        mock_request.base_url = None
        file_bytes = b"fake content"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                url, _ = await action._save_and_link(
                    file_bytes, "chat_export.pdf", __request__=mock_request
                )
        assert "https://myhost.example.com" in url

    @pytest.mark.asyncio
    async def test_base_url_from_base_url_attr(self, tmp_path):
        action = mod.Action()
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.base_url = "http://localhost:8080"
        file_bytes = b"fake content"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                url, _ = await action._save_and_link(
                    file_bytes, "chat_export.pdf", __request__=mock_request
                )
        assert "http://localhost:8080" in url

    @pytest.mark.asyncio
    async def test_no_request_uses_env_or_default(self, tmp_path):
        action = mod.Action()
        file_bytes = b"fake content"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                with patch.dict(os.environ, {"WEBUI_URL": "http://custom:9000"}):
                    url, _ = await action._save_and_link(file_bytes, "chat_export.pdf")
        assert "http://custom:9000" in url


class TestAction:
    """``Action.action`` — main entry point for chat export."""

    @pytest.mark.asyncio
    async def test_no_messages_returns_early(self):
        action = mod.Action()
        result = await action.action(body={})
        assert result == {"content": "No messages found to export."}

    @pytest.mark.asyncio
    async def test_no_formats_configured(self):
        action = mod.Action()
        action.valves.export_formats = ""
        result = await action.action(body={"messages": [{"role": "user", "content": "hi"}]})
        assert result == {
            "content": "No export formats configured. Set `export_formats` in plugin settings."
        }

    @pytest.mark.asyncio
    async def test_csv_export_generates_link(self, tmp_path):
        action = mod.Action()
        action.valves.export_formats = "csv"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                emitter = AsyncMock()
                result = await action.action(
                    body={"messages": [{"role": "user", "content": "hello"}]},
                    __event_emitter__=emitter,
                )
        assert "chat_export.csv" in result["content"]
        assert emitter.called

    @pytest.mark.asyncio
    async def test_pdf_export_generates_link(self, tmp_path):
        action = mod.Action()
        action.valves.export_formats = "pdf"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        page = MagicMock()
        page.rect.width = 612
        page.rect.height = 792
        mock_doc.new_page.return_value = page
        mock_fitz.open.return_value = mock_doc
        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            emitter = AsyncMock()
            result = await action.action(
                body={"messages": [{"role": "user", "content": "hello"}]},
                __event_emitter__=emitter,
            )
        assert "chat_export.pdf" in result["content"]
        assert emitter.called

    @pytest.mark.asyncio
    async def test_word_export_generates_link(self, tmp_path):
        action = mod.Action()
        action.valves.export_formats = "word"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
        mock_docx = MagicMock()
        mock_docx.Document.return_value = MagicMock()
        with patch.dict(sys.modules, {"docx": mock_docx}):
            emitter = AsyncMock()
            result = await action.action(
                body={"messages": [{"role": "user", "content": "hello"}]},
                __event_emitter__=emitter,
            )
        assert "chat_export.docx" in result["content"]
        assert emitter.called

    @pytest.mark.asyncio
    async def test_multiple_formats(self, tmp_path):
        action = mod.Action()
        action.valves.export_formats = "pdf, csv"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        page = MagicMock()
        page.rect.width = 612
        page.rect.height = 792
        mock_doc.new_page.return_value = page
        mock_fitz.open.return_value = mock_doc
        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            emitter = AsyncMock()
            result = await action.action(
                body={"messages": [{"role": "user", "content": "hello"}]},
                __event_emitter__=emitter,
            )
        assert "chat_export.pdf" in result["content"]
        assert "chat_export.csv" in result["content"]

    @pytest.mark.asyncio
    async def test_pdf_export_failure_reports_error(self):
        action = mod.Action()
        action.valves.export_formats = "pdf"
        with patch.dict(sys.modules, {"fitz": None}):
            emitter = AsyncMock()
            result = await action.action(
                body={"messages": [{"role": "user", "content": "hello"}]},
                __event_emitter__=emitter,
            )
        assert "No files were generated" in result["content"]

    @pytest.mark.asyncio
    async def test_no_event_emitter_still_returns(self):
        action = mod.Action()
        action.valves.export_formats = "pdf"
        with patch.dict(sys.modules, {"fitz": None}):
            result = await action.action(
                body={"messages": [{"role": "user", "content": "hello"}]},
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_action_returns_content_links(self, tmp_path):
        action = mod.Action()
        action.valves.base_url = "http://test:3000"
        action.valves.export_formats = "csv"
        with patch.object(mod, "_UPLOAD_DIR", str(tmp_path)):
            with patch.object(mod, "_DB_PATH", str(tmp_path / "webui.db")):
                conn = sqlite3.connect(str(tmp_path / "webui.db"))
                conn.execute(
                    """CREATE TABLE file
                    (id TEXT, user_id TEXT, hash TEXT, filename TEXT, path TEXT,
                     data TEXT, meta TEXT, created_at INTEGER, updated_at INTEGER)"""
                )
                conn.commit()
                conn.close()
                result = await action.action(
                    body={"messages": [{"role": "user", "content": "hello"}]},
                )
        assert "chat_export.csv" in result["content"]
        assert "http://test:3000" in result["content"]


class TestPdfOutputValidity:
    """PDF output validation using the real PyMuPDF library."""

    def generate_pdf_bytes(self, chat_text: str) -> bytes:
        import fitz

        buf = io.BytesIO()
        doc = fitz.open()
        page = doc.new_page()
        rect = fitz.Rect(50, 50, page.rect.width - 50, page.rect.height - 50)
        page.insert_textbox(rect, chat_text, fontsize=11)
        doc.save(buf, garbage=4, deflate=True)
        doc.close()
        return buf.getvalue()

    def test_pdf_has_correct_structure(self):
        text = "User: hello\nAssistant: world"
        pdf_bytes = self.generate_pdf_bytes(text)

        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert doc.page_count == 1
        page = doc[0]
        extracted = page.get_text().strip()
        assert "User:" in extracted
        assert "hello" in extracted
        assert "Assistant:" in extracted
        assert "world" in extracted
        doc.close()

    def test_pdf_with_multiple_messages(self):
        text = "\n\n".join(
            f"{role}: {msg}"
            for role, msg in [("User", "first"), ("Assistant", "second"), ("User", "third")]
        )
        pdf_bytes = self.generate_pdf_bytes(text)

        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert doc.page_count == 1
        page = doc[0]
        extracted = page.get_text()
        assert "User:" in extracted and "first" in extracted
        assert "Assistant:" in extracted and "second" in extracted
        assert "third" in extracted
        doc.close()

    def test_pdf_handles_unicode(self):
        text = "User: café, français, 中文, русский, goodbye"
        pdf_bytes = self.generate_pdf_bytes(text)

        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        extracted = page.get_text()
        assert "café" in extracted
        doc.close()

    def test_pdf_long_text_wraps(self):
        long_msg = "Hello " * 200
        text = f"User: {long_msg}"
        pdf_bytes = self.generate_pdf_bytes(text)

        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert doc.page_count >= 1
        doc.close()

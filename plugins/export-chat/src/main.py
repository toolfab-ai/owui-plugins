import csv
import hashlib
import io
import json
import os
import platform
import sqlite3
import sys
import time
import uuid
from typing import Optional

from pydantic import BaseModel, Field


def _get_owui_data_dir() -> str:
    data_dir = os.environ.get("OPEN_WEBUI_DATA_DIR", "")
    if data_dir:
        return data_dir
    home = os.path.expanduser("~")
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", home), "open-webui", "data")
    return os.path.join(home, "Library", "Application Support", "open-webui", "data")


def _get_owui_uploads_dir() -> str:
    data_dir = os.environ.get("OPEN_WEBUI_DATA_DIR", "")
    if data_dir:
        return os.path.join(data_dir, "data", "uploads")
    home = os.path.expanduser("~")
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", home), "open-webui", "data", "uploads")
    return os.path.join(home, "Library", "Application Support", "open-webui", "data", "uploads")


def _extract_output_text(output: list) -> str:
    texts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        parts = item.get("content")
        if not parts or not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "output_text":
                t = part.get("text", "")
                if t:
                    texts.append(str(t))
    return "\n".join(texts)


def _fetch_msg_output(chat_id: str, message_id: str) -> list:
    try:
        composite_id = f"{chat_id}-{message_id}"
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.execute("SELECT output FROM chat_message WHERE id = ?", (composite_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            data = row[0]
            if isinstance(data, str):
                data = json.loads(data)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[export-chat] DB lookup failed: {e}", file=sys.stderr)
    return []


def _get_msg_text(msg: dict, chat_id: str = None) -> str:
    content = msg.get("content", "")
    if content:
        return content
    output = msg.get("output")
    if (not output or not isinstance(output, list)) and chat_id and msg.get("id"):
        output = _fetch_msg_output(chat_id, msg["id"])
    if not output or not isinstance(output, list):
        return ""
    return _extract_output_text(output)


def _find_font() -> str:
    import glob as _glob
    import subprocess as _subprocess

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    try:
        result = _subprocess.run(
            ["fc-match", "-f", "%{file}", "DejaVu Sans"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        path = result.stdout.strip()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    try:
        result = _subprocess.run(
            ["fc-match", "-f", "%{file}", "sans-serif"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        path = result.stdout.strip()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    pattern_dirs = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        "/System/Library/Fonts",
        "/Library/Fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts"),
    ]
    for d in pattern_dirs:
        matches = _glob.glob(os.path.join(d, "**", "*"), recursive=True)
        for p in matches:
            bn = os.path.basename(p).lower()
            if bn in (
                "dejavusans.ttf",
                "liberationsans-regular.ttf",
                "arial.ttf",
                "arialunicode.ttf",
            ):
                return p
            if bn.startswith("dejavusans") and bn.endswith(".ttf"):
                return p
    print(
        "[export-chat] WARNING: No Unicode font found. Install fonts-dejavu-core (Debian) or google-noto-sans-fonts (Fedora) for Cyrillic PDF support.",
        file=sys.stderr,
    )
    return ""


_DB_PATH = os.path.join(
    os.environ.get("OPEN_WEBUI_DATA_DIR", ""),
    "data",
    "webui.db",
)
if not os.path.isfile(_DB_PATH):
    _DB_PATH = os.path.join(_get_owui_data_dir(), "webui.db")

_UPLOAD_DIR = os.path.join(
    os.environ.get("OPEN_WEBUI_DATA_DIR", ""),
    "data",
    "uploads",
)
if not os.path.isdir(_UPLOAD_DIR):
    _UPLOAD_DIR = _get_owui_uploads_dir()


class Action:
    class Valves(BaseModel):
        export_formats: str = Field(
            default="pdf",
            description="Comma-separated list of formats to export. Options: pdf, csv, word",
        )
        base_url: Optional[str] = Field(
            default=None,
            description="Override the base URL for download links. Auto-detected if unset.",
        )

    def __init__(self):
        self.valves = self.Valves()

    def _resolve_formats(self) -> list[str]:
        return [f.strip().lower() for f in self.valves.export_formats.split(",") if f.strip()]

    async def _save_and_link(self, file_bytes: bytes, filename: str, __request__=None) -> tuple:
        import base64 as _b64

        ext = os.path.splitext(filename)[1].lower()
        mt = {
            ".pdf": "application/pdf",
            ".csv": "text/csv",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        content_type = mt.get(ext, "application/octet-stream")

        try:
            file_id = str(uuid.uuid4())
            with open(os.path.join(_UPLOAD_DIR, file_id), "wb") as f:
                f.write(file_bytes)

            file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
            now = int(time.time())

            conn = sqlite3.connect(_DB_PATH)
            conn.execute(
                """INSERT OR REPLACE INTO file
                   (id, user_id, hash, filename, path, data, meta, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_id,
                    "",
                    file_hash,
                    filename,
                    os.path.join(_UPLOAD_DIR, file_id),
                    "{}",
                    json.dumps(
                        {
                            "name": filename,
                            "content_type": content_type,
                            "size": len(file_bytes),
                            "source": "export-chat",
                            "generated": True,
                        }
                    ),
                    now,
                    now,
                ),
            )
            conn.commit()
            conn.close()

            base_url = self.valves.base_url
            if not base_url and __request__:
                try:
                    host = __request__.headers.get("x-original-host") or __request__.headers.get(
                        "host"
                    )
                    if host:
                        base_url = f"https://{host}"
                except Exception:
                    pass
            if not base_url and __request__:
                try:
                    base_url = str(__request__.base_url).rstrip("/")
                except Exception:
                    pass
            if not base_url:
                base_url = os.environ.get("WEBUI_URL", "http://localhost:3000")
            base_url = base_url.rstrip("/")

            url = f"{base_url}/api/v1/files/{file_id}/content"
            return (url, filename)

        except Exception as e:
            print(f"[export-chat] Save failed: {e}", file=sys.stderr)
            try:
                data = _b64.b64encode(file_bytes).decode("ascii")
                return (f"data:{content_type};base64,{data}", filename)
            except Exception:
                return (None, None)

    async def action(
        self,
        body: dict,
        __user__=None,
        __event_emitter__=None,
        __event_call__=None,
        __request__=None,
        __metadata__=None,
    ) -> Optional[dict]:
        messages = body.get("messages", [])
        if not messages:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "No messages found to export.", "done": True},
                    }
                )
            return {"content": "No messages found to export."}

        chat_id = body.get("chat_id") or (__metadata__ or {}).get("chat_id")

        formats = self._resolve_formats()
        if not formats:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "No export formats configured.", "done": True},
                    }
                )
            return {
                "content": "No export formats configured. Set `export_formats` in plugin settings."
            }

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"Exporting as {', '.join(formats)}...", "done": False},
                }
            )

        chat_text = "\n\n".join(
            f"{msg.get('role', 'unknown').capitalize()}: {_get_msg_text(msg, chat_id)}"
            for msg in messages
        )

        output_links = []

        def _download_js(url: str, name: str) -> str:
            u = json.dumps(url)
            n = json.dumps(name)
            return f"""var a=document.createElement("a");a.href={u};a.download={n};document.body.appendChild(a);a.click();a.remove();"""

        if "pdf" in formats:
            try:
                import fitz

                buf = io.BytesIO()
                doc = fitz.open()
                page = doc.new_page()
                rect = fitz.Rect(50, 50, page.rect.width - 50, page.rect.height - 50)
                font_path = _find_font()
                page.insert_textbox(rect, chat_text, fontsize=11, fontfile=font_path or None)
                doc.save(buf, garbage=4, deflate=True)
                doc.close()
                buf.seek(0)
                url, name = await self._save_and_link(buf.read(), "chat_export.pdf", __request__)
                if url:
                    output_links.append(f"[{name}]({url})")
                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "execute",
                                "data": {"code": _download_js(url, name)},
                            }
                        )
            except Exception as e:
                print(f"[export-chat] PDF export failed: {e}", file=sys.stderr)
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {"description": f"PDF export failed: {e}", "done": True},
                        }
                    )

        if "csv" in formats:
            try:
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["Role", "Message"])
                for msg in messages:
                    writer.writerow([msg.get("role", ""), _get_msg_text(msg, chat_id)])
                url, name = await self._save_and_link(
                    buf.getvalue().encode("utf-8"), "chat_export.csv", __request__
                )
                if url:
                    output_links.append(f"[{name}]({url})")
                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "execute",
                                "data": {"code": _download_js(url, name)},
                            }
                        )
            except Exception as e:
                print(f"[export-chat] CSV export failed: {e}", file=sys.stderr)
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {"description": f"CSV export failed: {e}", "done": True},
                        }
                    )

        if "word" in formats:
            try:
                from docx import Document

                buf = io.BytesIO()
                document = Document()
                for msg in messages:
                    role = msg.get("role", "unknown").capitalize()
                    content = _get_msg_text(msg, chat_id)
                    document.add_paragraph(f"{role}: {content}")
                document.save(buf)
                buf.seek(0)
                url, name = await self._save_and_link(buf.read(), "chat_export.docx", __request__)
                if url:
                    output_links.append(f"[{name}]({url})")
                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "execute",
                                "data": {"code": _download_js(url, name)},
                            }
                        )
            except Exception as e:
                print(f"[export-chat] Word export failed: {e}", file=sys.stderr)
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {"description": f"Word export failed: {e}", "done": True},
                        }
                    )

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Export complete", "done": True},
                }
            )

        if not output_links:
            return {
                "content": "No files were generated. Check that required dependencies are installed and plugin logs."
            }

        return {"content": "Chat exported:\n\n" + "\n".join(output_links)}

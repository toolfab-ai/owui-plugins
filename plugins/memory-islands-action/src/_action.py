from __future__ import annotations

import asyncio
import html
import inspect
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from open_webui.models.chats import Chats
except ImportError:
    try:
        from open_webui.apps.webui.models.chats import Chats
    except ImportError:
        Chats = None  # noqa: N806

# ---------------------------------------------------------------------------
# Internal panel-command protocol (OQ-3, Option 1)
# ---------------------------------------------------------------------------
# The Manager panel has no silent iframe→Python callback. Add/delete round-trips
# flow through the chat: the panel posts ``@memory add: <fact>`` /
# ``@memory delete: <fact>`` via
# ``parent.postMessage({type:'input:prompt:submit', data:{prompt:'<command>'}})``
# and the Memory Islands Filter inlet (FR-011) intercepts the command, executes
# the DB operation, and rewrites the message into a confirmation reply. This
# Action NEVER writes the shared database — it only posts the command.
_PANEL_ADD_PREFIX: str = "@memory add: "
_PANEL_DELETE_PREFIX: str = "@memory delete: "


# ========================================================================
# PANEL HTML TEMPLATE
# ========================================================================
# The panel is a raw-HTML srcdoc iframe. It reports its height via postMessage
# and submits commands via ``input:prompt:submit``. ``{{MAIN_CONTENT}}`` is
# replaced with the state-specific body; ``{{ADD_CMD_PREFIX}}`` and
# ``{{DELETE_CMD_PREFIX}}`` are injected from the Python constants above so the
# panel JS always posts the exact protocol commands.
_PANEL_TEMPLATE: str = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Memory Islands Manager</title>
<style>
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 18px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: #1f2328;
  background: transparent;
}
@media (prefers-color-scheme: dark) {
  body { color: #e6edf3; }
}
.panel { max-width: 640px; margin: 0 auto; }
h1 { font-size: 16px; margin: 0 0 4px; font-weight: 600; }
.subtitle { font-size: 13px; opacity: 0.75; margin: 0 0 14px; }
.list { list-style: none; padding: 0; margin: 0 0 14px; }
.fact-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 8px;
  margin-bottom: 6px;
}
.fact-text { flex: 1; overflow-wrap: anywhere; white-space: pre-wrap; }
.delete-btn {
  flex-shrink: 0;
  background: none;
  border: 1px solid rgba(201, 59, 59, 0.5);
  color: #c93b3b;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
}
.delete-btn:hover { background: rgba(201, 59, 59, 0.12); }
.add-form { display: flex; gap: 8px; }
.add-form input[type="text"] {
  flex: 1;
  padding: 7px 10px;
  border: 1px solid rgba(128, 128, 128, 0.4);
  border-radius: 8px;
  font-size: 14px;
  background: transparent;
  color: inherit;
}
.add-form button {
  padding: 7px 14px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #ffffff;
  font-size: 14px;
  cursor: pointer;
}
.add-form button:hover { background: #1d4ed8; }
.banner { border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 13px; }
.banner.error {
  border: 1px solid rgba(201, 59, 59, 0.5);
  background: rgba(201, 59, 59, 0.08);
}
.notice {
  border: 1px solid rgba(37, 99, 235, 0.4);
  background: rgba(37, 99, 235, 0.08);
  border-radius: 8px;
  padding: 12px 14px;
}
.notice p { margin: 0 0 8px; }
.notice p:last-child { margin-bottom: 0; }
.empty { font-size: 13px; opacity: 0.8; margin: 0 0 14px; }
#toast {
  position: fixed;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: #1f2937;
  color: #f9fafb;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
  z-index: 10;
  max-width: 80%;
  text-align: center;
}
#toast.visible { opacity: 1; }
</style>
</head>
<body>
<div class="panel">
  <h1>Memory Islands Manager</h1>
  <p class="subtitle">Folder-scoped facts for the Memory Islands filter</p>
  {{MAIN_CONTENT}}
</div>
<div id="toast" role="status" aria-live="polite"></div>
<script>
function reportHeight() {
  var h = document.documentElement.scrollHeight;
  parent.postMessage({ type: 'iframe:height', height: h }, '*');
}
window.addEventListener('load', reportHeight);
if (typeof ResizeObserver !== 'undefined') {
  new ResizeObserver(reportHeight).observe(document.body);
}

function postCommand(cmd) {
  parent.postMessage({ type: 'input:prompt:submit', data: { prompt: cmd } }, '*');
}

function showToast(message) {
  var toast = document.getElementById('toast');
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(window.__miToastTimer);
  window.__miToastTimer = setTimeout(function () {
    toast.classList.remove('visible');
  }, 3000);
}

var addForm = document.getElementById('add-form');
if (addForm) {
  addForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var input = document.getElementById('fact-input');
    var fact = (input.value || '').trim();
    if (!fact) {
      showToast('Please enter a fact to add.');
      return;
    }
    postCommand('{{ADD_CMD_PREFIX}}' + fact);
    input.value = '';
  });
}

document.querySelectorAll('.delete-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    postCommand('{{DELETE_CMD_PREFIX}}' + btn.dataset.fact);
  });
});
</script>
</body>
</html>"""


# ========================================================================
# ACTION MIXIN
# ========================================================================


class ActionMixin:
    """Message-toolbar Action: Rich UI panel to view/add/delete folder facts."""

    def _escape_html(self, text: str) -> str:
        """HTML-escape a string for safe rendering inside the panel.

        Prevents stored-XSS from fact content learned by the LLM or entered by
        users: all fact text is escaped on render.
        """
        return html.escape(text or "", quote=True)

    async def _resolve_folder(
        self,
        metadata: Optional[Dict[str, Any]],
        body: Dict[str, Any],
        user_id: Optional[str],
    ) -> Optional[str]:
        """Resolve the active folder_id for the Action panel.

        Mirrors the Memory Islands Filter's resolution chain: the payload
        metadata ``folder_id`` first (when OWUI carries it), then the Chats
        model fallback via ``Chats.get_chat_folder_id(chat_id, user_id)`` with a
        resilient import and dynamic await for async callables.
        """
        meta: Dict[str, Any] = metadata or {}

        # 1. Modern OWUI carries folder_id inside the payload metadata.
        folder_id: Optional[str] = meta.get("folder_id") or body.get("folder_id")
        if folder_id:
            return folder_id

        # 2. Legacy fallback through the Chats model.
        chat_id: Optional[str] = meta.get("chat_id") or body.get("chat_id")
        if not chat_id or Chats is None or not user_id:
            return None
        try:
            res: Any = Chats.get_chat_folder_id(chat_id, user_id)
            if inspect.isawaitable(res) or asyncio.iscoroutine(res):
                return await res
            return res
        except Exception:
            logger.exception("Failed to resolve folder_id via Chats model.")
            return None

    def _validate_fact(self, fact: str) -> Optional[str]:
        """Return the trimmed fact, or None for empty/whitespace-only input.

        Mirrors the panel's local validation so the Python command builders
        never emit an invalid ``@memory add:`` / ``@memory delete:`` command.
        """
        cleaned: str = (fact or "").strip()
        return cleaned or None

    def _build_add_command(self, fact: str) -> Optional[str]:
        """Build the internal add command for the Filter's panel-command channel.

        Returns ``None`` when the fact is empty/whitespace-only so nothing is
        posted (local validation). The Filter executes the DB write.
        """
        cleaned: Optional[str] = self._validate_fact(fact)
        if cleaned is None:
            return None
        return f"{_PANEL_ADD_PREFIX}{cleaned}"

    def _build_delete_command(self, fact: str) -> Optional[str]:
        """Build the internal delete command for the Filter's panel-command channel.

        Delete targets an exact stored fact (which is never empty after the
        Filter trims on write); returns ``None`` only for defensive validation.
        """
        cleaned: Optional[str] = self._validate_fact(fact)
        if cleaned is None:
            return None
        return f"{_PANEL_DELETE_PREFIX}{cleaned}"

    # ------------------------------------------------------------------
    # Panel rendering
    # ------------------------------------------------------------------

    def _render_facts_list_html(self, facts: List[str]) -> str:
        """Render stored facts as list items, each with an exact-match delete button."""
        if not facts:
            return (
                '<div class="empty">No facts stored for this folder yet. '
                "Add the first fact below, or let the Memory Islands filter "
                "learn facts automatically as you chat.</div>"
            )
        items: List[str] = []
        for fact in facts:
            escaped: str = self._escape_html(fact)
            items.append(
                f'<li class="fact-item">'
                f'<span class="fact-text">{escaped}</span>'
                f'<button type="button" class="delete-btn" data-fact="{escaped}">Delete</button>'
                f"</li>"
            )
        return f'<ul class="list">{"".join(items)}</ul>'

    def _render_folder_main_html(self, facts: List[str], error: bool) -> str:
        """Render the main content for an active folder (facts / empty / error + add form).

        The add form posts through the chat even in the error state: the Filter
        is the writer and may have recovered even if this read failed.
        """
        parts: List[str] = []
        if error:
            parts.append(
                '<div class="banner error">Could not read the folder memory '
                "database. If the issue persists, check the plugin logs and try "
                "again.</div>"
            )
        else:
            parts.append(self._render_facts_list_html(facts))
        parts.append(
            '<form id="add-form" class="add-form" autocomplete="off">'
            '<input id="fact-input" type="text" name="fact" '
            'placeholder="Add a fact to remember…" />'
            '<button type="submit">Add fact</button>'
            "</form>"
        )
        return "\n".join(parts)

    def _render_outside_folder_main_html(self) -> str:
        """Render a friendly notice for chats outside any folder (no DB access)."""
        return (
            '<div class="notice">'
            "<p><strong>No active folder.</strong></p>"
            "<p>Memory Islands memories are scoped to folders. Open this action "
            "from a chat that lives inside a folder to view, add, or delete the "
            "facts stored for that folder.</p>"
            "</div>"
        )

    def _render_panel_html(
        self,
        folder_id: Optional[str],
        facts: List[str],
        error: bool = False,
    ) -> str:
        """Render the full Rich UI panel document as an HTML string.

        All fact content is HTML-escaped on render to prevent stored-XSS. The
        document renders inside the OWUI srcdoc iframe and reports its height via
        postMessage.
        """
        if error:
            main_content: str = self._render_folder_main_html(facts, error=True)
        elif not folder_id:
            main_content = self._render_outside_folder_main_html()
        else:
            main_content = self._render_folder_main_html(facts, error=False)

        return (
            _PANEL_TEMPLATE.replace("{{MAIN_CONTENT}}", main_content)
            .replace("{{ADD_CMD_PREFIX}}", _PANEL_ADD_PREFIX)
            .replace("{{DELETE_CMD_PREFIX}}", _PANEL_DELETE_PREFIX)
        )

    def _render_panel_response(
        self,
        folder_id: Optional[str],
        facts: List[str],
        error: bool = False,
    ) -> Any:
        """Return the panel as an inline HTMLResponse for the OWUI Rich UI iframe.

        ``fastapi`` is only guaranteed inside Open WebUI, so the import is lazy
        and resilient (mirrors export-chat's lazy optional-dependency imports).
        """
        from fastapi.responses import HTMLResponse

        html: str = self._render_panel_html(folder_id, facts, error)
        return HTMLResponse(content=html, headers={"Content-Disposition": "inline"})

    # ------------------------------------------------------------------
    # Event emitter helpers
    # ------------------------------------------------------------------

    async def _emit_status(self, __event_emitter__: Any, description: str, done: bool) -> None:
        """Emit a status toast via the event emitter."""
        await __event_emitter__(
            {"type": "status", "data": {"description": description, "done": done}}
        )

    # ------------------------------------------------------------------
    # Action entry point
    # ------------------------------------------------------------------

    async def action(
        self,
        body: Dict[str, Any],
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Any = None,
        __event_call__: Any = None,
        __request__: Any = None,
        __metadata__: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Handle the Memory Islands Manager message-toolbar button.

        Resolves the active folder from ``__metadata__['chat_id']`` +
        ``__user__['id']`` (with the same fallbacks as the Filter) and returns a
        Rich UI panel (HTMLResponse, ``Content-Disposition: inline``) listing the
        folder's stored facts with add/delete controls. Add/delete round-trips
        flow through the chat via ``input:prompt:submit`` and are executed by the
        Memory Islands Filter inlet — this Action never writes the shared DB.
        """
        if __event_emitter__:
            await self._emit_status(__event_emitter__, "Opening Memory Islands Manager…", False)

        try:
            if __user__ and self.valves.ENABLE_UPDATE_NOTIFICATIONS:
                try:
                    update_msg: Optional[str] = await self._get_update_notification(__user__)
                    if update_msg and __event_emitter__:
                        await self._emit_status(__event_emitter__, update_msg, False)
                except Exception:
                    logger.exception("Failed to check for updates.")

            folder_id: Optional[str] = await self._resolve_folder(
                __metadata__, body, (__user__ or {}).get("id")
            )

            if not folder_id:
                logger.info("Memory Islands Manager opened for a chat outside any folder.")
                if __event_emitter__:
                    await self._emit_status(
                        __event_emitter__,
                        "No active folder — facts are managed inside folder chats.",
                        True,
                    )
                return self._render_panel_response(None, [])

            error: bool = not self._is_db_readable()
            facts: List[str] = self._load_folder_data(folder_id) if not error else []
            logger.info(
                "Memory Islands Manager rendered %d facts for folder %s.",
                len(facts),
                folder_id,
            )
            return self._render_panel_response(folder_id, facts, error=error)
        except Exception:
            logger.exception("Failed to render Memory Islands Manager panel.")
            if __event_emitter__:
                await self._emit_status(
                    __event_emitter__, "Failed to open Memory Islands Manager.", True
                )
            return self._render_panel_response(None, [], error=True)

## Requirements

- **Python 3.11+** with the built-in `sqlite3` module — no external database is required.
- **Open WebUI with folder support** to scope each memory island to a folder.
- **No external API keys** — Memory Islands extracts facts with the internal Open WebUI generation engine (`open_webui.utils.chat.generate_chat_completion`), so it uses the models already configured in your instance.

---

## Quick start

1. **Install the plugin** — follow the steps in [Installation](#installation) to install **Memory Islands** from a URL or the Open WebUI Community.
2. **Enable the Filter** — in Open WebUI, go to **Admin Settings** -> **Filters**, enable **Memory Islands**, and review the Valves.
3. **Disable the native Open WebUI Memories** — in **Workspace** -> **Settings** -> **Memories**, turn off the memories toggle. Custom memory plugins inject their own context, and double-injection of memories breaks prompt caching and causes context duplication.
4. **Create a folder** — in the workspace sidebar, create a dedicated folder for each project or context you want to isolate.
5. **Start a chat inside the folder** — open a new chat that lives inside that folder.
6. **Watch facts auto-learn** — as you chat, Memory Islands extracts and stores new facts in the background (LLM-driven, language-agnostic), scoped to the folder.
7. **Manage facts (optional)** — install the companion **Memory Islands Manager** Action to view, add, and delete the folder's facts from a Rich UI panel.
8. **Per-folder instructions (optional)** — set the folder's native System Prompt in the folder settings. This replaces the old per-folder guidelines mechanism, which was removed.

---

## Description

**Memory Islands** is an Open WebUI `Filter` that provides dynamic, folder-scoped context isolation and memory management. Each project folder keeps its own learned facts, so every chat inside the folder automatically receives the right context — and none of the noise from other projects.

### Unique Features

- **Folder-Scoped Context Isolation** — learned facts are injected only into chats inside the folder they belong to (via the `inlet` hook).
- **Automatic LLM Fact Extraction** — after each exchange, a background LLM call extracts "facts worth remembering" with a strict JSON contract (via the internal `open_webui.utils.chat.generate_chat_completion` engine) and stores them per folder (via the `outlet` hook). Extraction is **language-agnostic** and never blocks the chat pipeline.
- **Configurable Extraction** — `EXTRACTION_MODEL` lets admins route extraction to a cheap/custom model (leave empty to reuse the chat's model); `EXTRACTION_INTERVAL` controls how often an exchange is analyzed.
- **No-Leakage Guarantee** — when `ISOLATE_BY_DEFAULT` is enabled, chats outside a folder receive no injected context at all, preventing cross-folder contamination.
- **Companion Manager Action** — the **Memory Islands Manager** Action (separate install) adds a message-toolbar button that opens a Rich UI panel to view, add, and delete facts for the active folder.
- **Native Per-Folder System Prompts** — per-folder instructions are handled by the native Open WebUI folder System Prompt (folder settings), which replaces the plugin's old custom guidelines mechanism.

---

## Problem Statement

Open WebUI uses folders to organize chats, but custom instructions and "memory" are effectively global. This creates two problems:

1. **Cross-Folder Memory Leakage** — instructions or remembered facts configured for one project unintentionally influence chats in unrelated folders, producing context contamination and confused responses.
2. **Context Bloat** — without scoped memory, users must repeat background context in every chat or rely on a single global memory that mixes unrelated projects.

Earlier versions tried to learn facts by scanning assistant replies for English prefixes (`"I "` / `"The user"`) — brittle, English-centric, and unreliable in real conversations.

**Memory Islands** solves this by turning each folder into a self-contained "memory island": auto-learned facts are extracted by a background LLM call (language-agnostic, strict JSON contract), scoped to the folder they were learned in, injected only into chats inside that folder, and never leak into the global workspace.

---

## Valves (Configuration)

Administrators can configure the plugin globally through **Admin Settings** -> **Filters** -> **Memory Islands** -> **Valves**:

| Valve Name | Type | Default | Description |
|------------|------|---------|-------------|
| **ISOLATE_BY_DEFAULT** | `bool` | `True` | Enforce strict isolation: chats outside a folder receive no injected context. |
| **AUTO_LEARN_MEMORIES** | `bool` | `True` | Automatically extract and save new memories from chats. |
| **EXTRACTION_MODEL** | `str` | `""` | Model id used for background fact extraction. Leave empty to reuse the chat's model. |
| **EXTRACTION_INTERVAL** | `int` | `1` | Analyze the chat for new facts every N exchanges. |
| **ENABLE_UPDATE_NOTIFICATIONS** | `bool` | `True` | Enable background checking for plugin updates. |
| **CHECK_PREVIEW_RELEASES** | `bool` | `False` | Whether to include pre-releases in update checks. |

---

## User Valves (per-user overrides)

This plugin does **not** define any User Valves. All behavior is configured globally by administrators through the Admin Valves above.

---

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/toolfab-ai/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** (or **Tools**) -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Memory Islands** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

### Companion Action (optional)

To view, add, and delete folder facts from a Rich UI panel, also install the **Memory Islands Manager** Action (a separate `plugin.py` on the same [Releases](https://github.com/toolfab-ai/owui-plugins/releases) page, or search for **Memory Islands Manager** on the Open WebUI Community). It shares the same local database and submits changes through the chat.

---

## Database

- The local SQLite database is created at `$DATA_DIR/memory-islands/folder_memories.db` and is shared with the Memory Islands Manager Action.
- Schema v2 stores `folder_id` (primary key), `facts` (JSON array of strings, deduplicated and capped at 200), and `updated_at` (ISO 8601).
- Legacy v1 databases (which also stored `guidelines`) are recreated with the v2 schema on startup — **no migration is performed** and no guidelines are carried over (the native folder System Prompt is their replacement).

---

## About the `@memory` prefix

Any **last user message** that starts with `@memory` is treated as an **internal panel command** for the Memory Islands Manager Action — not as a regular chat message. For example, a message like `@memorylane is fun` is not sent to the model as-is: the plugin recognizes the reserved prefix, does not change any memory, and answers with a polite explanation. Only the manager panel emits well-formed commands (`@memory add: <fact>` / `@memory delete: <fact>`); all other messages are left untouched.

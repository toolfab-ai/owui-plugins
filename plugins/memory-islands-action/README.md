## Requirements

- **Open WebUI v0.10+** with folder support.
- The **Memory Islands** Filter plugin installed and enabled — the Manager Action is its companion UI and shares the same `folder_memories.db`. The Action panel submits add/delete commands through the chat and the Filter executes them.
- **No external API keys** — the panel reads the shared local SQLite database and posts commands through your existing chat.

## Quick start

1. **Install the plugin** — follow the steps in [Installation](#installation) to install **Memory Islands Manager** from a URL or the Open WebUI Community.
2. **Install the Memory Islands Filter** (if not already installed) and enable it in **Admin Settings** -> **Filters**.
3. **Create a folder** in the workspace sidebar and open a chat inside it.
4. **Open the manager** — click the **Memory Islands** button in the message toolbar of any chat inside the folder.
5. **View facts** — the panel lists all learned facts for the active folder.
6. **Add a fact** — type a fact and press **Add fact**; the panel submits the command through the chat and the Memory Islands filter stores it (you confirm one prompt dialog, then a confirmation appears in the chat).
7. **Delete a fact** — click **Delete** next to a fact; the panel submits the exact fact for removal and the filter deletes it.
8. **Chats outside a folder** — the panel shows a friendly notice; memories are only managed inside folders.

> [!TIP]
> For best results with custom memory plugins, **disable the native Open WebUI Memories** (Workspace -> Settings -> Memories -> disable the memories toggle). Double-injection of memories breaks prompt caching and causes context duplication.

## Description

**Memory Islands Manager** is an Open WebUI `Action` plugin that renders a message-toolbar button opening a Rich UI panel for managing the active folder's learned facts: view the list, add a fact, and delete individual facts. It is the companion UI for the **Memory Islands** Filter, which learns folder-scoped facts automatically.

### Key Features

- **Visible toolbar button** — a "Memory Islands" action button on every chat message opens the manager panel.
- **Rich UI panel** — an inline iframe that lists all stored facts for the active folder, each with a delete button, plus a text input to add new facts. Includes an empty state, an error state, and an outside-folder notice.
- **Safe by design** — all fact content is HTML-escaped on render (stored-XSS protection), and the panel never talks to the backend directly.
- **Command-channel interactivity** — add/delete round-trips flow through the chat via `parent.postMessage({type:'input:prompt:submit', ...})`; the Memory Islands Filter inlet intercepts the command, executes the database write, and confirms in the chat. No security-lowering settings are required.
- **Shared database** — reads the same `$DATA_DIR/memory-islands/folder_memories.db` (schema v2) the Filter writes.

## Problem Statement

Open WebUI folders organize chats, but there is no native UI to inspect or edit facts learned by a plugin per folder. After the Memory Islands Filter learned facts automatically, users had no visible way to review or correct them. A message-toolbar Action button is the supported OWUI Action UX and gives users a panel to view, add, and delete folder-scoped facts — while keeping all writes owned by the Filter through the internal panel-command channel.

## Valves (Configuration)

Administrators can configure the plugin globally through **Admin Settings** -> **Functions** -> **Memory Islands Manager** -> **Valves**:

| Valve Name | Type | Default | Description |
|------------|------|---------|-------------|
| **ENABLE_UPDATE_NOTIFICATIONS** | `bool` | `True` | Enable background checking for plugin updates. |
| **CHECK_PREVIEW_RELEASES** | `bool` | `False` | Whether to include pre-releases in update checks. |

## User Valves (per-user overrides)

This plugin does **not** define any User Valves. All behavior is configured globally by administrators through the Admin Valves above.

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/toolfab-ai/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** (or **Tools**) -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Memory Islands Manager** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

## How the panel communicates

Open WebUI Action embeds are raw-HTML `srcdoc` iframes with no silent iframe-to-Python callback. The Manager panel therefore submits add/delete work through the chat using the internal panel-command protocol (shared with the Memory Islands Filter):

- **Add**: `parent.postMessage({type:'input:prompt:submit', data:{prompt:'@memory add: <fact>'}}, '*')`
- **Delete**: `parent.postMessage({type:'input:prompt:submit', data:{prompt:'@memory delete: <exact fact>'}}, '*')`

The Memory Islands Filter inlet intercepts these internal commands, performs the database write for the resolved folder, and replies with a concise confirmation. One confirmation dialog per action is expected Open WebUI behavior for cross-origin embeds. The Action itself never writes the shared database.
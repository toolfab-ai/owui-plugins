# Universal Chat Importer

## Quick start

### Method A: File Upload
1.  **Upload** your ChatGPT export (ZIP or `conversations.json`) to the chat.
2.  **Ask** the AI to "import my ChatGPT history from the uploaded file."
3.  **Wait** for the process to complete. You will see status updates as the chats are imported.

### Method B: Direct Server Path (For Large Files)
1.  **Place** your large export file (e.g., `export.zip`) into an allowed directory on the server (default: `/app/backend/data`).
2.  **Ask** the AI to "import my ChatGPT history from the server path /app/backend/data/export.zip".
3.  **Wait** for the process to complete.

## Description

The Universal Chat Importer is an Open WebUI Tool that allows users to import chat history from external platforms directly into their Open WebUI instance using natural language.

### Key Features
- **Natural Language Tooling**: Trigger imports by simply asking the AI to process your uploaded export files or server paths.
- **Large File Support**: Bypass upload limits by importing files directly from the server filesystem.
- **Security**: Admin-controlled list of allowed import directories.
- **Hierarchy Preservation**: Maps ChatGPT's complex message branching (DAG) into Open WebUI's chat tree.
- **Bulk Import**: Process entire export archives (ZIP or JSON) in one go.
- **Progress Reporting**: Real-time status updates via events during the database insertion process.

## Problem Statement

Migrating existing AI conversations to Open WebUI can be a manual and tedious process. This plugin provides a tool that the AI can use to automatically parse and insert chat history from external exports into your local database, preserving message structure and timestamps.

## Valves (Configuration)

| Valve | Default | Description |
|---|---|---|
| `ENABLE_UPDATE_NOTIFICATIONS` | `True` | If enabled, the plugin will check GitHub for new releases. |
| `CHECK_PREVIEW_RELEASES` | `False` | If enabled, check for preview/dev/pre-release versions. |
| `DEFAULT_MODEL` | `gpt-4o` | The model name to assign to imported chats. |
| `ALLOWED_IMPORT_DIRECTORIES` | `['/app/backend/data']` | List of filesystem paths allowed for direct imports. |

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/toolfab-ai/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Universal Chat Importer** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

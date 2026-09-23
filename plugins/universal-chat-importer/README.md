# Universal Chat Importer

## Quick start

### Method: File Upload
1.  **Upload** one or more ChatGPT export files (ZIP or `conversations.json`) to the chat.
2.  **Ask** the AI to "import my ChatGPT history from the uploaded files."
3.  **Wait** for the process to complete. You will see status updates as the chats are imported.

## Description

The Universal Chat Importer is an Open WebUI Tool that allows users to import chat history from external platforms directly into their Open WebUI instance using natural language.

### Key Features
- **Natural Language Tooling**: Trigger imports by simply asking the AI to process your uploaded export files.
- **Bulk Import**: Support for multiple file uploads in a single request.
- **Hierarchy Preservation**: Maps ChatGPT's complex message branching (DAG) into Open WebUI's chat tree.
- **Progress Reporting**: Real-time status updates via events and detailed logs during the database insertion process.
- **Non-Blocking Execution**: Large imports run in background threads to keep the UI responsive.

## Problem Statement

Migrating existing AI conversations to Open WebUI can be a manual and tedious process. This plugin provides a tool that the AI can use to automatically parse and insert chat history from external exports into your local database, preserving message structure and timestamps.

## Valves (Configuration)

| Valve | Default | Description |
|---|---|---|
| `ENABLE_UPDATE_NOTIFICATIONS` | `True` | If enabled, the plugin will check GitHub for new releases. |
| `CHECK_PREVIEW_RELEASES` | `False` | If enabled, check for preview/dev/pre-release versions. |
| `DEFAULT_MODEL` | `gpt-4o` | The model name to assign to imported chats. |

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/toolfab-ai/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Universal Chat Importer** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

# Universal Chat Importer

## Description

The Universal Chat Importer is an Open WebUI Tool that allows users to import chat history from external platforms directly into their Open WebUI instance. The MVP focus is on ChatGPT exports, supporting both ZIP archives and raw `conversations.json` files.

What is it for?
- Moving your long-standing conversations from ChatGPT to a self-hosted Open WebUI instance.
- Preserving the context and history of your AI interactions across platforms.

What are its unique features?
- **Hierarchy Preservation**: Maps ChatGPT's complex message branching (DAG) into Open WebUI's chat tree.
- **Natural Language Interaction**: Since it's a Tool, the LLM can assist you in the import process once you upload the file.
- **Bulk Import**: Process entire export archives in one go.

## Problem Statement

While Open WebUI has built-in import features, they are often tucked away in settings menus. This Tool approach brings the import capability into the chat itself, making it more accessible and allowing the AI to help summarize or navigate the imported history immediately.

## Quick start

1.  Upload your ChatGPT export (ZIP or `conversations.json`) to the Open WebUI chat.
2.  Ask the AI to "import my ChatGPT history from the uploaded file."
3.  The AI will call the `import_chatgpt_export` tool with the file ID.
4.  Once complete, your imported chats will appear in your chat history sidebar.

## Valves (Configuration)

- `DEFAULT_MODEL`: The model name to assign to imported chats (default: `gpt-4o`).

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/toolfab-ai/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Tools** -> **+ New Tool** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Universal Chat Importer** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

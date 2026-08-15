## Quick start

1. In Open WebUI, navigate to **Admin Settings** -> **Functions** -> **Export Chat** -> **Valves** to configure your desired export formats (default: `pdf,csv,word`).
2. Open any chat session.
3. Click the **Export Chat** button in the message action toolbar.
4. Download links for the requested formats will appear in the chat interface, and the files will be downloaded automatically.

## Description

**Export Chat** is an Open WebUI action plugin that allows users to export entire chat sessions into professional formats, including **PDF**, **CSV**, and **Word (.docx)** files. 

This plugin is a modernized, robust, and highly reliable version of the legacy `export_chat` community script, fully optimized for compatibility with the latest Open WebUI v0.10+ platforms.

### Key Features
- **Multi-Format Export**: Export chats in PDF, CSV, and Word format simultaneously or choose specific ones.
- **Auto-Download Injection**: Automatically triggers client-side file downloads using inline JavaScript injection.
- **Robust Font Fallbacks**: Features automatic system font detection (e.g., DejaVu Sans, Arial Unicode) to support non-ASCII and Cyrillic character encodings seamlessly in PDF outputs.
- **Multi-Domain & Reverse Proxy Support**: Automatically resolves secure download URLs via the `X-Original-Host` reverse proxy header or `WEBUI_URL` environment variables.

## Problem Statement

When sharing or archiving conversations, users often need to export their chat logs to structured files for offline viewing, compliance, or external analysis. While legacy community scripts existed, they are unmaintained, do not work on newer Open WebUI installations (such as v0.10+), lack proper non-ASCII font support for PDF exports, and fail to generate correct URLs behind reverse proxies. 

This plugin solves these compatibility, encoding, and network routing issues, offering a modern and robust chat export capability.

## Valves (Configuration)

The plugin can be configured by administrators through the Open WebUI Admin interface using the following Valves:

| Valve Name | Type | Default | Description |
|------------|------|---------|-------------|
| **export_formats** | `str` | `"pdf"` | Comma-separated list of formats to export. Supported values: `pdf`, `csv`, `word`. |
| **base_url** | `str` | `None` | Explicit manual override for the download link base URL. If unset, it is auto-detected. |

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/open-webui/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** (or **Tools**) -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Export Chat** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

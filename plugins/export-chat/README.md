This action based on https://openwebui.com/posts/export_chat_75a32274 plugin, which haven't being updated for 10 month and can't be installed in owui `0.10.2` 

## Status
In development

## Export Chat

Exports chat messages to PDF, CSV, and/or Word (.docx) format.

## Usage

1. Click the **Export Chat** button in the message action toolbar.
2. The export formats are configured in the plugin settings (Valves).
3. Download links appear in the chat.

## Configuration

### Admin Valves
- `export_formats` — Comma-separated list of formats: `pdf`, `csv`, `word` (default: `pdf,csv,word`)
- `base_url` — Override the base URL for download links (auto-detected if unset)

### User Valves
- `export_formats` — Per-user override. Set to `"default"` to inherit the admin setting.

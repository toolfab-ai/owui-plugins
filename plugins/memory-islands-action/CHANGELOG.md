# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New **Memory Islands Manager** Action plugin (v0.2.0) — a message-toolbar button that opens a Rich UI panel to view, add, and delete folder-scoped facts for the Memory Islands Filter.
- Folder resolution from `__metadata__['chat_id']` and `__user__['id']` via the Chats model, with the same resilient import, dynamic await, and fallbacks as the Memory Islands Filter.
- Rich UI panel rendering via `HTMLResponse` with `Content-Disposition: inline`: stored facts listed with exact-match delete buttons, an add-fact text input, an empty state, an error state, and an outside-folder notice.
- Stored-XSS protection: all fact content is HTML-escaped on render.
- Internal panel-command channel: add/delete round-trips are posted through the chat via `parent.postMessage({type:'input:prompt:submit', data:{prompt:'@memory add: <fact>'}})` / `@memory delete: <fact>` and executed by the Memory Islands Filter inlet; the Action never writes the shared database directly.
- Local validation in the panel: empty or whitespace-only add submissions show a status toast and are never posted.
- iframe height reporting via `postMessage({type:'iframe:height'})` per the Rich UI reference.
- Shared database read helpers (`_resolve_data_dir`, `_init_databases` ensuring schema v2, `_load_folder_data`) mirroring the Filter's implementations, with `timeout=5` and graceful sqlite3 error handling.
- Update notifier with the `memory-islands-action/` release tag prefix and `ENABLE_UPDATE_NOTIFICATIONS` / `CHECK_PREVIEW_RELEASES` admin valves.
- Unit and integration tests (folder resolution with a mocked Chats model, panel HTML generation and escaping, exact command payloads, local validation, schema v2 read helpers, and generated-command-to-Filter-parser protocol compatibility).
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- LLM-based fact extraction: folder facts are now learned automatically from the last exchange of every chat via a background LLM call with a strict JSON contract.
- New admin valves: `EXTRACTION_MODEL` (model id used for background fact extraction; leave empty to reuse the chat's model) and `EXTRACTION_INTERVAL` (analyze the chat for new facts every N exchanges).
- Memory Islands Manager Action companion plugin (separate install) to view, add, and delete folder facts from a Rich UI panel.
- Internal panel-command channel for the Memory Islands Manager Action panel: add/delete actions submitted from the panel are executed by the Filter (stored/deleted in the folder's facts) and confirmed in the chat with a concise reply; malformed commands or commands outside a folder produce a polite explanation instead of changing memory.

### Changed
- Fact learning is now LLM-driven and language-agnostic, replacing the brittle English-prefix scan of assistant replies (`"I "` / `"The user"`).
- Database schema v2: the `memories` table now stores `facts` and `updated_at` (the `guidelines` column is gone); legacy v1 databases are recreated automatically without migrating guidelines.

### Removed
- Custom folder guidelines — use the native Open WebUI folder System Prompt instead.
- All `/island-*` slash commands (`/island-help`, `/island-guidelines`, `/island-status`, `/island-clear-guidelines`, `/island-clear-facts`).
# Changelog

## [Unreleased]

### Added
- Added `import_chatgpt_from_path` tool for importing exports directly from the server filesystem, bypassing upload limits.
- Added `ALLOWED_IMPORT_DIRECTORIES` Valve for security, restricting direct path imports to admin-defined folders.
- Initial implementation of Universal Chat Importer Tool.
- Support for ChatGPT ZIP and `conversations.json` imports.
- Automatic mapping of ChatGPT hierarchy (DAG) to Open WebUI chat tree.
- Database integration with Open WebUI's `chat` table.
- Summary reporting of imported/failed chats.
- Progress reporting via status events during the import process.

### Changed
- Optimized tool triggers by updating `import_chatgpt_export` docstring with more explicit action keywords (PARSE, EXECUTE).
- Refactored core import logic into a private `_execute_import` method for reusability.
- Added logging for LLM tool invocation visibility in server logs.
- Refactored `import_chatgpt_export` to be non-blocking using `asyncio.to_thread`.

### Fixed
- Fixed "endless loading" issue during large chat imports by offloading heavy JSON parsing and DB operations.

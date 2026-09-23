# Changelog

## [Unreleased]

### Added
- Support for importing multiple uploaded files in a single tool call.
- Enhanced logging for ZIP and JSON processing, visible in server logs.
- Added explicit trigger instructions to the tool docstring to improve LLM invocation reliability.

### Changed
- Refactored `import_chatgpt_export` to accept a list of file IDs (`file_ids: List[str]`).
- Improved progress reporting with cumulative summaries for multiple files.

### Removed
- Removed direct path support (`import_chatgpt_from_path`) and the associated `ALLOWED_IMPORT_DIRECTORIES` Valve for improved security and simplified workflow.

### Fixed
- Fixed "nothing happened" issue reported by users by making the tool docstring more aggressive and explicit about execution.

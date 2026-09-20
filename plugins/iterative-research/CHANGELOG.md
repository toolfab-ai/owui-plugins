# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
## [Unreleased]

### Added
- Pre-flight configuration validation to ensure at least one search engine (SearXNG or Tavily) is configured and a backend model is specified in the valves before execution.
- Prominent inline, user-facing critical markdown warning banners at the very top of responses when configurations or backend models are missing or invalid.
- Robust unit test coverage for validation rules, including only-Tavily, only-SearXNG, and unexpected falsy valve types.
- Explicit `requirements` metadata field for automated dependency provisioning in isolated environments (v10+).

### Changed
- Removed model auto-detection logic completely to strictly enforce manual MODEL configuration in valves and avoid unexpected database model lookups.

### Fixed
- Misleading exit state ("All Information Gaps Resolved") when the planning LLM call failed or returned an empty response.
- Runtime LLM failure handling in both planning and synthesis phases to raise clear inline errors and halt execution immediately, preventing token and API waste.
- **Open WebUI v11 Compatibility**: Refactored internal imports (`Models`, `generate_chat_completion`) to support both legacy and modern `open_webui` namespaces.
- **Resilience**: Implemented dynamic sync/async resolution for `Users` model calls to ensure stability across database driver upgrades.

## [0.9.2] - 2026-08-15

### Fixed
- Integration tests: Robust Open WebUI container startup verification to prevent transient CI network handshake failures.

## [0.9.1] - 2026-08-15

### Added
- Compiled with Open WebUI Community compatibility forward declaration (`class Pipe: pass` injection).

## [0.9.0] - 2026-08-15

### Added
- Temporal awareness: Automatic UTC date-time injection into LLM prompts for search planning and report synthesis.

### Fixed
- Robust configuration resolution: Support for `UserValves` passed as standard Python dictionaries, fixing issues with per-user overrides for SearXNG URL and Co-STORM steering.
- Resilience: Improved `pipe` entry point to correctly resolve valves from `__user__` object context.

## [0.1.0-beta.1] - 2026-08-15

### Added
- Initial implementation of the autonomous multi-turn deep research loop.
- Built-in parallel web scraper using BeautifulSoup4 with robust SSRF validation protection.
- Support for Tavily Search and SearXNG search engines.
- Co-STORM style human-in-the-loop steering to pause and adjust search parameters interactively.
- Native Open WebUI citation event emission for seamless references rendering.
- Background update checking against GitHub releases API to notify administrators.

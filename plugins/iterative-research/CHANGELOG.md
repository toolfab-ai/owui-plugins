# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Fixed

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

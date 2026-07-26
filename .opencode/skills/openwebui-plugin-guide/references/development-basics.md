# Development Basics: Structure, Naming, and Docstrings

## Project Structure

### File Location
- Single code file: `plugins/{type}/{name}/{name}.py`
- Never create separate source files for different languages
- Built-in i18n support required for UI and log messages

### Required Files
- `README.md` (English)
- `README_CN.md` (Chinese)
- Plugin Python file with standardized docstring

## Docstring Standard (Frontmatter)

Every plugin file must start with a standardized docstring:

```python
"""
title: Plugin Name
author: Your Name
author_url: https://github.com/your-name
funding_url: https://github.com/open-webui
version: 0.1.0
icon_url: data:image/svg+xml;base64,<base64-encoded-svg>
requirements: dependency1==1.0.0, dependency2>=2.0.0
description: Brief description of plugin functionality.
"""
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Display name in the admin UI |
| `author` | Yes | Creator name |
| `author_url` | No | Link to author's profile/repo |
| `funding_url` | No | Link for sponsorship |
| `version` | Yes | Version identifier (SemVer) |
| `icon_url` | Action plugins | Base64 SVG or URL to icon |
| `required_open_webui_version` | No | Minimum compatible version |
| `requirements` | No | Comma-separated pip packages |
| `description` | Yes | Brief description |

### Icon URL Notes
- Required for Action plugins
- Use Lucide Icons for base64-encoded SVGs
- **Use hosted URLs instead of base64** — base64 icons bloat the `/api/models` API response significantly
- A 500 KB base64 icon on 20 models adds ~10 MB of payload

## Language & Code Requirements

- **Python** only (single file)
- Use `async` for all I/O operations
- All Valves fields must use **UPPER_SNAKE_CASE**
- Must dynamically switch UI, prompts, and logs based on user language
- Dependencies listed in `requirements:` frontmatter are auto-installed via pip

## Metadata Auto-Fill (v0.9.6+)

When creating a new tool/function/skill, the editor reads the frontmatter and auto-fills Name, ID, and Description fields from `title` and `description` if not already filled.

## Naming Conventions

- **Short and punchy**: e.g., "FlashCard", "DeepRead"
- **Avoid generic names**: don't use "Text Analysis Assistant"
- **Complementary**: clarify the specific problem your plugin solves

## Versioning

Follow Semantic Versioning (SemVer). Update version numbers when pushing to `main`.

## Release Workflow

Pushing to `main` triggers automatic release. Use Conventional Commits for commit messages. Any addition, modification, or removal of a plugin must simultaneously update the plugin code, READMEs, project docs, doc indexes, and the root README.

Source: [Plugin Development Guide](https://fu-jie.github.io/openwebui-extensions/development/plugin-guide/) and [OpenWebUI Tools Development](https://docs.openwebui.com/features/extensibility/plugin/tools/development/)
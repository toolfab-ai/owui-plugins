# Code Style Rules

## General Conventions

- **Language**: Python 3.11+ (`pyproject.toml` target-version = `py311`).
- **Line length**: 100 characters (enforced by ruff, `E501` ignored).
- **Formatter**: ruff (`ruff format`). Run `ruff check` and `ruff format` before committing.
- **Virtual environment**: Use `uv` (`uv run`, `uv sync`).

## Module Docstring

Every plugin file **must** begin with a module-level docstring containing metadata fields:

```python
"""
title: <Plugin Name>
author: <GitHub username or real name>
author_url: <optional GitHub profile URL>
version: <semver>
description: <one-line description>
requirements: <comma-separated pip packages, optional>
license: MIT
"""
```

Required fields: `title`, `author`, `version`, `description`.

## Imports

- Group imports in this order, separated by a blank line:
  1. Standard library
  2. Third-party
  3. Local
- Use **type annotations** on all imports that are used as types.
- Prefer `from __future__ import annotations` at the top of every file to enable postponed evaluation of annotations.
- Do not use wildcard imports (`from module import *`).

## Type Annotations

**Annotate everything.** All public and private functions, methods, class variables, and module-level variables must have explicit type annotations.

### Functions / Methods

```python
def _get_owui_data_dir() -> str:
    """Return the Open WebUI data directory for the current OS."""
    ...
```

- Every function definition must include a return type annotation (`-> <type>`), even if it is `-> None` or `-> str`.
- Every parameter must include its type, including `self` and `cls`.
- Use `Optional[X]` for nullable return types and parameters.
- Use `Callable[[...], <return>]` for callable parameters.
- For async methods, annotate the return type as `-> Awaitable[<type>]` or `-> None`.

### Classes

```python
class Tools:
    """Tools — plugin tools."""

    class Valves(BaseModel):
        """Admin-configurable settings."""

        max_results: int = Field(default=5, ge=1, le=100)
        mode: str = Field(default="balanced")
```

- All public classes must have a docstring.
- All Pydantic model fields must include a type annotation and a default value or `Field(...)`.
- Nested classes (e.g., `Valves`) must be defined inside their parent class.

### Variables

```python
_CONFIG_MAP: Dict[str, Tuple[str, str]] = {
    "mode": ("DEFAULT_MODE", "mode"),
}
```

- Module-level constants: `UPPER_CASE_WITH_UNDERSCORES`, always annotated.
- Local variables: annotate when the type is not obvious from the assignment.
- Use `Any` and `Dict[str, Any]` sparingly; prefer specific types.

## Class Structure

Plugin entry points must be one of: `Tools`, `Action`, `Filter`, or `Pipe`.

```python
class Tools:
    """Tools — description of what this plugin does."""

    class Valves(BaseModel):
        """Admin-configurable settings."""

        # fields with Field(...) and type annotations

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def public_method(self, query: str) -> str:
        """Short description of what this method does."""
        ...

    def _private_helper(self) -> None: ...
```

- The main class must contain a nested `Valves` class (Pydantic `BaseModel`) for admin-configurable settings.
- The `__init__` must instantiate `self.valves = self.Valves()`.
- Public methods must have docstrings.
- Private helpers must be prefixed with `_`.

## Section Comments

Use visual section separators for logical blocks:

```python
# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# ========================================================================
# TOOLS CLASS
# ========================================================================
```

- `---` style (`# ---`) for medium sub-sections within a class or function.
- `===` style (`# ===`) for top-level section headers (class definitions, major blocks).

## Logging

- Use the `logging` module, not `print()`.
- Configure at module level: `logger = logging.getLogger(__name__)`.
- Log errors with `logger.exception(...)` inside `except` blocks.

## Pydantic / Field Validation

- Use `Field(...)` with validation constraints (`ge`, `le`, `gt`, `lt`, `regex`, etc.) for numeric and string fields.
- Use `model_config = ConfigDict(...)` for Pydantic v2 model configuration when needed.

## Error Handling

- Catch specific exceptions, not bare `except:` or `except Exception`.
- Log exceptions with `logger.exception(...)` rather than printing to stderr.
- Return early on error rather than deep nesting.

## Naming Conventions

| Kind | Convention | Example |
|---|---|---|
| Module-level constant | `UPPER_CASE` | `MAX_RESULTS = 10` |
| Private function | `_lower_case` | `_resolve_path()` |
| Public function/method | `lower_case` | `get_model()` |
| Class | `PascalCase` | `class Tools:` |
| Type alias | `PascalCase` | `JsonDict = Dict[str, Any]` |

## Linting & Formatting

```bash
ruff check .    # type-check and lint
ruff format .   # format code
```

Configure in `pyproject.toml` under `[tool.ruff]`. Do not disable rules without justification in a comment.
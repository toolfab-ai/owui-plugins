# Valve Conventions

This document formalizes the pattern for implementing per-user configuration overrides in Open WebUI plugins using the `UserValves` system.

## The Problem

Open WebUI provides **Admin Valves** for global, system-wide configuration. However, professional users often need to provide their own API keys, search URLs, or adjust agent behaviors (like research depth) without affecting other users or requiring admin intervention.

## The Solution: User Valves

Plugins should implement a dual-valve system:
1.  **Admin Valves (`Valves`)**: Strong types, system defaults, secure credentials.
2.  **User Valves (`UserValves`)**: Flexible strings, per-user overrides, persists across chats.

### 1. The Pydantic Models

Define both models in `src/_valves.py`.

```python
from pydantic import BaseModel, Field

class Valves(BaseModel):
    """Admin-configurable settings — System Defaults."""
    SEARXNG_URL: str = Field(default="http://searxng:8080")
    MAX_STEPS: int = Field(default=3, ge=1, le=10)

class UserValves(BaseModel):
    """Per-user settings — configurable from the chat interface.

    All fields MUST be strings and default to "default" to allow inheritance.
    """
    searxng_url: str = Field(
        default="default",
        description="Private SearXNG instance URL. Use 'default' to inherit admin setting."
    )
    max_steps: str = Field(
        default="default",
        description="Max research steps. Use 'default' to inherit admin setting."
    )
```

### 2. Configuration Mapping

In `src/main.py`, define a mapping between internal logic keys and the specific attributes in both models.

```python
# key -> (Valves_attr, UserValves_attr)
_CONFIG_MAP: Dict[str, Tuple[str, str]] = {
    "searxng_url": ("SEARXNG_URL", "searxng_url"),
    "max_steps": ("MAX_STEPS", "max_steps"),
}
```

### 3. Resolution Logic (`_get_config`)

Implement a helper in your main class to resolve settings. The priority is: **User Override > Admin Default**.

```python
def _get_config(self, key: str, user_valves: Optional[UserValves] = None) -> Any:
    """Resolve a single config value."""
    mapping = _CONFIG_MAP.get(key, (key, key))
    valve_attr, user_attr = mapping

    # 1. Try User Override
    if user_valves is not None:
        val = getattr(user_valves, user_attr, None)
        if val is not None and str(val).strip().lower() not in ("", "default"):
            admin_val = getattr(self.valves, valve_attr)
            # Type casting based on Admin Valve type
            if isinstance(admin_val, bool):
                return str(val).strip().lower() in ("true", "1", "yes", "on")
            if isinstance(admin_val, int):
                try:
                    return int(str(val).strip())
                except (ValueError, TypeError):
                    return admin_val
            return val

    # 2. Fallback to Admin Valve
    return getattr(self.valves, valve_attr)
```

### 4. Implementation in Methods

Pass `__user_valves__` through your call chain and use `_get_config` for all lookups.

```python
async def pipe(self, body, __user_valves__=None, ...):
    user_valves = __user_valves__ or self.UserValves()
    max_steps = self._get_config("max_steps", user_valves)
    # ... pass to internal logic
```

### 5. Description Conventions

To ensure a high-quality User Interface, all `UserValves` fields must include clear descriptions that provide:
1.  **Examples**: Inline examples of what the value should look like (in purely string format).
2.  **Variants**: For enum-like or range-based fields, explicitly list the allowed options.

```python
class UserValves(BaseModel):
    searxng_url: str = Field(
        default="default",
        description="Private SearXNG URL (e.g., http://localhost:8080). Use 'default' to inherit."
    )
    max_steps: str = Field(
        default="default",
        description="Max steps (e.g., 5). Variants: 1-10. Use 'default' to inherit."
    )
    mode: str = Field(
        default="default",
        description="Search mode (e.g., deep). Variants: simple, deep. Use 'default' to inherit."
    )
```

## Standard Valve Names

To maintain consistency across all plugins, use these standard names for common infrastructure settings:

| Name | Type | Description |
|---|---|---|
| `proxy_url` | `str` | Outbound HTTP/HTTPS proxy (e.g., `http://proxy:8080`). |
| `base_url` | `str` | Public-facing base URL for the plugin (useful for links/exports). |
| `bypass_proxy` | `bool` | Whether to ignore system proxy settings for specific requests. |

## Benefits

- **Clean UI**: Users see clear "per-user" settings in the chat.
- **Inheritance**: "default" value allows admins to update global settings without forcing every user to change theirs.
- **Type Safety**: The resolution logic handles casting strings back to the integers/booleans expected by the backend logic.

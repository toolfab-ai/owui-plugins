# Core Concepts: Valves, Async, Context, and Logging

## ⚠️ Async vs Sync

Open WebUI plugins run within an `asyncio` event loop.

**Critical rules:**
- All I/O operations (database, file, network) must be non-blocking
- Calling synchronous methods directly (e.g., `time.sleep`, `requests.get`) will freeze the entire server
- Wrap synchronous calls using `await asyncio.to_thread(sync_func, ...)`

**Best practice:** Always use `async def` for plugin methods and `httpx.AsyncClient` for HTTP requests.

## Valves Configuration System

Use Pydantic `BaseModel` to define configurable parameters.

### Admin Valves vs User Valves

| Valves Type | Class | Who Configures | Where |
|-------------|-------|----------------|-------|
| **Valves** | `Valves` | Administrators only | Admin Panel → Functions → ⚙️ |
| **UserValves** | `UserValves` | Any user | Chat interface, per-function |

### Basic Valve Example

```python
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        SHOW_STATUS: bool = Field(
            default=True, description="Whether to show operation status updates."
        )
        API_KEY: str = Field(default="", description="Your API key here")
        priority: int = Field(
            default=0, description="Filter execution order. Lower values run first."
        )
```

### Valve Naming
- All Valves fields must use **UPPER_SNAKE_CASE**
- Use `description` parameter for UI help text

### Valve Input Types

Open WebUI supports special input types via `json_schema_extra`:

- **Password input**: `json_schema_extra={"input": {"type": "password"}}` — masks the value in the UI
- **Select dropdown**: `json_schema_extra={"input": {"type": "select", "options": ["opt1", "opt2"]}}` — static options
- **Dynamic select**: `json_schema_extra={"input": {"type": "select", "options": "method_name"}}` — runtime-generated options via `@classmethod`

### Encrypting Valve Values at Rest

Set `ENABLE_VALVE_ENCRYPTION=true` to encrypt Tool and Function Valve values with Fernet (AES-128). The `WEBUI_SECRET_KEY` must be a valid 44-character url-safe base64 Fernet key.

## Context Access

All plugins **must** use `_get_user_context` and `_get_chat_context` methods to safely extract information, rather than accessing `__user__` or `body` directly.

## Event Emission & Logging

### Event Emission
Implement helper methods `_emit_status` and `_emit_notification` for consistent UI feedback.

### Frontend Console Debugging
Use `_emit_debug_log` to print structured debug logs in the browser console for real-time data flow viewing.

### Server-side Logging
Use Python's standard `logging` module. Do not use `print()`.

```python
import logging

logger = logging.getLogger(__name__)


async def pipe(self, body: dict):
    logger.info(f"Processing pipe with model: {body.get('model')}")
```

## Database & File Storage

### Database
Re-use Open WebUI's internal database connection via `open_webui.internal.db`.

### File Storage
Implement multi-level fallback mechanisms:
DB → S3 → Local → URL → API

## Internationalization (i18n)

Define a `TRANSLATIONS` dictionary and use a robust language detection mechanism:
1. JS localStorage (client preference)
2. HTTP Accept-Language header
3. User profile language setting
4. Fallback to `en-US`

## Error Handling

Never fail silently. Always catch exceptions and inform the user via `__event_emitter__`:

```python
try:
    # Business logic
    pass
except Exception as e:
    await __event_emitter__(
        {
            "type": "notification",
            "data": {"type": "error", "content": f"Processing failed: {str(e)}"},
        }
    )
```

## Long-running Task Notifications

If a foreground task takes more than 3 seconds, implement progress notifications (e.g., sending a notification every 5 seconds).

## Long-running Background Tasks

For time-consuming operations without blocking the user response:

```python
import asyncio


async def outlet(self, body: dict, __metadata__: dict):
    asyncio.create_task(self.background_job(__metadata__["chat_id"]))
    return body


async def background_job(self, chat_id: str):
    # Execute time-consuming operation...
    pass
```

Source: [Plugin Development Guide](https://fu-jie.github.io/openwebui-extensions/development/plugin-guide/) and [OpenWebUI Documentation](https://docs.openwebui.com/)
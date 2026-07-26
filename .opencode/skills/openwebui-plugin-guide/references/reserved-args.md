# Reserved Arguments Reference

All plugin methods support injecting special parameters via their function signature. Open WebUI inspects the signature at runtime to determine what to pass.

## Core Parameters

### `body` (dict)
**Core Data.** Contains request info like `messages`, `model`, `stream`, `tools`, `files`, and `metadata`.

```python
{
    "stream": true,
    "model": "my-cool-model",
    "messages": [...],
    "features": {"image_generation": false, "code_interpreter": false},
    "metadata": {...},
    "files": [...],
    "tools": [...],
}
```

### `__user__` (dict)
**Current User.** Contains `id`, `email`, `name`, `role`, and `valves` (UserValves object).

```python
{
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "email": "user@example.com",
    "name": "Patrick",
    "role": "user",  # "user" or "admin"
    "valves": {...},  # UserValves instance (only if UserValves class is defined)
}
```

### `__metadata__` (dict)
**Metadata.** Contains `chat_id`, `message_id`, `session_id`, `user_prompt`, `system_prompt`, `variables`, `features`, and more.

```python
{
    "user_id": "...",
    "chat_id": "...",
    "message_id": "...",
    "session_id": "...",
    "user_prompt": "What is in this picture?",
    "system_prompt": "You are a helpful assistant.",
    "sources": [],
    "tool_ids": null,
    "files": [],
    "features": {"image_generation": false, "code_interpreter": false},
    "variables": {
        "{{USER_NAME}}": "cheesy_username",
        "{{CURRENT_DATETIME}}": "2025-02-02 XX:XX:XX",
        "{{CURRENT_DATE}}": "2025-02-02",
        "{{CURRENT_TIME}}": "XX:XX:XX",
        "{{CURRENT_WEEKDAY}}": "Monday",
        "{{CURRENT_TIMEZONE}}": "Europe/Berlin",
        "{{USER_LANGUAGE}}": "en-US",
    },
    "model": {...},
    "function_calling": "native",
    "interface": "open-webui",
}
```

The `interface` field indicates the request source:
- `"open-webui"`: Request from the Web UI
- Other/missing: Likely a direct API call

### `__model__` (dict)
**Model Information.** Contains model dict including `info.base_model_id` for workspace models.

```python
{
    "id": "my-cool-model",
    "name": "My Cool Model",
    "owned_by": "openai",
    "info": {
        "base_model_id": "gpt-4o",
        "params": {...},
        "capabilities": {"vision": true, "usage": true},
    },
}
```

### `__request__` (Request)
**FastAPI Request Object.** Access `app.state` for cross-plugin communication and internal services.

```python
from fastapi import Request


async def pipe(self, body: dict, __request__: Request):
    cache = __request__.app.state.__dict__.setdefault("my_cache", {})
```

### `__event_emitter__` (func)
**One-way Notification.** Used to send toast notifications, status updates, citations, files, and other UI updates.

```python
await __event_emitter__({"type": "status", "data": {"description": "Processing...", "done": False}})
```

### `__event_call__` (func)
**Two-way Interaction.** Used to execute JS, show confirmations, or input boxes. Returns the user's response.

```python
result = await __event_call__(
    {"type": "confirmation", "data": {"title": "Confirm", "message": "Are you sure?"}}
)
```

## Additional Optional Parameters

### `__messages__` (list)
List of previous messages (same as `body["messages"]`).

### `__chat_id__` (str)
The chat session ID. Available for all function invocations that originate from a chat context.

### `__session_id__` (str)
The session ID.

### `__message_id__` (str)
The message ID associated with the active turn.

### `__files__` (list)
Files sent via the chat. Images are not included here; they are sent directly in `body["messages"]`.

```python
[
    {
        "type": "file",
        "file": {"id": "...", "filename": "doc.pdf", "data": {"content": "..."}},
        "url": "/api/v1/files/...",
        "name": "doc.pdf",
    }
]
```

### `__task__` (str)
A shorthand for `__metadata__["task"]`. Possible values:
- `title_generation`
- `tags_generation`
- `emoji_generation`
- `query_generation`
- `image_prompt_generation`
- `autocomplete_generation`
- `function_calling`
- `moa_response_generation`

### `__task_body__` (dict)
The `body` needed for a given `__task__`. Shorthand for `__metadata__["task_body"]`.

### `__tools__` (list)
List of `ToolUserModel` instances. See Open WebUI source for attributes.

### `__oauth_token__` (dict)
The user's OAuth token payload with `access_token`, `id_token`, etc. The secure way to access user tokens for making authenticated API calls from Tools.

```python
async def get_user_profile(self, __oauth_token__: dict = None):
    access_token = __oauth_token__["access_token"]
    # Use the access token to call external APIs
```

### `__id__` (str)
Action ID — useful for multi-action functions.

### `__metadata__` fields for Tool Mode Detection

```python
def is_legacy_mode(__metadata__: dict) -> bool:
    # Native is the default; only an explicit "legacy" opts out
    return (__metadata__ or {}).get("params", {}).get("function_calling") == "legacy"
```

Source: [OpenWebUI Reserved Arguments Docs](https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args/) and [Plugin Functions Overview](https://docs.openwebui.com/features/extensibility/plugin/functions/)
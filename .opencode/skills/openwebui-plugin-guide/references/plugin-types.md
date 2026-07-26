# Plugin Types: Pipe, Filter, Action, Event

## Pipe Function

Pipes act as custom models or agents. They handle the entire request lifecycle without needing an LLM backend.

### Basic Structure

```python
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        MODEL_ID: str = Field(default="")

    def __init__(self):
        self.valves = self.Valves()

    async def pipe(self, body: dict):
        # Logic goes here
        return "Hello, World!"
```

### Multiple Models (Manifold)

```python
class Pipe:
    def pipes(self):
        return [
            {"id": "model_id_1", "name": "model_1"},
            {"id": "model_id_2", "name": "model_2"},
        ]

    async def pipe(self, body: dict):
        model = body.get("model", "")
        return f"{model}: Hello, World!"
```

### Key Points
- `pipes()` returns a list of model definitions for multi-model Pipes
- `pipe()` is the core handler; receives `body` with request data
- Use `httpx.AsyncClient` instead of `requests` for async compatibility
- Pipes can access internal Open WebUI functions like `generate_chat_completion`

### Example: OpenAI Proxy Pipe

```python
import httpx
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        OPENAI_API_KEY: str = Field(default="")
        OPENAI_API_BASE_URL: str = Field(default="https://api.openai.com/v1")
        NAME_PREFIX: str = Field(default="OPENAI/")

    def __init__(self):
        self.valves = self.Valves()

    async def pipes(self):
        if not self.valves.OPENAI_API_KEY:
            return [{"id": "error", "name": "API Key not provided."}]
        headers = {"Authorization": f"Bearer {self.valves.OPENAI_API_KEY}"}
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.valves.OPENAI_API_BASE_URL}/models", headers=headers)
            r.raise_for_status()
            models = r.json()
        return [
            {"id": m["id"], "name": f"{self.valves.NAME_PREFIX}{m.get('name', m['id'])}"}
            for m in models["data"]
            if "gpt" in m["id"]
        ]

    async def pipe(self, body: dict):
        model_id = body["model"][body["model"].find(".") + 1 :]
        payload = {**body, "model": model_id}
        headers = {"Authorization": f"Bearer {self.valves.OPENAI_API_KEY}"}
        async with httpx.AsyncClient(timeout=None) as client:
            r = await client.post(
                f"{self.valves.OPENAI_API_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                stream=body.get("stream", False),
            )
            r.raise_for_status()
            if body.get("stream"):
                return r.aiter_lines()
            return r.json()
```

## Filter Function

Filters intercept data flowing between the user and the model at three stages.

### Hooks

| Hook | When | Purpose |
|------|------|---------|
| `inlet()` | Before request | Inject context, modify model params, sanitize input |
| `stream()` | During streaming | Real-time sensitive word filtering, token tracking |
| `outlet()` | After response | Format output, log, append disclaimers |

### Basic Structure

```python
from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict) -> dict:
        return body

    async def stream(self, event: dict) -> dict:
        return event

    async def outlet(self, body: dict) -> dict:
        return body
```

### Toggleable Filters

Set `self.toggle = True` in `__init__` to make the filter user-controllable per chat.

### file_handler Mode

Set module-level `file_handler = True` to skip the built-in RAG pipeline and handle retrieval yourself in `inlet()`.

### Filter Priority

Filters execute in ascending priority order (default 0 runs first). Set via `Valves.priority`.

## Action Function

Actions add clickable buttons to messages that trigger custom Python code.

### Basic Structure

```python
class Action:
    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        priority: int = 0  # Lower = appears first

    async def action(self, body: dict, __user__=None, __event_emitter__=None, __event_call__=None):
        # Action implementation
        return {"content": "Modified message content"}
```

### Key Features
- Support for `__event_emitter__` (one-way UI updates) and `__event_call__` (two-way interaction)
- Multi-action support via `actions` array with `__id__` parameter
- Can return `HTMLResponse` for Rich UI embeds
- Button display order controlled by `priority` valve

### Frontmatter Metadata

```python
"""
title: Enhanced Message Processor
author: @admin
version: 1.2.0
required_open_webui_version: 0.5.0
icon_url: https://example.com/icons/processor.svg
requirements: requests,beautifulsoup4
"""
```

## Event Function

Event functions run custom Python in response to system events (user signup, chat deleted, server startup, etc.).

### Basic Structure

```python
class Event:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()

    async def event(
        self,
        event: dict,
        __event_name__: str = None,
        __event_id__: str = None,
        __id__: str = None,
        __app__=None,
        __request__=None,
    ):
        if __event_name__ == "auth.signup":
            await self.on_signup(event)
```

### Key Features
- Receives `__app__` (FastAPI app) — can register custom API routes
- Receives `__request__` when triggered by HTTP requests
- Supports 170+ event types across all subsystems
- Can self-configure on `system.startup.completed`
- Supports lifecycle hooks for startup/shutdown

Concurrency note: `system.startup.completed` fires on every replica. Use Redis for exactly-once semantics in multi-instance deployments.

Source: [OpenWebUI Plugin Docs](https://docs.openwebui.com/features/extensibility/plugin/) and [Function Type Guides](https://docs.openwebui.com/features/extensibility/plugin/functions/)
# Advanced Development Patterns

## Pipe & Filter Collaboration

Use `__request__.app.state` to share data between plugins:

**Pipe writes:**
```python
async def pipe(self, body: dict, __request__=None):
    __request__.app.state.search_results = [...]
    return body
```

**Filter (Outlet) reads:**
```python
async def outlet(self, body: dict, __request__=None):
    results = getattr(__request__.app.state, "search_results", [])
    # Format as citation links
    return body
```

## Async Background Tasks

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

## Calling Built-in LLM

```python
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users

user_obj = Users.get_user_by_id(user_id)
llm_payload = {
    "model": "model-id",
    "messages": [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User input"},
    ],
    "temperature": 0.7,
    "stream": False,
}
llm_response = await generate_chat_completion(__request__, llm_payload, user_obj)
```

## JS Render to Markdown (Data URL Embedding)

For complex frontend rendering (AntV charts, Mermaid diagrams) with persistent Markdown output:

1. **Python Action**: Analyze content, call LLM to generate structured data, send JS to frontend via `__event_call__`
2. **Browser JS**: Dynamically load visualization library, render SVG/Canvas offscreen, export to Base64 Data URL via `toDataURL()`, update message content via REST API
3. **Markdown Rendering**: Display `![description](data:image/svg+xml;base64,...)`

## Agent File Delivery Standards (3-Step Delivery Protocol)

1. **Write Local**: Create files in the current execution directory (`.`)
2. **Publish**: Call `publish_file_from_workspace(filename='name.ext')`
3. **Display Link**: Present the returned `download_url` as a Markdown link

## Filter Singleton Discipline

Do not store request-scoped mutable state on `self`. Compute from request context each run. This prevents bugs when filters are reused across concurrent requests.

## Async Compression Pattern

Use `inlet` for summary injection and `outlet` for background summary generation:

```python
async def inlet(self, body: dict, __metadata__: dict):
    # Inject compressed context into system prompt
    summary = await self.compress(body["messages"])
    body["messages"][0]["content"] += f"\n\n{summary}"
    return body


async def outlet(self, body: dict, __metadata__: dict):
    asyncio.create_task(self.generate_summary(__metadata__["chat_id"], body))
    return body
```

With model-threshold override and system-message protection.

## Workspace/Tool Hardening

- Always define explicit `params_type` schemas for tool parameters
- Use strict path-boundary validation for file operations
- Return `/api/v1/files/{id}/content` with `skip_rag=true` metadata for file delivery

## MoE Refinement Pipeline

Detect aggregation prompts, parse segmented responses, and rewrite to synthesis-oriented master prompts with optional reroute model.

## HTML Merge Strategy

Use stable wrapper markers (`OPENWEBUI_PLUGIN_OUTPUT`) and support both overwrite and merge modes for HTML output in filters and actions.

## Theme Consistency

Detect parent/system theme and apply theme-aware rendering/export styles for iframe-based outputs.

## Render-Export-Persist Loop

1. Offscreen render (SVG/PNG)
2. Upload to `/api/v1/files/`
3. Emit event update + persistence update to avoid refresh loss

## DOCX Production Path

- Use `TITLE_SOURCE` fallback naming
- Strip reasoning blocks
- Convert native Word math via `latex2mathml + mathml2omml`
- Anchor citations/references to sections

## File Retrieval Fallback Chain

DB inline → S3 direct → local path variants → public URL → internal API → raw fields, with max-byte guards on each stage.

## Calling External APIs with OAuth

Use `__oauth_token__` for secure, user-delegated API access:

```python
async def get_user_profile(self, __oauth_token__: dict = None):
    if not __oauth_token__ or "access_token" not in __oauth_token__:
        return "Error: User not authenticated via OAuth"
    access_token = __oauth_token__["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.my-service.com/v1/profile", headers=headers)
        return f"API Response: {response.json()}"
```

## Copilot SDK Tool Definition Standards

When developing tools for GitHub Copilot SDK, define a Pydantic `BaseModel` for parameters and explicitly reference it using `params_type` in `define_tool`. All tool methods should be `async` for future compatibility.

Source: [Plugin Development Guide](https://fu-jie.github.io/openwebui-extensions/development/plugin-guide/) and [OpenWebUI Docs](https://docs.openwebui.com/)
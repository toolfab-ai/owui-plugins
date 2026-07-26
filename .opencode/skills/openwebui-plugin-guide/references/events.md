# Event System: __event_emitter__ and __event_call__

## Overview

Open WebUI provides a real-time event system for plugin-to-UI communication. Use `__event_emitter__` for one-way updates (fire and forget) and `__event_call__` for two-way interactions (await user response).

## Event Payload Structure

```python
{
    "type": "event_type",  # See table below
    "data": {...},  # Event-specific payload
}
```

## Event Type Catalog

### Status Events ✅ Fully Compatible (Native + Legacy)

```python
await __event_emitter__(
    {"type": "status", "data": {"description": "Working...", "done": False, "hidden": False}}
)
```

| Field | Type | Description |
|-------|------|-------------|
| `description` | str | Status message text |
| `done` | bool | True = completed, removes shimmer animation |
| `hidden` | bool | True = save to history but don't show |

Always emit a final `done: True` to stop the shimmer animation.

### Message/Delta Events ⚠️ Legacy Mode Only

**Incompatible with Native function calling mode** — content gets overwritten by completion snapshots.

```python
# Append content
await __event_emitter__({"type": "chat:message:delta", "data": {"content": "Partial text"}})

# Replace entire message
await __event_emitter__({"type": "chat:message", "data": {"content": "Full text"}})
```

### Notification Events ✅ Compatible

```python
await __event_emitter__(
    {
        "type": "notification",
        "data": {"type": "info" or "success" or "error" or "warning", "content": "Message"},
    }
)
```

### File Events ✅ Compatible

```python
await __event_emitter__(
    {
        "type": "files",  # or "chat:message:files"
        "data": {"files": [{"name": "report.pdf", "url": "/files/report.pdf"}]},
    }
)
```

### Follow-up Events ✅ Compatible

```python
await __event_emitter__(
    {
        "type": "chat:message:follow_ups",
        "data": {"follow_ups": ["What about X?", "Tell me more about Y"]},
    }
)
```

### Title Update Events ✅ Compatible

```python
await __event_emitter__({"type": "chat:title", "data": {"title": "New Chat Title"}})
```

### Tag Events ✅ Compatible

```python
await __event_emitter__(
    {"type": "chat:tags", "data": {"tags": ["research", "analysis", "completed"]}}
)
```

### Error Events ✅ Compatible

```python
await __event_emitter__(
    {"type": "chat:message:error", "data": {"error": {"content": "Error message"}}}
)
```

### Confirmation Events ✅ Compatible (requires __event_call__)

```python
result = await __event_call__(
    {"type": "confirmation", "data": {"title": "Confirm", "message": "Are you sure?"}}
)
```

### Input Request Events ✅ Compatible (requires __event_call__)

```python
result = await __event_call__(
    {
        "type": "input",
        "data": {"title": "Enter name", "message": "Please provide:", "placeholder": "Your name"},
    }
)

# Password input
result = await __event_call__(
    {"type": "input", "data": {"title": "API Key", "message": "Enter key:", "type": "password"}}
)
```

### Code Execution Events ✅ Compatible (works with both __event_call__ and __event_emitter__)

```python
# Two-way: get return value
result = await __event_call__({"type": "execute", "data": {"code": "return document.title;"}})

# Fire-and-forget: trigger download, no return needed
await __event_emitter__({"type": "execute", "data": {"code": "..."}})
```

The `execute` event runs JavaScript in the main page context (not sandboxed). Use `__event_call__` when you need the result; use `__event_emitter__` for fire-and-forget. On iOS PWA, use `__event_emitter__` for blob downloads to avoid `TypeError: Load failed`.

### Embeds Events ✅ Compatible

```python
await __event_emitter__(
    {
        "type": "embeds",  # short name for DB persistence
        "data": {"embeds": ["<html>..."], "replace": False},
    }
)
```

- A `http://`, `https://`, or `//`-prefixed URL is loaded as an iframe `src`
- Anything else is treated as raw HTML and rendered inline
- Use `replace: True` to overwrite existing embeds instead of appending

### Citation/Source Events ✅ Compatible

```python
await __event_emitter__(
    {
        "type": "source",  # or "citation"
        "data": {
            "source": {"name": "Title", "url": "https://..."},
            "document": ["citation text"],
            "metadata": [{"source": "url", "date_accessed": "2024-01-01"}],
        },
    }
)
```

### Chat Completion Events ⚠️ Legacy Mode

Streaming LLM deltas via Socket.IO only. Not persisted to DB.

## Persistence

**Persisted to DB (survive tab close):** `status`, `message`, `replace`, `embeds`, `files`, `source`/`citation`

**Not persisted (lost on tab close):** `chat:completion`, `chat:message:delta`, `chat:message`, `notification`, `chat:title`, `chat:tags`, `chat:message:favorite`, `chat:message:error`, `chat:message:follow_ups`

**Requires live connection (will error on tab close):** `confirmation`, `input`, `execute` via `__event_call__`

## Best Practices

- Use `status` for progress — it works in both Native and Legacy modes
- Use `notification` for one-time alerts
- Use `citation` for source references
- Use `embeds` for persistent visual content (dashboards, charts)
- Use `execute` for transient interactions (downloads, DOM manipulation)
- Don't rely solely on event-emitted content for Pipes — return/yield content directly
- Always emit `done: True` as the final status event

Source: [OpenWebUI Events Docs](https://docs.openwebui.com/features/extensibility/plugin/development/events/)
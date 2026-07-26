# OpenWebUI Extensibility Overview

Open WebUI provides a powerful plugin system that lets you extend the platform with Python code, HTTP endpoints, or community plugins. There are two main layers:

- **In-process Python** (Tools & Functions) runs inside Open WebUI itself with zero infrastructure and instant iteration.
- **External HTTP** (OpenAPI & MCP servers) connects to services running anywhere.

## Plugin Types at a Glance

| Type | Class Name | What It Does | How Users See It |
|------|-----------|--------------|------------------|
| **Tool** | `Tools` | Extends LLM abilities (web search, API calls) | Appears in tool picker during chat |
| **Pipe** | `Pipe` | Adds a custom model or agent | Appears as selectable model in sidebar |
| **Filter** | `Filter` | Modifies data before/after model calls | Runs transparently on existing models |
| **Action** | `Action` | Adds interactive buttons to messages | Appears as clickable button on chat messages |
| **Event** | `Event` | Runs logic in response to system events | Runs in background; no direct UI |

## Key Extensibility Concepts

### Tools vs Functions
- **Tools** give LLMs external abilities (weather, stock prices, API calls). The model decides when to call them.
- **Functions** extend Open WebUI itself (new model providers, filters, UI actions). They are platform extensions.

### When to Use What

| Use Case | Use |
|----------|-----|
| Give LLM access to live data | **Tool** |
| Add a model provider with non-OpenAI API | **Pipe Function** |
| Build a non-LLM interface (search, DB) | **Pipe Function** |
| Translate, moderate, redact content | **Filter Function** |
| Log requests to observability | **Filter Function** |
| Add a button to export/summarize | **Action Function** |
| Trigger external workflow from chat | **Action Function** |
| Run logic on system events | **Event Function** |

## Security

All plugin types execute arbitrary Python on your server. Only install from trusted sources, review code before importing, and restrict Workspace access to administrators. See the [Security Policy](https://docs.openwebui.com/security) for details.

## Architecture

```
User Chat
    ↓
Filter inlet (modify request)
    ↓
Model call (with Tools/Functions)
    ↓
Filter stream (modify streaming chunks)
    ↓
Filter outlet (modify response)
    ↓
Action buttons (user-triggered)
    ↓
Event function (system event reactions)
```

Source: [OpenWebUI Extensibility Docs](https://docs.openwebui.com/features/extensibility/) and [Plugin Guide](https://fu-jie.github.io/openwebui-extensions/development/plugin-guide/)
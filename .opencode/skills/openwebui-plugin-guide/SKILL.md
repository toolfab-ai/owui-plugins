---
name: openwebui-plugin-guide
description: OpenWebUI plugin development guide covering Pipes, Filters, Actions, Events, Tools, Valves, reserved arguments, Rich UI embedding, and the plugin loader internals
---

# OpenWebUI Plugin Development Guide

Comprehensive knowledge skill for developing OpenWebUI plugins (Functions and Tools). Covers all plugin types, the SDK API, configuration system, event handling, rich UI embedding, and internal loader mechanics.

## Table of Contents
- [Extensibility Overview](./references/overview.md)
- [Plugin Types: Pipe, Filter, Action, Event](./references/plugin-types.md)
- [Development Basics: Structure, Naming, Docstrings](./references/development-basics.md)
- [Core Concepts: Valves, Async, Context, Logging](./references/core-concepts.md)
- [Reserved Arguments Reference](./references/reserved-args.md)
- [Rich UI Embedding](./references/rich-ui.md)
- [Event System](./references/events.md)
- [Valves and UserValves](./references/valves.md)
- [Under the Hood: Plugin Loader](./references/under-the-hood.md)
- [Advanced Development Patterns](./references/advanced-patterns.md)

## Core Principles
- All plugin code runs in Open WebUI's async event loop — use `async` for all I/O
- Valves (Pydantic `BaseModel`) provide admin-configurable settings; UserValves give per-user config
- The `__event_emitter__` and `__event_call__` dunders enable real-time UI feedback and user interaction
- Filters use `inlet`/`stream`/`outlet` hooks; Pipes use `pipe`/`pipes`; Actions use `action`; Events use `event`
- The plugin loader executes source via `exec()` and caches modules in `sys.modules` — module-level side effects persist across reloads
- Plugin security is critical: all plugins execute arbitrary Python on the server
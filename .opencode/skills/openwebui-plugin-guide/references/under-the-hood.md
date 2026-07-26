# Under the Hood: Plugin Loader Internals

## How a Plugin is Loaded

The loader in `backend/open_webui/utils/plugin.py` handles every plugin type:

1. Plugin Python source is read from the database
2. A fresh `types.ModuleType` is created and registered in `sys.modules` as `function_{id}` or `tool_{id}`
3. The source is fed to `exec(content, module.__dict__)` — anything at module top level runs at this point
4. The loader looks for **one** entry-point class: `Tools`, `Pipe`, `Filter`, or `Action`
5. The module stays in `sys.modules` for the life of the process — side effects persist

### When Modules are Re-executed

| Hook | DB check per call? | Module re-exec'd when |
|------|-------------------|----------------------|
| `inlet` / `outlet` (Filter) | yes | Source change between calls |
| `stream` (Filter) | no | Another hook triggers reload |
| Tools, Pipes, Actions | yes on dispatch | Source change between calls |

**Practical consequence:** Editing a Filter via the editor takes effect on the next chat for `inlet`/`outlet`. `stream` picks it up when another hook triggers a reload.

## Full Access to Open WebUI Internals

From any hook (and from module top level), plugins have access to:

- The full `open_webui.*` package (e.g., `from open_webui.models.chats import Chats`)
- The live FastAPI `Request` via `__request__`, giving `__request__.app` and `__request__.app.state`
- All reserved dunder args (`__user__`, `__metadata__`, `__model__`, etc.)
- Events via `__event_emitter__` and `__event_call__`
- Any pip package via `requirements:` frontmatter
- The Python stdlib and all installed packages

**There is no sandbox, no allowlist, no capability system.** The execution model is "this is Python, you are inside the server process."

## Key Patterns

### 1. Mutate the per-request model dict from `inlet`

The `__model__` you receive is the same dict object the rest of the request reads. Changing its keys from `inlet` changes downstream behavior:

```python
class Filter:
    async def inlet(self, body: dict, __model__: dict = None) -> dict:
        if __model__ and __model__.get("provider") not in ("ollama", "llama.cpp"):
            __model__["provider"] = "llama.cpp"
        return body
```

### 2. Monkey-patch a backend function

```python
import open_webui.utils.middleware as _mw

_original = _mw.process_chat_payload


async def _patched(request, form_data, user, metadata, model):
    return await _original(request, form_data, user, metadata, model)


_mw.process_chat_payload = _patched
```

⚠️ Runs once per source version. Deleting/disabling the plugin does **not** revert the patch. Only a process restart does.

### 3. Serve a page or asset from a route

```python
from fastapi.responses import HTMLResponse, Response


def _ensure_routes(app):
    if any(getattr(r, "path", None) == "/my/tool" for r in app.routes):
        return

    async def page():
        return HTMLResponse("<html>...</html>")

    app.add_api_route("/my/tool", page, methods=["GET"])
```

Call from a hook or `system.startup.completed` event that has `__app__`. Routes run on the real application — they are **not authenticated** unless you add auth yourself.

### 4. Spawn a background task

```python
import asyncio


async def _loop(app):
    while True:
        await asyncio.sleep(60)
        # periodic work...


def _start_once(app):
    if getattr(app.state, "_my_plugin_started", False):
        return
    app.state._my_plugin_started = True
    asyncio.create_task(_loop(app))
```

### 5. Stash state in `app.state`

Shared across requests and **across plugins** in the same process — use unique keys:

```python
async def inlet(self, body, __request__):
    cache = __request__.app.state.__dict__.setdefault("my_cache", {})
```

### 6. Monkey-patching caution

Cross-plugin interference is a real risk: if two plugins patch the same function, the result depends on load order, which is not deterministic. Prefer additive patterns over destructive ones.

## Concurrency and Multiple Instances

**Open WebUI does not serialize your plugin code.** Hooks and handlers run inside an async event loop and can overlap. In a multi-replica deployment, the same logical work can run on several workers at once.

### Within one process
Async hooks interleave. Use `asyncio.Lock` for coroutines or `threading.Lock` for offloaded work to serialize read-modify-write operations.

### Across replicas
Each replica is a separate process. Module globals and in-process locks coordinate nothing between them. Use **Redis** for distributed coordination:

```python
from open_webui.utils.redis import get_redis_connection
from open_webui.env import REDIS_URL, REDIS_KEY_PREFIX

_redis = get_redis_connection(REDIS_URL, decode_responses=True) if REDIS_URL else None


def run_once(key: str, ttl: int = 300) -> bool:
    if _redis is None:
        return True
    return bool(_redis.set(f"{REDIS_KEY_PREFIX}:plugin:{key}", "1", nx=True, ex=ttl))
```

## Footguns

- **No sandboxing** — granting Tool/Function creation is equivalent to shell access
- **`stream` hooks use a stale cache** — edits only take effect after another hook triggers a reload or a process restart
- **Cross-plugin interference is not detected** — two plugins patching the same function will collide
- **Disabling does not unload** — the module stays in `sys.modules`; restart to fully revert
- **No concurrency control, no exactly-once** — you must coordinate side effects yourself
- **`requirements:` runs `pip install` on every replica at load** — set `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False` in multi-replica deployments and pre-install dependencies
- **Internal APIs are not stable** — `open_webui.utils.*` and internals can rename/move between releases
- **Pipelines server is out of scope** — it's a separate out-of-process server, not covered here

Source: [OpenWebUI Under the Hood Docs](https://docs.openwebui.com/features/extensibility/plugin/development/under-the-hood/)
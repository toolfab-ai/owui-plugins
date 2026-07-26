# Rich UI Embedding

Tools and Actions both support rich UI element embedding — returning HTML content and interactive iframes that display directly within chat conversations.

## Tool Usage

Return an `HTMLResponse` with `Content-Disposition: inline` header:

```python
from fastapi.responses import HTMLResponse


def render_checklist(self, items: list[str]) -> HTMLResponse:
    items_html = "".join(
        f'<li><label><input type="checkbox"> {item}</label></li>' for item in items
    )
    html_content = f"""
    <!DOCTYPE html><html><body><ul>{items_html}</ul></body></html>
    """
    return HTMLResponse(content=html_content, headers={"Content-Disposition": "inline"})
```

### Custom Result Context

Return a tuple `(HTMLResponse, context)` to give the LLM actionable context about the embed:

```python
def render_feedback_form(self, prompt: str) -> tuple:
    html_content = "<html>...</html>"
    result_context = {
        "status": "success",
        "form_type": "feedback",
        "fields": ["rating", "comment"],
    }
    return HTMLResponse(
        content=html_content, headers={"Content-Disposition": "inline"}
    ), result_context
```

The context can be a `str`, `dict`, or `list`. If missing or wrong type, a generic fallback message is used.

## Action Usage

Actions work the same way via the event emitter or direct return:

**Option A, HTMLResponse:**
```python
async def action(self, body, __event_emitter__=None):
    from fastapi.responses import HTMLResponse

    return HTMLResponse(content="<h1>Dashboard</h1>", headers={"Content-Disposition": "inline"})
```

**Option B, Tuple with headers:**
```python
async def action(self, body, __event_emitter__=None):
    html = "<h1>Interactive Chart</h1><script>...</script>"
    return (html, {"Content-Disposition": "inline", "Content-Type": "text/html"})
```

## Pipe Function Usage

When a Pipe handles tool calls itself (bypassing the middleware), it must emit embeds manually:

```python
from fastapi.responses import HTMLResponse


async def execute_tool(self, tool_call, tools, __event_emitter__):
    result = await tools[tool_call.name]["callable"](**tool_call.args)
    if isinstance(result, HTMLResponse):
        content_disposition = result.headers.get("Content-Disposition", "")
        if "inline" in content_disposition:
            html_content = result.body.decode("utf-8", "replace")
            await __event_emitter__(
                {
                    "type": "embeds",
                    "data": {"embeds": [html_content]},
                }
            )
            return json.dumps({"status": "success", "message": f"{tool_call.name}: UI rendered."})
    return json.dumps(result)
```

## iframe Height and Auto-Sizing

Rich UI embeds render inside a sandboxed iframe. The iframe must report its own height:

```html
<script>
  function reportHeight() {
    const h = document.documentElement.scrollHeight;
    parent.postMessage({ type: 'iframe:height', height: h }, '*');
  }
  window.addEventListener('load', reportHeight);
  new ResizeObserver(reportHeight).observe(document.body);
</script>
```

### Same-Origin Auto-Resize
When `allowSameOrigin` is on (user setting), the parent page auto-resizes the iframe without JS. Off by default for security.

## Sandbox and Security

Embedded iframes are sandboxed with `allow-scripts`, `allow-popups`, `allow-downloads` by default. Two additional user-toggled flags:

| Setting | Default | Description |
|---------|---------|-------------|
| Allow Iframe Same-Origin Access | Off | Allows iframe to interact with parent page |
| Allow Iframe Form Submissions | Off | Allows form submissions within embedded content |

## Advanced Communication

### Payload Requests
Iframes can request data from the parent page via `postMessage`:

```javascript
parent.postMessage({ type: 'payload', requestId: 'my-request' }, '*');
```

The parent responds with `{ type: 'payload', requestId, payload }`. Currently, only citation-opened embeds in the Embeds panel provide a payload.

### Tool Args Injection (Tools Only)
When a Tool returns an HTMLResponse inline, `window.args` is exposed as a JSON string:

```javascript
const args = JSON.parse(window.args || '{}');
```
Requires `allowSameOrigin`. Does not work for `__event_emitter__` embeds or Action embeds.

### Auto-Injected Libraries
With `allowSameOrigin`, Alpine.js and Chart.js are auto-detected and injected if used in HTML.

### Prompt Submission
Embeds can submit prompts to the chat:

```javascript
// Fill chat input (no submit)
parent.postMessage({ type: 'input:prompt', text: 'Analyze this' }, '*');

// Fill and submit
parent.postMessage({ type: 'input:prompt:submit', text: 'Show me a summary' }, '*');

// Submit existing input
parent.postMessage({ type: 'action:submit', text: '' }, '*');
```

Cross-origin: `input:prompt:submit` shows a confirmation dialog.

Source: [Rich UI Embedding Docs](https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/)
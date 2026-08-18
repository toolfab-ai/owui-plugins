# LLM Calls & Error Handling Guide

Plugins that call an LLM (background fact extraction, summarization, title-style
generation, synthesis, etc.) **must** follow the consolidated error-handling pattern
proven in `iterative-research`. The goal is **graceful degradation**: an LLM failure
must never block the chat pipeline or crash the plugin.

## Resilient Internal Imports

`generate_chat_completion` is the internal engine OWUI itself uses for lightweight
tasks such as title generation. Import it defensively (new namespace first, legacy
fallback, then `None`):

```python
try:
    from open_webui.utils.chat import generate_chat_completion
except ImportError:
    try:
        from open_webui.apps.webui.utils.chat import generate_chat_completion
    except ImportError:
        generate_chat_completion = None  # noqa: N816
```

## Calling the Built-in LLM

Check availability before calling, keep `stream=False`, and never let an exception
escape to the caller:

```python
async def _call_llm(
    self, __request__, user_obj, system_prompt: str, user_prompt: str, model_id: str
) -> str:
    if generate_chat_completion is None:
        logger.warning("generate_chat_completion unavailable; skipping LLM call")
        return ""
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    try:
        response = await generate_chat_completion(__request__, payload, user_obj)
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return response.get("content", str(response))
        return str(response)
    except Exception:
        logger.exception("LLM generation failed")
        return ""
```

## Robust JSON Parsing

LLM JSON output is never guaranteed. Strip code fences, fall back to the largest
brace block, and degrade to a safe default before giving up:

```python
def _parse_json_completions(self, text: str) -> Any:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            text = match.group(1)
    try:
        return json.loads(text.strip())
    except Exception:
        logger.warning("Failed to parse JSON from LLM output")
        return None
```

## Fallback Chains

Prefer a primary source with explicit fallbacks and a safe default when all fail
(see `_search_query` in `iterative-research`: Tavily → SearXNG → `[]`). For model
selection, prefer an explicit cheap-model valve (e.g. `EXTRACTION_MODEL`) and fall
back to the request's own model id when the valve is empty.

## Rules of Thumb

- Never let an LLM error escape into the filter/pipe/action caller — log and return a safe default.
- Log failures with `logger.exception(...)` inside `except` blocks; use `logger.warning(...)` for recoverable conditions.
- Run long LLM work in a background `asyncio.create_task(...)`; never inside `inlet`.
- Keep a per-task timeout so a hung model cannot stall background work.
- Guard every internal import; a missing optional dependency must disable the feature, not the plugin.

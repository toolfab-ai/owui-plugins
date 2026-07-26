# Valves and UserValves

Valves and UserValves provide a two-tier configuration system for plugins, built on Pydantic `BaseModel`.

## Admin Valves (Valves)

Configured by administrators only via the Admin Panel.

```python
class Filter:
    class Valves(BaseModel):
        API_KEY: str = Field(default="", description="Your API key")
        MAX_REQUESTS: int = Field(default=100, description="Rate limit per minute")
        priority: int = Field(default=0, description="Execution order")
```

## User Valves (UserValves)

Configurable by any user directly from the chat interface.

```python
class Filter:
    class UserValves(BaseModel):
        language: str = Field(default="en", description="Output language")
        detailed: bool = Field(default=False, description="Enable detailed output")
```

## Accessing Valves in Code

### Admin Valves
Access directly via `self.valves`:
```python
api_key = self.valves.API_KEY
```

### User Valves
Access via `__user__["valves"]`:
```python
user_language = __user__["valves"].language
# or
user_language = dict(__user__["valves"])["language"]
# NOT: dict(__user__["valves"])["language"] — returns default instead of actual value
```

## UI Rendering Based on Field Types

Pydantic field types determine the UI widget:

| Field Type | UI Widget |
|------------|-----------|
| `str` | Text input |
| `bool` | Toggle switch |
| `int` / `float` | Number input |
| `Literal["a", "b"]` | Select dropdown |
| `List[str]` | Multi-select |

### Custom Input Types

Use `json_schema_extra` to customize rendering:

**Password input:**
```python
api_key: str = Field(
    default="", description="Your API key", json_schema_extra={"input": {"type": "password"}}
)
```

**Select dropdown:**
```python
priority: str = Field(
    default="medium",
    description="Processing priority",
    json_schema_extra={"input": {"type": "select", "options": ["low", "medium", "high"]}},
)
```

**Dynamic select (runtime options):**
```python
selected_model: str = Field(
    default="",
    description="Choose a model",
    json_schema_extra={"input": {"type": "select", "options": "get_model_options"}},
)


@classmethod
def get_model_options(cls, __user__=None) -> list[dict]:
    return [
        {"value": "gpt-4", "label": "GPT-4"},
        {"value": "claude-3", "label": "Claude 3"},
    ]
```

## Encrypting Valve Values at Rest

Set `ENABLE_VALVE_ENCRYPTION=true` to encrypt Valve values with Fernet (AES-128) using a key derived from `WEBUI_SECRET_KEY`.

**Requirements:**
- `WEBUI_SECRET_KEY` must be a valid 44-character url-safe base64 Fernet key
- Rotating the key makes previously encrypted values unreadable (must be re-entered)
- This applies to both `Valves` and `UserValves`

## Key Principles

- Valves are defined as nested Pydantic `BaseModel` classes inside the plugin class
- `Valves` are for admin config; `UserValves` are for user config
- All Valves fields should use `UPPER_SNAKE_CASE`
- Use `description` on every field for UI help text
- `required=False` can enforce optional fields explicitly
- A trailing `pass` in the Valves class is recommended for parsing compatibility

Source: [OpenWebUI Valves Docs](https://docs.openwebui.com/features/extensibility/plugin/development/valves/)
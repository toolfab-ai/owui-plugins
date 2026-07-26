# Best Practices

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Test file | `test_<name>.py` | `test_search.py`, `test_integration.py` |
| Test class | `Test<Feature>` | `TestRecencyDetection`, `TestSnippetConsistency` |
| Test method | `test_<behavior>` | `test_year_2025_detected`, `test_empty_snippets_list` |
| Test data constant | `UPPER_SNAKE_CASE` class attribute | `YES_SNIPPET`, `LONG_SNIPPET` |

## File Organization

```
plugins/<plugin-name>/
├── <plugin-name>.py          # Source plugin
├── pyproject.toml            # Plugin metadata & deps
├── tests/
│   ├── test_<feature>.py     # Unit tests (pure logic)
│   └── test_integration.py   # Integration tests (container-required)
```

## Patterns

### Use `setup_method` for fresh state

```python
def setup_method(self):
    self.tools = Tools()
```

Each test gets a fresh instance — no shared mutable state.

### Prefer `is True`/`is False` over truthiness

```python
# Good
assert needs is True
assert result["needs_full_fetch"] is False

# Avoid — booleans should be exact
assert needs
assert not result["needs_full_fetch"]
```

### Test One Behavior Per Method

Each test method should verify one logical assertion. If a method returns a tuple, check each element:

```python
def test_year_2025_detected(self):
    needs, reason, conf = self.tools._detect_recency_need("what happened in 2025")
    assert needs is True
    assert "2025" in reason
    assert conf == 0.95
```

### Cover Negative Cases

For every signal, test that it does **not** trigger on unrelated input:

```python
def test_historical_query(self):
    needs, _, _ = self.tools._detect_recency_need("causes of world war II")
    assert needs is False
```

### Use Descriptive Constants for Long Strings

Define multi-sentence test data as class-level constants to keep test methods readable:

```python
class TestSnippetConsistency:
    YES_SNIPPET = (
        "The answer is yes the framework supports asynchronous operations "
        "and provides a comprehensive API..."
    )
```

### Compare Returned Dict Fields by Key

```python
result = self.tools._analyze_snippet_consistency(...)
assert result["needs_full_fetch"] is True
assert "temporal" in result["reason"]
assert result["confidence"] == 0.7
```

### Let Unit Tests Inherit the Plugin's Default Valves

Avoid mocking or overriding valves in unit tests unless the test specifically exercises valve resolution. The default `Valves()` instance is sufficient for testing pure-logic methods.

## Test Data Strategy

- **Unit tests**: Craft minimal, realistic snippets that exercise each heuristic (contradiction, uncertainty, short length, etc.)
- **Integration tests**: Use the actual plugin source file — read it from disk with `Path.read_text()`

## Avoiding Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Plugin filename has hyphens (can't `import`) | Use `tests._plugin_loader.load_plugin()` |
| Integration tests share state | Create the tool in the first test method of the class |
| Missing `asyncio_mode` | Already set to `"auto"` in `pyproject.toml` — `async def` tests work automatically |
| Integration test without marker | Always add `@pytest.mark.integration` |

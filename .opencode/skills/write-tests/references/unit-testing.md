# Unit Testing

Unit tests cover pure-logic methods that do not require a running Open WebUI container. They rely on `load_plugin` to import the plugin module and instantiate its `Tools` class directory.

## File Structure

Place unit tests in `plugins/<plugin-name>/tests/test_<name>.py`.

## Basic Pattern

```python
"""Module docstring describing what's being tested."""

from tests._plugin_loader import load_plugin

mod = load_plugin("<plugin-name>")
MyClass = mod.MyClass


class TestFeature:
    def setup_method(self):
        self.instance = MyClass()

    def test_something(self):
        result = self.instance._some_method(...)
        assert result == expected_value
```

## Example: `tests/test_search.py` (optimized-search)

The full file is at `plugins/optimized-search/tests/test_search.py` (665 lines). Here are the key patterns:

### Grouping by Method

Each test class maps to one method:

```python
class TestRecencyDetection:
    """``_detect_recency_need`` — 5 pattern groups, complex regex matching."""

    def setup_method(self):
        self.tools = Tools()
```

### Testing Truthy/Falsey Return Values

```python
def test_year_2025_detected(self):
    needs, reason, conf = self.tools._detect_recency_need("what happened in 2025")
    assert needs is True
    assert "2025" in reason
    assert conf == 0.95


def test_old_year_not_detected(self):
    needs, reason, conf = self.tools._detect_recency_need("roman empire 117 AD")
    assert needs is False
```

### Testing Dict Return Values

```python
def test_simple_query_no_triggers(self):
    result = self.tools._analyze_query_complexity("bread recipe ingredients")
    assert result["decision"] == "simple"
    assert result["trigger_count"] == 0
    assert result["needs_fresh"] is False
```

### Testing Complex Decision Logic

```python
def test_recency_with_complexity_triggers_deep(self):
    result = self.tools._analyze_query_complexity("just announced best smartphone for photography")
    assert result["needs_fresh"] is True
    assert result["decision"] == "deep"
```

### Using Class-Level Constants for Readable Test Data

```python
class TestSnippetConsistency:
    LONG_SNIPPET = (
        "Python is an interpreted high-level general-purpose programming "
        "language with dynamic semantics and comprehensive standard library."
    )

    YES_SNIPPET = ...
    NO_SNIPPET = ...

    def test_yes_no_contradiction_detected(self):
        result = self.tools._analyze_snippet_consistency(
            [self.YES_SNIPPET, self.NO_SNIPPET],
            "framework async support",
        )
        assert result["needs_full_fetch"] is True
        assert "yes/no contradiction" in result["reason"]
```

### Testing Edge Cases

```python
def test_empty_snippets_list(self):
    result = self.tools._analyze_snippet_consistency([], "test")
    assert result["needs_full_fetch"] is True
    assert result["reason"] == "No snippets"


def test_force_fetch_bypasses_all_analysis(self):
    result = self.tools._analyze_snippet_consistency(["anything"], "test", force_fetch=True)
    assert result["needs_full_fetch"] is True
    assert result["confidence"] == 1.0
```

### Testing Negative Cases (No-Op)

```python
def test_non_recency_query(self):
    needs, reason, conf = self.tools._detect_recency_need("how to bake sourdough bread")
    assert needs is False
    assert reason == ""
    assert conf == 0.0


def test_historical_query(self):
    needs, _, _ = self.tools._detect_recency_need("causes of world war II")
    assert needs is False
```

## Running Unit Tests

```bash
# All unit tests across all plugins (default, no marker needed)
uv run pytest

# Specific test file
uv run pytest plugins/optimized-search/tests/test_search.py -v

# Specific test class
uv run pytest plugins/optimized-search/tests/test_search.py::TestRecencyDetection -v

# Specific test method
uv run pytest plugins/optimized-search/tests/test_search.py::TestRecencyDetection::test_year_2025_detected -v

# Exclude integration tests
uv run pytest -m "not integration"
```

# Plugin Development Guide

## General conventions

- Python 3.11+, target-version `py311`
- Ruff linting with `E`, `F`, `I`, `N`, `W` (line-length 100, ignore `E501`)
- pytest with `asyncio_mode = auto` (see [QA Guide](plugin_qa.md))


## Modular Plugin Architecture & Compilation

To keep complex plugins clean and simple to maintain, developers should split their plugin source code across multiple small files inside a `src/` subfolder. Files should be organized by **plugin feature** rather than generic categories like "helpers".

### 1. Directory Structure

```
plugins/<plugin-name>/
├── pyproject.toml                      # Plugin dependencies
├── build.py                            # Direct script to trigger ruff check, pytest, and compilation
├── install.py                          # MANDATORY: Script to install/update the plugin in Open WebUI
├── plugin.py                           # Compiled final single-file output (Do NOT edit directly)
├── src/
│   ├── meta.py                         # MANDATORY: Metadata block with Open WebUI frontmatter docstring
│   ├── _valves.py                      # MANDATORY: Admin-configurable settings (Valves)
│   ├── _updates.py                     # MANDATORY: Background update check mixin
│   ├── _search.py                      # EXAMPLE <feature>: Search engine integration mixin
│   ├── _scraper.py                     # EXAMPLE <feature>: Web scraping mixin
│   ├── _analysis.py                    # EXAMPLE <feature>: Logic/processing mixin
│   └── main.py                         # MANDATORY: Entry point (inherits from all feature mixins)
└── tests/
    ├── test_<feature>.py     # Unit test suite (pure logic)
    └── test_integration.py   # Integration test suite (container-gated)

For detailed information on writing and running tests, see the [Plugin QA Guide](plugin_qa.md).
```

### 2. The Valves Rule

All admin-configurable settings must be defined in `src/_valves.py` within a Pydantic `BaseModel` class named `Valves`.
- **Detailed Descriptions**: Every `Field` must include a `description` that clearly explains the setting's impact.
- **Validation**: Use Pydantic's validation features (`ge`, `le`, `min_length`, etc.) where applicable.

### 3. Multi-File Compilation Mechanics

During a build, the build runner (`build.py` using `scripts/build_lib.py`) automatically compiles the final single-file plugin using these rules:
1.  **Metadata Extraction**: Extracts the docstring from `src/meta.py` and places it at the absolute top of the final output file as the global metadata.
2.  **Feature Modules Merging**: Reads all files starting with an underscore (e.g. `src/_*.py`) alphabetically, strips any relative imports (e.g., `from .` or `import .`), and appends them to the builder stream.
3.  **Entry Point Merging**: Reads `src/main.py`, strips its own docstring and relative imports, and appends the core logic at the bottom of the stream.
4.  **Formatting and Verification**: Formats the final file using `ruff format`, runs quality audits (`ruff check`), and executes both unit and integration test suites before writing the production-ready code to `plugin.py`.

### 4. Mixin Design Pattern

To preserve type validation and logical scoping across separate source files, classes should be structured as **Mixins**. The core class in `src/main.py` simply inherits from these feature-specific mixins. Split logic into small, focused mixins that each handle a single conceptual feature.

### 5. Installation Script (`install.py`)

Every plugin must include an `install.py` script to automate deployment to an Open WebUI instance. This script uses the `OwuiClient` to interface with the Open WebUI API.

-   **Environment Variables**:
    -   `OWUI_URL`: The base URL of your Open WebUI instance (defaults to `http://localhost:3000`).
    -   `OWUI_TOKEN`: Your API key or JWT token (required).
-   **Workflow**:
    1.  Reads the compiled `plugin.py`.
    2.  Identifies if the plugin is a **Tool** or a **Function** (Action/Filter/Pipe).
    3.  Automates the creation or updating of the plugin on the target instance via API.
    4.  Configures access permissions (e.g., sharing Tools with all users) and activates Functions.

### 6. The Update Notifier Rule

Every plugin must include `src/_updates.py` to provide background update checks. This module must import the shared `UpdateMixin` and configure the plugin-specific tag prefix.

- **Implementation**:
  ```python
  from shared.update_notifier.notifier import UpdateMixin

  class UpdateMixin(UpdateMixin):
      _RELEASE_TAG_PREFIX: str = "your-plugin-name/"
  ```
- **Placeholders**: The notification message (defined in the shared mixin) supports `{plugin_name}`, `{version}`, and `{url}` (for admins). The `{plugin_name}` is automatically extracted from the `title` field in `src/meta.py`.
- **Configuration**: The `UpdateMixin` expects `ENABLE_UPDATE_NOTIFICATIONS` and `CHECK_PREVIEW_RELEASES` fields to be present in the plugin's `Valves` class (defined in `src/_valves.py`).
- **Trigger**: The update check should typically be called at the start of the plugin's main execution method (e.g., `pipe` or `action`).
79: 
80: ### 7. The User Valves Rule
81: 
82: Complex plugins that require per-user overrides (like API keys or specific behavior settings) must implement the `UserValves` pattern. This allows users to configure the plugin directly from the chat interface without affecting other users or requiring global admin changes.
83: 
84: - **Implementation**: Follow the strict resolution logic and naming standards defined in [Valve Conventions](valves_conventions.md).
### 8. Proxy and Custom URL Support

Plugins that perform network requests (e.g., to external APIs, search engines, or LLMs) must support proxy configuration and custom base URLs to ensure compatibility with enterprise environments and local deployments.

- **Proxy Configuration**: Include a `proxy_url` field in `Valves` to allow routing traffic through an HTTP/HTTPS proxy.
- **Custom URLs**: Always provide a `base_url` or equivalent field in `Valves` for API endpoints, rather than hardcoding production URLs.
- **Reverse Proxy Support**: For plugins that generate links or return files (Actions/Tools), use `__request__` to detect the public host.

#### Implementation Examples:

**Outbound Proxy (httpx):**
```python
async with httpx.AsyncClient(
    proxies=self.valves.proxy_url if self.valves.proxy_url else None,
    timeout=10.0
) as client:
    response = await client.get(url)
```

**Base URL Resolution (Inbound/Links):**
```python
def _resolve_base_url(self, __request__=None) -> str:
    # 1. Manual Valve Override
    if self.valves.base_url:
        return self.valves.base_url.rstrip("/")
    
    # 2. Reverse Proxy Detection
    if __request__:
        host = __request__.headers.get("x-original-host") or __request__.headers.get("host")
        if host:
            scheme = __request__.headers.get("x-forwarded-proto", "https")
            return f"{scheme}://{host}"
            
    # 3. Environment Fallback
    return os.environ.get("WEBUI_URL", "http://localhost:3000").rstrip("/")
```

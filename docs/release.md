# Release Guide

This guide explains the release process for Open WebUI plugins in this monorepo. Releases are strictly managed by maintainers using Git tags and automated GitHub Actions.

## Release Process Overview

Releases are triggered by pushing a specific tag format to the repository. The automation handles building the final `plugin.py`, creating a GitHub Release, and attaching the production-ready code.

### 1. Versioning Convention

We follow a strict tagging convention to identify which plugin and version to release:

- **Format**: `<plugin-folder-name>/v<semver>`
- **Stable Release**: `iterative-research/v1.0.0`
- **Pre-release**: `iterative-research/v1.0.0-beta.1` (Any version containing a **hyphen** `-` is automatically treated as a pre-release).

### 2. Triggering a Release

To release a plugin, a maintainer pushes a tag:

```bash
# Example: Releasing Iterative Research v1.0.0
git tag iterative-research/v1.0.0
git push origin iterative-research/v1.0.0
```

### 3. Automated Workflow Actions

Once the tag is pushed, the `.github/workflows/release.yml` workflow performs the following steps:

1.  **Tag Parsing**: Extracts the plugin name and version from the tag.
2.  **Pre-release Detection**: Checks for a hyphen in the version. If found:
    - Sets the GitHub Release to `prerelease: true`.
    - Injects a `[!CAUTION]` warning into the release body.
3.  **Build & Compilation**: Runs `uv run python build.py <version>` for the specific plugin. This step:
    - Runs `ruff check` and `ruff format`.
    - Executes the unit and integration test suites.
    - Merges modular source files from `src/` into the final `plugin.py`.
    - Updates the version in `pyproject.toml` and the module docstring.
4.  **GitHub Release Creation**: Creates a formal GitHub Release and attaches the compiled `plugin.py`.
5.  **Version Synchronization**: Commits the version bump in `pyproject.toml` back to the `trunk` branch to keep the source of truth in sync.

## Maintainer Responsibility

> [!IMPORTANT]
> **Only project maintainers are eligible to release plugins.**

Contributors should submit Pull Requests. Once merged, a maintainer will review the state of the `trunk` branch and trigger the release using the tagging method described above.

### Pre-release Verification
Before pushing a stable tag, maintainers are encouraged to:
1.  Run the local build script: `uv run python build.py` inside the plugin directory.
2.  Verify the generated `plugin.py` manually in a [bootstrap environment](plugin_qa.md#route-3-manual-testing-ui-iteration).
3.  Push a `-beta` or `-rc` tag first if the changes are significant.

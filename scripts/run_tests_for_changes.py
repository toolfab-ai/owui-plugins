"""Run pytest for plugins that have changed since the last push.

Designed for pre-commit's pre-push stage.  Uses ``PRE_COMMIT_FROM_REF``
and ``PRE_COMMIT_TO_REF`` environment variables set by pre-commit.

- Changes to core infrastructure (``conftest.py``, ``pyproject.toml``,
  ``tests/``) run **all** unit tests.
- Changes inside a ``plugins/<name>/`` directory run only that plugin's tests.
- Changes to non-plugin files (scripts, docs, …) skip tests entirely.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"

CORE_PATHS = {
    "conftest.py",
    "pyproject.toml",
    ".pre-commit-config.yaml",
}


def get_changed_files() -> list[str]:
    from_ref = os.environ.get("PRE_COMMIT_FROM_REF", "")
    to_ref = os.environ.get("PRE_COMMIT_TO_REF", "")

    if from_ref and to_ref:
        result = subprocess.run(
            ["git", "diff", "--name-only", to_ref, from_ref],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    else:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

    return [f for f in result.stdout.splitlines() if f]


def get_affected_plugins(changed_files: list[str]) -> set[str] | None:
    plugins: set[str] = set()
    for f in changed_files:
        if f in CORE_PATHS or f.startswith("tests/"):
            return None
        parts = Path(f).parts
        if len(parts) > 1 and parts[0] == "plugins":
            plugins.add(parts[1])
    return plugins


def main() -> None:
    changed_files = get_changed_files()
    if not changed_files:
        sys.exit(0)

    affected = get_affected_plugins(changed_files)

    if affected is None:
        cmd = ["uv", "run", "pytest", "-m", "not integration", "-x"]
    elif not affected:
        sys.exit(0)
    else:
        test_paths: list[str] = []
        for name in sorted(affected):
            test_dir = PLUGINS_DIR / name / "tests"
            if test_dir.is_dir():
                test_paths.append(str(test_dir))
        if not test_paths:
            sys.exit(0)
        cmd = ["uv", "run", "pytest", "-m", "not integration", "-x", *test_paths]

    result = subprocess.run(cmd, cwd=ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

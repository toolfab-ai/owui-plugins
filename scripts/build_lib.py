"""Shared build utilities for Open WebUI plugin releases."""

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


def verify_lint(plugin_root: Path) -> None:
    result = subprocess.run(
        ["uv", "run", "ruff", "check", str(plugin_root)],
        cwd=plugin_root.parent.parent,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def verify_format(plugin_root: Path) -> None:
    result = subprocess.run(
        ["uv", "run", "ruff", "format", "--check", str(plugin_root)],
        cwd=plugin_root.parent.parent,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def run_unit_tests(plugin_root: Path) -> None:
    test_dir = plugin_root / "tests"
    if not test_dir.is_dir():
        return
    has_tests = list(test_dir.rglob("test_*.py"))
    if not has_tests:
        return
    result = subprocess.run(
        ["uv", "run", "pytest", "-m", "unit", "-x", str(test_dir)],
        cwd=plugin_root.parent.parent,
    )
    if result.returncode not in (0, 5):
        sys.exit(result.returncode)


def run_integration_tests(plugin_root: Path) -> None:
    test_dir = plugin_root / "tests"
    if not test_dir.is_dir():
        return
    has_integration = list(test_dir.rglob("*integration*"))
    if not has_integration:
        return
    result = subprocess.run(
        ["uv", "run", "pytest", "-m", "integration", "-x", str(test_dir)],
        cwd=plugin_root.parent.parent,
    )
    if result.returncode not in (0, 5):
        sys.exit(result.returncode)


def merge_sources(src_dir: Path) -> str:
    parts = []
    seen_shared = set()
    repo_root = src_dir.parent.parent.parent

    meta_file = src_dir / "meta.py"
    if meta_file.exists():
        tree = ast.parse(meta_file.read_text(encoding="utf-8"))
        docstring = ast.get_docstring(tree)
        if docstring:
            parts.append(f'"""\n{docstring}\n"""')

    parts.append("from __future__ import annotations")

    internal_files = sorted(src_dir.glob("_*.py"))
    for f in internal_files:
        content = f.read_text(encoding="utf-8")
        content = _strip_docstring(content)
        content = _resolve_shared_imports(content, repo_root, seen_shared)
        content = _strip_internal_imports(content)
        parts.append(content)

    main_file = src_dir / "main.py"
    if main_file.exists():
        content = main_file.read_text(encoding="utf-8")
        content = _strip_docstring(content)
        content = _resolve_shared_imports(content, repo_root, seen_shared)
        content = _strip_internal_imports(content)
        parts.append(content)
    return "\n\n".join(parts)


def _resolve_shared_imports(content: str, repo_root: Path, seen_shared: set[str]) -> str:
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("from shared."):
            # e.g., from shared.update_notifier.notifier import UpdateMixin
            match = re.match(r"from shared\.([\w\.]+)\s+import\s+.*", stripped)
            if match:
                module_name = match.group(1)
                if module_name in seen_shared:
                    continue

                module_path = module_name.replace(".", "/") + ".py"
                full_path = repo_root / "shared" / module_path
                if full_path.exists():
                    shared_content = full_path.read_text(encoding="utf-8")
                    shared_content = _strip_docstring(shared_content)
                    shared_content = _strip_internal_imports(shared_content)
                    # Recursively resolve if the shared module itself imports other shared modules
                    shared_content = _resolve_shared_imports(shared_content, repo_root, seen_shared)
                    lines.append(f"# --- Shared: {module_name} ---")
                    lines.append(shared_content)
                    lines.append("# --- End Shared ---")
                    seen_shared.add(module_name)
                    continue
        lines.append(line)
    return "\n".join(lines)


def _strip_internal_imports(content: str) -> str:
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if (
            stripped.startswith("from .")
            or stripped.startswith("import .")
            or stripped.startswith("from __future__")
        ):
            continue
        lines.append(line)
    return "\n".join(lines)


def _strip_docstring(content: str) -> str:
    for quote in ['"""', "'''"]:
        stripped = content.lstrip()
        if not stripped.startswith(quote):
            continue
        idx = content.index(quote)
        after = idx + 3
        end = after
        while True:
            end = content.find(quote, end)
            if end == -1:
                break
            if content[end - 1] != "\\":
                end += 3
                break
            end += 3
        if end > after:
            rest = content[end:].lstrip("\n")
            return rest
    return content


def inject_version(content: str, version: str) -> str:
    return re.sub(
        r"(^version:\s*).+",
        f"\\g<1>{version}",
        content,
        flags=re.MULTILINE,
    )


def update_pyproject_toml(pyproject_path: Path, version: str) -> None:
    content = pyproject_path.read_text(encoding="utf-8")
    content = re.sub(
        r'(^version\s*=\s*")[^"]+(")',
        f"\\g<1>{version}\\g<2>",
        content,
        flags=re.MULTILINE,
    )
    pyproject_path.write_text(content, encoding="utf-8")


def write_output(content: str, path: Path) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"Built: {path}")


def verify(plugin_root: Path) -> None:
    verify_lint(plugin_root)
    verify_format(plugin_root)
    run_unit_tests(plugin_root)
    print(f"Validation passed: {plugin_root.name}")


def build(
    plugin_root: Path,
    version: Optional[str] = None,
    check_only: bool = False,
    skip_tests: bool = False,
) -> None:
    verify_lint(plugin_root)
    verify_format(plugin_root)

    # 1. Unit tests run early as they don't depend on merged output
    if not skip_tests:
        run_unit_tests(plugin_root)

    # 2. Merge source files
    output = merge_sources(plugin_root / "src")
    if version:
        output = inject_version(output, version)

    # 3. Handle check_only mode (returns before writing or running integration tests)
    if check_only:
        print(f"Check passed: {plugin_root.name}")
        return

    # 4. Write output to plugin.py (required for integration tests and release)
    output_path = plugin_root / "plugin.py"
    write_output(output, output_path)
    if version:
        update_pyproject_toml(plugin_root / "pyproject.toml", version)

    # 5. Integration tests run LAST, as they rely on the existence of plugin.py
    if not skip_tests:
        run_integration_tests(plugin_root)

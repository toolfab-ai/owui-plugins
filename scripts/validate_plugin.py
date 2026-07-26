"""Validate Open WebUI plugin files for correct structure and metadata."""

import ast
import re
import sys
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"

SKIP_FILES = {"build.py", "plugin.py", "__init__.py"}

VALID_CLASS_NAMES = {"Tools", "Action", "Filter", "Pipe"}
REQUIRED_META = {"title", "author", "version", "description"}


def parse_docstring_meta(docstring: str) -> dict[str, str]:
    meta = {}
    for line in docstring.strip().splitlines():
        m = re.match(r"^(\w+):\s*(.+)$", line.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta


def validate_plugin(path: Path) -> list[str]:
    errors = []
    source = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]

    docstring = ast.get_docstring(tree)
    if not docstring:
        errors.append("Missing module docstring")

    meta = parse_docstring_meta(docstring or "")
    for key in REQUIRED_META:
        if key not in meta:
            errors.append(f"Missing required metadata field: '{key}'")

    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    class_names = {c.name for c in classes}

    if not class_names & VALID_CLASS_NAMES:
        errors.append(
            f"No valid plugin class found. Expected one of: {', '.join(sorted(VALID_CLASS_NAMES))}"
        )
    else:
        _funcdef = (ast.FunctionDef, ast.AsyncFunctionDef)
        for c in classes:
            if c.name in VALID_CLASS_NAMES:
                methods = [n.name for n in ast.walk(c) if isinstance(n, _funcdef)]
                if c.name == "Action" and "action" not in methods:
                    errors.append("Action class missing 'action' method")
                if c.name == "Tools" and not any(m for m in methods if not m.startswith("_")):
                    errors.append("Tools class has no public methods")

    return errors


def _combined_src(plugin_dir: Path) -> tuple[str | None, str | None]:
    meta_file = plugin_dir / "src" / "meta.py"
    main_file = plugin_dir / "src" / "main.py"
    meta_source = meta_file.read_text(encoding="utf-8") if meta_file.is_file() else None
    main_source = main_file.read_text(encoding="utf-8") if main_file.is_file() else None
    return meta_source, main_source


def _validate_src_layout(plugin_dir: Path) -> list[str]:
    meta_source, main_source = _combined_src(plugin_dir)
    if not meta_source and not main_source:
        return []

    errors: list[str] = []

    if meta_source:
        try:
            meta_tree = ast.parse(meta_source)
        except SyntaxError as e:
            return [f"Syntax error in meta.py: {e}"]

        docstring = ast.get_docstring(meta_tree)
        if not docstring:
            errors.append(f"{plugin_dir.name}/src/meta.py: Missing module docstring")
        else:
            meta = parse_docstring_meta(docstring)
            for key in REQUIRED_META:
                if key not in meta:
                    errors.append(
                        f"{plugin_dir.name}/src/meta.py: Missing required metadata field: '{key}'"
                    )

    if main_source:
        try:
            tree = ast.parse(main_source)
        except SyntaxError as e:
            return [*errors, f"Syntax error in main.py: {e}"]

        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        class_names = {c.name for c in classes}

        if not class_names & VALID_CLASS_NAMES:
            errors.append(
                f"{plugin_dir.name}/src/main.py: No valid plugin class found. "
                f"Expected one of: {', '.join(sorted(VALID_CLASS_NAMES))}"
            )
        else:
            _funcdef = (ast.FunctionDef, ast.AsyncFunctionDef)
            for c in classes:
                if c.name in VALID_CLASS_NAMES:
                    methods = [n.name for n in ast.walk(c) if isinstance(n, _funcdef)]
                    if c.name == "Action" and "action" not in methods:
                        errors.append(
                            f"{plugin_dir.name}/src/main.py: Action class missing 'action' method"
                        )
                    if c.name == "Tools" and not any(m for m in methods if not m.startswith("_")):
                        errors.append(
                            f"{plugin_dir.name}/src/main.py: Tools class has no public methods"
                        )

    return errors


def _plugin_sources(plugin_dir: Path) -> list[Path]:
    flat_files = [f for f in sorted(plugin_dir.glob("*.py")) if f.name not in SKIP_FILES]
    src_main = plugin_dir / "src" / "main.py"
    src_meta = plugin_dir / "src" / "meta.py"
    has_src_layout = src_main.is_file() or src_meta.is_file()
    return flat_files if not has_src_layout else []


def main():
    exit_code = 0
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir():
            continue

        flat_files = _plugin_sources(plugin_dir)
        if flat_files:
            for py_file in flat_files:
                errors = validate_plugin(py_file)
                if errors:
                    exit_code = 1
                    print(f"FAIL  {py_file.relative_to(PLUGINS_DIR.parent)}")
                    for err in errors:
                        print(f"       - {err}")
                else:
                    print(f"OK    {py_file.relative_to(PLUGINS_DIR.parent)}")
        else:
            errors = _validate_src_layout(plugin_dir)
            if errors:
                exit_code = 1
                for err in errors:
                    print(
                        f"FAIL  {plugin_dir.name}/src/{err.split(':', 1)[0].split('/')[-1] if '/' in err else err}"
                    )
                    if ": " in err:
                        print(f"       - {err.split(': ', 1)[1]}")
            else:
                print(f"OK    {plugin_dir.name}/src/")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

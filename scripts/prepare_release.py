"""Prepare release metadata for Open WebUI plugins."""

import hashlib
import os
import re
import sys
from pathlib import Path


def extract_changelog(plugin_path: Path, version: str) -> str:
    changelog_path = plugin_path / "CHANGELOG.md"
    if not changelog_path.exists():
        print(f"::error::Missing CHANGELOG.md for plugin {plugin_path.name}")
        sys.exit(1)

    content = changelog_path.read_text(encoding="utf-8")
    header_pattern = rf"^## \[{re.escape(version)}\](?: - \d{{4}}-\d{{2}}-\d{{2}})?\s*$"
    lines = content.splitlines()
    start_idx = -1
    for i, line in enumerate(lines):
        if re.match(header_pattern, line):
            start_idx = i + 1
            break

    if start_idx == -1:
        print(f"::error::Version {version} header not found in {plugin_path.name}/CHANGELOG.md")
        sys.exit(1)

    content_lines = []
    for i in range(start_idx, len(lines)):
        if lines[i].startswith("## ["):
            break
        content_lines.append(lines[i])

    return "\n".join(content_lines).strip()


def calculate_checksum(file_path: Path) -> str:
    if not file_path.exists():
        print(f"::error::File not found for checksum: {file_path}")
        sys.exit(1)

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def main() -> None:
    plugin = os.environ.get("plugin")
    version = os.environ.get("version")
    tag = os.environ.get("tag")
    repo = os.environ.get("GITHUB_REPOSITORY")
    status_note = os.environ.get("status_note", "")

    if not all([plugin, version, tag, repo]):
        print("::error::Missing environment variables (plugin, version, tag, GITHUB_REPOSITORY)")
        sys.exit(1)

    plugin_path = Path(f"plugins/{plugin}")
    plugin_file = plugin_path / "plugin.py"

    changelog = extract_changelog(plugin_path, version)
    checksum = calculate_checksum(plugin_file)

    template_path = Path("scripts/release_template.md")
    if not template_path.exists():
        print("::error::Missing scripts/release_template.md")
        sys.exit(1)

    template = template_path.read_text(encoding="utf-8")
    values = {
        "{plugin}": plugin,
        "{version}": version,
        "{repo}": repo,
        "{tag}": tag,
        "{status_note}": status_note,
        "{changelog}": changelog,
        "{checksum}": checksum,
    }

    body = template
    for placeholder, value in values.items():
        body = body.replace(placeholder, value)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write("body<<EOF\n")
            f.write(body + "\n")
            f.write("EOF\n")
    else:
        print(body)


if __name__ == "__main__":
    main()

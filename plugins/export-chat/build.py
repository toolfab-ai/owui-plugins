#!/usr/bin/env python3
"""Build script for export-chat plugin."""

import sys
from pathlib import Path

# ruff: noqa: I001
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.build_lib import build


if __name__ == "__main__":
    root = Path(__file__).parent
    version = None
    check_only = False
    for arg in sys.argv[1:]:
        if arg == "--check":
            check_only = True
        elif arg.startswith("--version="):
            version = arg.split("=", 1)[1]
        elif arg.startswith("--"):
            print(f"Unknown flag: {arg}")
            sys.exit(1)
        else:
            version = arg
    build(root, version=version, check_only=check_only)

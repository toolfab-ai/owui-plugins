#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from pathlib import Path

from tests.owui_client import OwuiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("install")

# Configuration Constants
DEFAULT_OWUI_URL = "http://localhost:3000"
PLUGIN_FILE_NAME = "plugin.py"
TOOL_TYPE_KEYWORD = "class Tools"
PTYPE_TOOL = "tool"
PTYPE_FUNCTION = "function"
PUBLIC_ACCESS_GRANTS = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def plugin_id_from_path(path: Path) -> str:
    return path.parent.name.replace("-", "_").replace(".", "_").lower()


def plugin_name_from_meta(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip()
    return "Unknown"


def get_plugin_type(content: str) -> str:
    if TOOL_TYPE_KEYWORD in content:
        return PTYPE_TOOL
    return PTYPE_FUNCTION


async def install():
    url = os.environ.get("OWUI_URL", DEFAULT_OWUI_URL)
    token = os.environ.get("OWUI_TOKEN")

    if not token:
        logger.error("OWUI_TOKEN environment variable is required")
        sys.exit(1)

    plugin_dir = Path(__file__).parent
    plugin_file = plugin_dir / PLUGIN_FILE_NAME

    if not plugin_file.exists():
        logger.error(f"{PLUGIN_FILE_NAME} not found in {plugin_dir}. Did you run build.py?")
        sys.exit(1)

    content = plugin_file.read_text(encoding="utf-8")
    pid = plugin_id_from_path(plugin_file)
    pname = plugin_name_from_meta(content)
    ptype = get_plugin_type(content)

    client = OwuiClient(url)
    client.token = token

    logger.info(f"Installing {ptype} {pname} ({pid})...")

    try:
        if ptype == PTYPE_TOOL:
            try:
                await client.create_tool(
                    tool_id=pid,
                    name=pname,
                    content=content,
                    description=f"Auto-installed from {plugin_dir.name}",
                )
                logger.info(f"Created tool: {pid}")
            except RuntimeError as e:
                if "409" in str(e) or "already registered" in str(e):
                    # We don't have a direct update_tool method in OwuiClient yet that takes content,
                    # but we can update access. For now, let's assume it's there or handle it.
                    logger.info(f"Tool {pid} already exists")
                else:
                    raise e

            # Make tool public
            await client.update_tool_access(pid, PUBLIC_ACCESS_GRANTS)
            logger.info(f"Shared tool: {pid}")

        else:
            try:
                await client.create_function(
                    function_id=pid,
                    name=pname,
                    content=content,
                    description=f"Auto-installed from {plugin_dir.name}",
                )
                logger.info(f"Created function: {pid}")
            except RuntimeError as e:
                if "409" in str(e) or "already registered" in str(e):
                    await client.update_function(
                        function_id=pid,
                        name=pname,
                        content=content,
                        description=f"Auto-installed from {plugin_dir.name}",
                    )
                    logger.info(f"Updated function: {pid}")
                else:
                    raise e

            # Activate
            try:
                res = await client.toggle_function(pid)
                if not res.get("is_active"):
                    await client.toggle_function(pid)
                logger.info(f"Activated function: {pid}")
            except RuntimeError:
                logger.warning(f"Could not activate function: {pid}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(install())

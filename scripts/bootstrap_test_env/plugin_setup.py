import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

BUILD_SCRIPT_NAME = "build.py"
INSTALL_SCRIPT_NAME = "install.py"
BUILD_ARGS = ["--skip-tests"]


def build_plugin(plugin_dir: Path, url: str):
    """Run the plugin's build script."""
    build_script = plugin_dir / BUILD_SCRIPT_NAME
    if not build_script.exists():
        return False

    logger.info("Building plugin: %s", plugin_dir.name)
    env = os.environ.copy()
    env["OWUI_URL"] = url
    result = subprocess.run(
        [sys.executable, str(build_script)] + BUILD_ARGS,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        logger.error("Build failed for %s:\n%s", plugin_dir.name, result.stderr)
        return False
    return True


async def install_plugin(plugin_dir: Path, url: str, token: str):
    """Run the plugin's install script or fallback to generic install."""
    install_script = plugin_dir / INSTALL_SCRIPT_NAME

    if install_script.exists():
        logger.info("Running install script for: %s", plugin_dir.name)
        # Find the project root (3 levels up from this file: scripts/bootstrap_test_env/plugin_setup.py)
        root = Path(__file__).resolve().parent.parent.parent
        env = os.environ.copy()
        env["OWUI_URL"] = url
        env["OWUI_TOKEN"] = token
        # Add project root to PYTHONPATH so install.py can find tests.owui_client
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{root}:{existing_pythonpath}" if existing_pythonpath else str(root)
        result = subprocess.run(
            [sys.executable, str(install_script)],
            cwd=plugin_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        if result.returncode != 0:
            logger.error("Install script failed for %s:\n%s", plugin_dir.name, result.stderr)
            return None
        return plugin_dir.name
    else:
        logger.warning(
            "No %s found for %s, skipping installation (or implement fallback)",
            INSTALL_SCRIPT_NAME,
            plugin_dir.name,
        )
        return None


async def setup_plugins(plugins_dir: Path, url: str, token: str):
    """Build and install all plugins."""
    installed = []
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue

        if build_plugin(plugin_dir, url):
            pid = await install_plugin(plugin_dir, url, token)
            if pid:
                installed.append(pid)
    return installed

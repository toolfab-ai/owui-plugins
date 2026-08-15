import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from tests.owui_client import OwuiClient

from .ai_provider_setup import setup_ai_provider
from .docker_setup import run_docker_compose
from .plugin_setup import setup_plugins
from .user_setup import setup_users

logger = logging.getLogger("bootstrap")

ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_FILE = ROOT / "tests" / "docker-compose.yml"
PLUGINS_DIR = ROOT / "plugins"
DEFAULT_PORT = "3000"


async def bootstrap():
    load_dotenv()
    port = os.environ.get("OWUI_PORT", DEFAULT_PORT)
    url = f"http://localhost:{port}"

    # 1. Launch Docker
    run_docker_compose(COMPOSE_FILE, port)

    client = OwuiClient(url)
    try:
        await client.wait_for_ready()
        logger.info("Open WebUI is ready at %s", url)

        # 2. Setup Users
        user_info = await setup_users(client)
        admin_token = client.token

        # 3. Setup AI Provider
        await setup_ai_provider(client)

        # 4. Setup Plugins
        installed = await setup_plugins(PLUGINS_DIR, url, admin_token)

        user_lines = "\n".join(
            [f"  User:     {u['email']} / {u['password']}" for u in user_info["users"]]
        )

        logger.info(
            f"""
============================================================
  Manual Testing Environment Ready
============================================================
  URL:      {url}
  Admin:    {user_info["admin"]["email"]} / {user_info["admin"]["password"]}
{user_lines}
  Plugins:  {", ".join(installed)}

  Container is RUNNING. Shut down manually with:
  docker compose -f tests/docker-compose.yml down -v
============================================================
"""
        )

    finally:
        await client.close()

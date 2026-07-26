import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from tests.owui_client import OwuiClient


@pytest.fixture(scope="session")
def owui_url() -> str:
    """Start or connect to Open WebUI and return its base URL.

    Set ``OWUI_URL`` to skip docker-compose lifecycle (manual mode).
    """
    url = os.environ.get("OWUI_URL")
    if url:
        return url

    compose_file = Path(__file__).parent / "tests" / "docker-compose.yml"
    port = os.environ.get("OWUI_PORT", "3000")
    env = os.environ.copy()
    env["OWUI_PORT"] = port

    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d", "--remove-orphans"],
        check=True,
        env=env,
    )

    url = f"http://localhost:{port}"

    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/api/auth", timeout=5.0)
            if r.status_code == 200:
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(2)
    else:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "-v"],
            env=env,
        )
        raise RuntimeError(f"Open WebUI did not become ready within 120s at {url}")

    yield url

    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "down", "-v"],
        env=env,
    )


@pytest.fixture
async def owui_client(owui_url: str) -> OwuiClient:
    client = OwuiClient(owui_url)
    try:
        await client.signup()
    except RuntimeError:
        await client.signin()
    yield client
    await client.close()

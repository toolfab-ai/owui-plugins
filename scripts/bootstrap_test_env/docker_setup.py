import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DOCKER_CMD = "docker"
DOCKER_INFO_CMD = [DOCKER_CMD, "info"]
DOCKER_COMPOSE_CMD = [DOCKER_CMD, "compose"]
DOCKER_START_WAIT_SECONDS = 60
DOCKER_POLL_INTERVAL = 2

# Platform specific start commands
DARWIN_START_CMD = ["open", "--background", "-a", "Docker"]
LINUX_START_CMD = ["sudo", "systemctl", "start", "docker"]


def ensure_docker_running():
    """Check if Docker engine is running and attempt to start it if not."""
    try:
        subprocess.run(DOCKER_INFO_CMD, check=True, capture_output=True)
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("Docker engine is not running. Attempting to start...")

        if sys.platform == "darwin":
            # Start Docker Desktop on macOS
            subprocess.run(DARWIN_START_CMD, check=True)
        elif sys.platform.startswith("linux"):
            # Start Docker via systemctl on Linux (may require sudo)
            subprocess.run(LINUX_START_CMD, check=True)
        else:
            logger.error("Unsupported platform %s to start Docker automatically.", sys.platform)
            sys.exit(1)

        # Wait for Docker to start (up to 60 seconds)
        for i in range(DOCKER_START_WAIT_SECONDS // DOCKER_POLL_INTERVAL):
            try:
                subprocess.run(DOCKER_INFO_CMD, check=True, capture_output=True)
                logger.info("Docker engine is now running.")
                return
            except subprocess.CalledProcessError:
                if i % 5 == 0:
                    logger.info("Waiting for Docker to initialize...")
                time.sleep(DOCKER_POLL_INTERVAL)

        logger.error("Docker engine failed to start within %s seconds.", DOCKER_START_WAIT_SECONDS)
        sys.exit(1)


def run_docker_compose(compose_file: Path, port: str):
    ensure_docker_running()

    logger.info("Ensuring Open WebUI is running...")
    env = os.environ.copy()
    env["OWUI_PORT"] = port

    # Auto-configure WEBUI_URL and CORS for local development to prevent "Old UI" fallback
    local_url = f"http://localhost:{port}"
    if not env.get("WEBUI_URL"):
        env["WEBUI_URL"] = local_url
        logger.info("Setting WEBUI_URL to %s", local_url)

    cors = env.get("CORS_ALLOW_ORIGIN", "*")
    if cors != "*" and local_url not in cors:
        env["CORS_ALLOW_ORIGIN"] = f"{cors};{local_url};http://127.0.0.1:{port}"
        logger.info("Appended local origins to CORS_ALLOW_ORIGIN")

    # Log the resolved configuration for debugging "Old UI" issues
    logger.info("Verifying resolved Docker Compose configuration...")
    config_result = subprocess.run(
        DOCKER_COMPOSE_CMD + ["-f", str(compose_file), "config"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if config_result.returncode == 0:
        # We use debug level for the full YAML to keep output clean, but show it now since requested
        logger.info(
            "--- Resolved Compose YAML ---\n%s\n---------------------------", config_result.stdout
        )
    else:
        logger.error("Failed to resolve Docker Compose config: %s", config_result.stderr)

    # Force pull and recreate to ensure environment changes apply
    logger.info("Pulling latest Open WebUI image and recreating containers...")
    subprocess.run(
        DOCKER_COMPOSE_CMD + ["-f", str(compose_file), "pull"],
        check=False,
        env=env,
    )

    subprocess.run(
        DOCKER_COMPOSE_CMD
        + [
            "-f",
            str(compose_file),
            "up",
            "-d",
            "--force-recreate",
            "--remove-orphans",
        ],
        check=True,
        env=env,
    )

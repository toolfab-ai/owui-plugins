import asyncio
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_API_BASE_URL = "https://api.kilo.ai/api/gateway"
DEFAULT_MODEL_ID = "stepfun/step-3.7-flash:free"
DISCOVERY_TIMEOUT_ATTEMPTS = 15
DISCOVERY_POLL_INTERVAL = 2


def get_provider_name(url: str) -> str:
    """Derive a provider name from the base URL."""
    return urlparse(url).hostname or "Provider"


async def setup_ai_provider(client):
    """Configure external AI provider if environment variables are present."""
    api_key = os.environ.get("BOOTSTRAP_OPENAI_API_KEY")
    base_url = os.environ.get("BOOTSTRAP_OPENAI_API_BASE_URL", DEFAULT_API_BASE_URL)
    model_id = os.environ.get("BOOTSTRAP_OPENAI_API_MODEL_ID", DEFAULT_MODEL_ID)

    if not api_key:
        logger.warning("BOOTSTRAP_OPENAI_API_KEY not found, skipping AI provider configuration")
        return

    provider_name = get_provider_name(base_url)
    provider_logger = logging.getLogger(f"bootstrap.{provider_name.lower()}")

    provider_logger.info("Configuring AI provider (%s)...", provider_name)
    try:
        # 1. Configure OpenAI connection
        provider_logger.info("Updating OpenAI config at %s...", base_url)
        await client.update_openai_config(
            {
                "ENABLE_OPENAI_API": True,
                "OPENAI_API_BASE_URLS": [base_url],
                "OPENAI_API_KEYS": [api_key],
                "OPENAI_API_CONFIGS": {
                    "0": {
                        "enable": True,
                        "name": provider_name,
                        "model_ids": [model_id],
                    }
                },
            }
        )
        provider_logger.info("OpenAI config updated (restricted to %s)", model_id)

        # 2. Wait for discovery and make model public
        provider_logger.info("Waiting for model discovery...")
        found = False
        for _ in range(DISCOVERY_TIMEOUT_ATTEMPTS):
            try:
                models_data = await client.get_models()
                models = (
                    models_data if isinstance(models_data, list) else models_data.get("data", [])
                )

                matching_id = None
                for m in models:
                    mid = m["id"] if isinstance(m, dict) else m
                    if model_id in mid:
                        matching_id = mid
                        break

                if matching_id:
                    await client.update_model_access(
                        matching_id,
                        [
                            {
                                "principal_type": "user",
                                "principal_id": "*",
                                "permission": "read",
                            }
                        ],
                    )
                    provider_logger.info("Model %s is now public", matching_id)
                    found = True
                    break
            except Exception as e:
                provider_logger.debug("Discovery attempt failed: %s", e)
            await asyncio.sleep(DISCOVERY_POLL_INTERVAL)

        if not found:
            provider_logger.warning(
                "AI provider model %s not discovered yet, skipping public access",
                model_id,
            )

        provider_logger.info("%s API configuration finished", provider_name)
    except RuntimeError as e:
        provider_logger.error("Failed to configure %s: %s", provider_name, e)

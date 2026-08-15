"""
Bootstrap an Open WebUI test environment for manual testing.

This package provides a modularized workflow to:
1. Ensure the Docker engine is running.
2. Launch the Open WebUI container via Docker Compose.
3. Setup Admin and Test users.
4. Integrate a generic OpenAI-compatible AI provider.
5. Build and install all plugins via their individual install.py scripts.

Usage:
    Ensure you have a `.env` file configured (see `.env.example` in the root), then run:
    uv run python -m scripts.bootstrap_test_env
"""

from .main import bootstrap as bootstrap

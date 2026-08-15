"""
title: Update Check Mixin
author: @philipp
version: 0.1.0
description: A mixin to check for plugin updates and notify the administrator or users.
license: MIT
"""

import logging
import re
import time
from typing import Any, Awaitable, Callable, Optional

import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ========================================================================
# UPDATE CHECK MIXIN
# ========================================================================


class UpdateMixin:
    """Mixin for background checking of new releases on GitHub."""

    _GITHUB_RELEASES_URL: str = "https://api.github.com/repos/toolfab-ai/owui-plugins/releases"
    _CACHE_EXPIRY_SECONDS: float = 3600.0  # Cache GitHub API responses for 1 hour

    def _get_current_version(self) -> str:
        """Retrieve the plugin version from the module docstring."""
        doc = globals().get("__doc__")
        if doc:
            match = re.search(r"version:\s*([^\n\r]+)", doc)
            if match:
                return match.group(1).strip()
        return "0.1.0"

    def _is_preview_version(self, v_str: str) -> bool:
        """Check if a version string represents a preview version (contains a hyphen)."""
        return "-" in v_str

    def _parse_version(
        self, v_str: str, is_preview: Optional[bool] = None
    ) -> tuple[int, int, int, int]:
        """Parse version string into a 4-tuple of integers for semver comparison.

        The 4th element represents pre-release status:
        - 1 for stable releases (higher priority)
        - 0 for pre-releases/dev versions
        """
        try:
            if is_preview is None:
                is_preview = self._is_preview_version(v_str)
            # Strip any leading 'v'
            v_str = v_str.lstrip("v")
            # Extract the numeric parts (first 3 numbers)
            match = re.match(r"^(\d+)\.(\d+)\.(\d+)", v_str)
            if match:
                major, minor, patch = map(int, match.groups())
                pre_release_weight = 0 if is_preview else 1
                return (major, minor, patch, pre_release_weight)
            return (0, 0, 0, 0)
        except Exception as e:
            logger.warning("Failed to parse version string %s: %s", v_str, e)
            return (0, 0, 0, 0)

    async def _check_for_updates(
        self,
        __user__: Optional[dict[str, Any]],
        emitter: Optional[Callable[[dict[str, Any]], Awaitable[None]]],
    ) -> None:
        """Check for updates in the background and notify via event emitter."""
        if not emitter:
            logger.debug("No event emitter provided; skipping update check.")
            return

        if not __user__:
            logger.debug("No user context provided; skipping update check.")
            return

        if hasattr(self, "valves") and not getattr(
            self.valves, "ENABLE_UPDATE_NOTIFICATIONS", True
        ):
            logger.debug("Update notifications disabled by admin config.")
            return

        # Lazy initialization of state to play nicely with Mixin inheritance
        if not hasattr(self, "_releases_cache"):
            self._releases_cache = None
        if not hasattr(self, "_last_update_check_time"):
            self._last_update_check_time = 0.0
        if not hasattr(self, "_seen_notifications"):
            self._seen_notifications = set()

        user_id = __user__.get("id", "anonymous")
        role = __user__.get("role", "user")

        releases = self._releases_cache
        now = time.time()

        # Check if cache expired or not checked yet
        if not releases or (now - self._last_update_check_time > self._CACHE_EXPIRY_SECONDS):
            logger.debug("Querying GitHub Releases API for updates...")
            headers = {
                "User-Agent": "OpenWebUI-Plugin-Update-Checker",
                "Accept": "application/vnd.github+json",
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(self._GITHUB_RELEASES_URL, headers=headers)
                    response.raise_for_status()
                    releases = response.json()

                    if isinstance(releases, list):
                        self._releases_cache = releases
                        self._last_update_check_time = now
            except httpx.HTTPError as e:
                logger.warning("HTTP error checking for updates: %s", e)
            except Exception as e:
                logger.exception("Unexpected error checking for updates: %s", e)

        # If we failed to get releases, return
        if not isinstance(releases, list):
            return

        check_previews = hasattr(self, "valves") and getattr(
            self.valves, "CHECK_PREVIEW_RELEASES", False
        )

        current_version_str = self._get_current_version()
        current_is_preview = self._is_preview_version(current_version_str)
        current_version = self._parse_version(current_version_str, is_preview=current_is_preview)

        latest_eligible_version_str: Optional[str] = None
        latest_eligible_is_preview: bool = False

        for release in releases:
            tag_name = release.get("tag_name")
            if not tag_name:
                continue

            # Match iterative-research/vX.Y.Z...
            match = re.match(r"^iterative-research/v?(\d+\.\d+\.\d+.*)", tag_name)
            if not match:
                continue

            candidate_version_str = match.group(1)
            # Use GitHub's official "prerelease" label to differentiate stable vs unstable
            is_preview = release.get("prerelease", False)

            # If it's a preview release but checking previews is disabled, skip it
            if is_preview and not check_previews:
                continue

            # Standard users must never get notified of preview versions
            if is_preview and role != "admin":
                continue

            # This is the first/newest eligible version in the sorted list of releases
            latest_eligible_version_str = candidate_version_str
            latest_eligible_is_preview = is_preview
            break

        if not latest_eligible_version_str:
            return

        latest_eligible_version = self._parse_version(
            latest_eligible_version_str, is_preview=latest_eligible_is_preview
        )

        # Compare version and check if this user has already seen this specific notification
        if latest_eligible_version > current_version:
            if (user_id, latest_eligible_version_str) not in self._seen_notifications:
                # Prepare message depending on user role and version type
                if latest_eligible_is_preview:
                    content = (
                        f"A new preview version of Iterative Deep Research Agent ({latest_eligible_version_str}) "
                        "is available on GitHub! Please update."
                    )
                elif role == "admin":
                    content = (
                        f"A new version of Iterative Deep Research Agent ({latest_eligible_version_str}) "
                        "is available on GitHub! Please update."
                    )
                else:
                    content = (
                        f"A new version of Iterative Deep Research Agent ({latest_eligible_version_str}) "
                        "is available. Contact your administrator to get it."
                    )

                logger.info(
                    "Notifying user %s (role: %s) of new release %s",
                    user_id,
                    role,
                    latest_eligible_version_str,
                )
                await emitter(
                    {
                        "type": "notification",
                        "data": {
                            "type": "info",
                            "content": content,
                        },
                    }
                )
                # Mark as seen for this user & version
                self._seen_notifications.add((user_id, latest_eligible_version_str))

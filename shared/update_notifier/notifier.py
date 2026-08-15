from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_REPO: str = "toolfab-ai/owui-plugins"
RELEASE_TAG_PREFIX: str = ""
CACHE_EXPIRY_SECONDS: float = 3600.0  # Cache GitHub API responses for 1 hour

ADMIN_UPDATE_MSG: str = (
    "**New version available**: [{plugin_name} {version}]({url}) "
    "Update the plugin for the latest fixes."
)
USER_UPDATE_MSG: str = (
    "**New version available**: {plugin_name}. Contact your administrator to update the plugin."
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ========================================================================
# SHARED UPDATE NOTIFIER MIXIN
# ========================================================================


class UpdateMixin:
    """Mixin for background checking of new releases on GitHub."""

    _GITHUB_REPO: str = GITHUB_REPO
    _RELEASE_TAG_PREFIX: str = RELEASE_TAG_PREFIX
    _CACHE_EXPIRY_SECONDS: float = CACHE_EXPIRY_SECONDS
    _ADMIN_UPDATE_MSG: str = ADMIN_UPDATE_MSG
    _USER_UPDATE_MSG: str = USER_UPDATE_MSG

    def _get_metadata_field(self, field: str) -> Optional[str]:
        """Retrieve a specific field from the module docstring metadata."""
        import inspect
        import sys

        # Try to find the module by its name in sys.modules
        mod_name = self.__class__.__module__
        mod = sys.modules.get(mod_name)
        doc = getattr(mod, "__doc__", None) if mod else None

        if not doc:
            # Fallback: search sys.modules by filename
            try:
                mod_file = inspect.getfile(self.__class__)
                for m in sys.modules.values():
                    if getattr(m, "__file__", None) == mod_file:
                        doc = getattr(m, "__doc__", None)
                        if doc:
                            break
            except Exception:
                pass

        if not doc:
            # Final fallback to globals (works if inlined)
            doc = globals().get("__doc__")

        if doc:
            match = re.search(rf"{field}:\s*([^\n\r]+)", doc)
            if match:
                return match.group(1).strip()
        return None

    def _get_current_version(self) -> str:
        """Retrieve the plugin version from the module docstring."""
        return self._get_metadata_field("version") or "0.1.0"

    def _get_plugin_name(self) -> str:
        """Retrieve the plugin title from the module docstring."""
        return self._get_metadata_field("title") or "Plugin"

    def _parse_version(self, v_str: str) -> tuple[int, int, int, int, int]:
        """Parse version string into a 5-tuple for semver comparison.

        Tuple format: (major, minor, patch, type_weight, pre_release_version)
        Weights: dev=0, alpha=1, beta=2, rc=3, stable=4
        """
        try:
            # Strip any leading 'v'
            v_str = v_str.lstrip("v").lower()

            # Base version (major.minor.patch)
            base_match = re.match(r"^(\d+)\.(\d+)\.(\d+)", v_str)
            if not base_match:
                return (0, 0, 0, 0, 0)

            major, minor, patch = map(int, base_match.groups())

            # Determine type weight and pre-release number
            type_weight = 4  # Default to stable
            pre_num = 0

            if "-" in v_str:
                suffix = v_str.split("-", 1)[1]
                if "dev" in suffix:
                    type_weight = 0
                elif "alpha" in suffix:
                    type_weight = 1
                elif "beta" in suffix:
                    type_weight = 2
                elif "rc" in suffix:
                    type_weight = 3

                # Extract number from suffix (e.g., beta.1 -> 1)
                num_match = re.search(r"(\d+)", suffix)
                if num_match:
                    pre_num = int(num_match.group(1))

            return (major, minor, patch, type_weight, pre_num)
        except Exception as e:
            logger.warning("Failed to parse version string %s: %s", v_str, e)
            return (0, 0, 0, 0, 0)

    async def _get_update_notification(
        self,
        __user__: Optional[dict[str, Any]],
    ) -> Optional[str]:
        """Check for updates and return a formatted Markdown notification if available."""
        if not __user__:
            return None

        # Check if notifications are disabled via valves
        if hasattr(self, "valves") and not getattr(
            self.valves, "ENABLE_UPDATE_NOTIFICATIONS", True
        ):
            return None

        # Lazy initialization of state on the instance
        if not hasattr(self, "_releases_cache"):
            self._releases_cache = None
        if not hasattr(self, "_last_update_check_time"):
            self._last_update_check_time = 0.0

        role = __user__.get("role", "user")
        releases = self._releases_cache
        now = time.time()

        # Check if cache expired or not checked yet
        if not releases or (now - self._last_update_check_time > self._CACHE_EXPIRY_SECONDS):
            url = f"https://api.github.com/repos/{self._GITHUB_REPO}/releases"
            logger.debug("Querying GitHub Releases API for updates: %s", url)
            headers = {
                "User-Agent": "OpenWebUI-Plugin-Update-Checker",
                "Accept": "application/vnd.github+json",
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    releases = response.json()

                    if isinstance(releases, list):
                        self._releases_cache = releases
                        self._last_update_check_time = now
            except Exception as e:
                logger.warning("Failed to check for updates: %s", e)

        if not isinstance(releases, list):
            return None

        check_previews = hasattr(self, "valves") and getattr(
            self.valves, "CHECK_PREVIEW_RELEASES", False
        )

        current_version_str = self._get_current_version()
        current_version = self._parse_version(current_version_str)
        plugin_name = self._get_plugin_name()

        latest_release = None
        latest_version = (0, 0, 0, 0, 0)

        for release in releases:
            tag_name = release.get("tag_name", "")
            if not tag_name:
                continue

            # Check if tag matches our prefix
            if self._RELEASE_TAG_PREFIX and not tag_name.startswith(self._RELEASE_TAG_PREFIX):
                continue

            # Extract version string
            candidate_version_str = tag_name[len(self._RELEASE_TAG_PREFIX) :]
            is_preview = release.get("prerelease", False)

            if is_preview and not check_previews and role != "admin":
                continue

            candidate_version = self._parse_version(candidate_version_str)
            if candidate_version > latest_version:
                latest_version = candidate_version
                latest_release = release

        if not latest_release:
            return None

        latest_tag = latest_release.get("tag_name", "")
        # Extract version part from tag for display (strip prefix)
        display_version = latest_tag[len(self._RELEASE_TAG_PREFIX) :]
        html_url = latest_release.get("html_url", "")

        if latest_version > current_version:
            if role == "admin":
                return self._ADMIN_UPDATE_MSG.format(
                    plugin_name=plugin_name, version=display_version, url=html_url
                )
            else:
                return self._USER_UPDATE_MSG.format(
                    plugin_name=plugin_name, version=display_version
                )

        return None

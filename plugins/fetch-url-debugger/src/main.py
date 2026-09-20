from __future__ import annotations

import asyncio
import inspect
import logging
import socket
import sys
import time
import traceback
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlparse

from ._updates import Updates
from ._valves import Valves

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ========================================================================
# FILTER CLASS
# ========================================================================


class Filter(Updates):
    """
    Fetch URL Debugger — A Filter plugin that monkey-patches the native
    Open WebUI fetch_url tool to provide deep internal logging.
    """

    def __init__(self) -> None:
        self.valves = Valves()
        self._patched: bool = False

    def _log_to_stderr(self, message: str) -> None:
        """Helper to log big blocky messages to stderr."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        sys.stderr.write(f"\n{'=' * 80}\n")
        sys.stderr.write(f"FETCH URL DEBUGGER [{timestamp}]\n")
        sys.stderr.write(f"{'-' * 80}\n")
        sys.stderr.write(f"{message}\n")
        sys.stderr.write(f"{'=' * 80}\n\n")
        sys.stderr.flush()

    def _get_error_category(self, exc: Exception) -> str:
        """Categorize the exception into a readable string."""
        exc_str = str(exc).lower()
        if "timeout" in exc_str or "timed out" in exc_str:
            return "TIMEOUT"
        if "ssl" in exc_str or "certificate" in exc_str:
            return "SSL_ERROR"
        if "connection" in exc_str or "refused" in exc_str:
            return "CONNECTION_ERROR"
        if "name or service not known" in exc_str or "gaierror" in exc_str:
            return "DNS_ERROR"
        return "UNKNOWN_ERROR"

    def _dns_precheck(self, url: str) -> str:
        """Perform a DNS resolution check for the hostname."""
        try:
            hostname = urlparse(url).hostname
            if not hostname:
                return "DNS Check: No hostname found in URL"

            start_dns = time.perf_counter()
            addr_info = socket.getaddrinfo(hostname, None)
            duration = (time.perf_counter() - start_dns) * 1000
            ips = list(set(item[4][0] for item in addr_info))
            return f"DNS Check: Resolved {hostname} to {ips} in {duration:.2f}ms"
        except Exception as dns_exc:
            return f"DNS Check: Failed for {hostname if 'hostname' in locals() else url} - {str(dns_exc)}"

    async def inlet(
        self,
        body: Dict[str, Any],
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Inlet hook to perform the monkey-patching of fetch_url.
        """
        if __event_emitter__:
            update_msg = await self._get_update_notification(__user__)
            if update_msg:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": update_msg, "done": True},
                    }
                )

        if not self.valves.ENABLED:
            return body

        if self._patched:
            return body

        # Use a class-level or module-level flag to ensure absolute single patching
        # across instances if necessary, but instance-level is usually enough for a singleton Filter.
        # However, to be safe against multiple Filter instances:
        if getattr(Filter, "_global_patched", False):
            self._patched = True
            return body

        try:
            # Attempt to import the builtin tools module
            builtin_tools = None
            for import_path in [
                "open_webui.tools.builtin",
                "open_webui.apps.webui.tools.builtin",
            ]:
                try:
                    builtin_tools = __import__(import_path, fromlist=["fetch_url"])
                    if hasattr(builtin_tools, "fetch_url"):
                        logger.info(f"Found fetch_url at {import_path}")
                        break
                except ImportError:
                    continue

            if not builtin_tools or not hasattr(builtin_tools, "fetch_url"):
                self._log_to_stderr(
                    "WARNING: Could not find open_webui.tools.builtin.fetch_url. "
                    "This plugin might not be compatible with your Open WebUI version."
                )
                return body

            original_fetch_url = builtin_tools.fetch_url

            # Defensive check: if it's already a wrapped function from us, skip
            if getattr(original_fetch_url, "__is_fetch_url_debugger__", False):
                self._patched = True
                Filter._global_patched = True
                return body

            # Define the wrapper logic
            def get_wrapped_logic(is_async: bool) -> Any:
                if is_async:

                    async def wrapped_fetch_url(*args: Any, **kwargs: Any) -> Any:
                        url = args[0] if args else kwargs.get("url", "UNKNOWN")
                        __event_emitter__ = kwargs.get("__event_emitter__")

                        dns_info = self._dns_precheck(url)
                        self._log_to_stderr(
                            f"REQUEST INITIATED (ASYNC)\nURL: {url}\n{dns_info}\nArgs: {args}\nKwargs: {kwargs}"
                        )
                        if __event_emitter__:
                            await __event_emitter__(
                                {
                                    "type": "status",
                                    "data": {"description": f"DEBUG: {dns_info}", "done": False},
                                }
                            )
                            await __event_emitter__(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": "DEBUG: Calling native fetch_url...",
                                        "done": False,
                                    },
                                }
                            )

                        try:
                            start_req = time.perf_counter()
                            result = await original_fetch_url(*args, **kwargs)
                            duration = (time.perf_counter() - start_req) * 1000
                            self._log_to_stderr(
                                f"REQUEST SUCCESSFUL\nURL: {url}\nDuration: {duration:.2f}ms"
                            )
                            return result
                        except Exception as e:
                            category = self._get_error_category(e)
                            stack = traceback.format_exc()
                            self._log_to_stderr(
                                f"REQUEST FAILED\nCATEGORY: {category}\nURL: {url}\nERROR: {str(e)}\n\nTRACEBACK:\n{stack}"
                            )
                            if __event_emitter__:
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": f"DEBUG: fetch_url failed ({category}): {str(e)}",
                                            "done": False,
                                        },
                                    }
                                )
                            raise e

                    return wrapped_fetch_url
                else:

                    def wrapped_fetch_url(*args: Any, **kwargs: Any) -> Any:
                        url = args[0] if args else kwargs.get("url", "UNKNOWN")
                        __event_emitter__ = kwargs.get("__event_emitter__")

                        dns_info = self._dns_precheck(url)
                        self._log_to_stderr(
                            f"REQUEST INITIATED (SYNC)\nURL: {url}\n{dns_info}\nArgs: {args}\nKwargs: {kwargs}"
                        )
                        if __event_emitter__:
                            # We can't await here in sync, but we might be able to try to call it if it's not a coroutine
                            # However, Open WebUI event_emitters are usually async.
                            # For sync tools, we might be limited, but let's try a safe approach.
                            if inspect.iscoroutinefunction(__event_emitter__):
                                try:
                                    # This is risky in sync code but common in some OWUI environments
                                    loop = asyncio.get_event_loop()
                                    if loop.is_running():
                                        loop.create_task(
                                            __event_emitter__(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": f"DEBUG: {dns_info}",
                                                        "done": False,
                                                    },
                                                }
                                            )
                                        )
                                    else:
                                        loop.run_until_complete(
                                            __event_emitter__(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": f"DEBUG: {dns_info}",
                                                        "done": False,
                                                    },
                                                }
                                            )
                                        )
                                except Exception:
                                    pass
                            else:
                                try:
                                    __event_emitter__(
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": f"DEBUG: {dns_info}",
                                                "done": False,
                                            },
                                        }
                                    )
                                except Exception:
                                    pass

                        try:
                            start_req = time.perf_counter()
                            result = original_fetch_url(*args, **kwargs)
                            duration = (time.perf_counter() - start_req) * 1000
                            self._log_to_stderr(
                                f"REQUEST SUCCESSFUL\nURL: {url}\nDuration: {duration:.2f}ms"
                            )
                            return result
                        except Exception as e:
                            category = self._get_error_category(e)
                            stack = traceback.format_exc()
                            self._log_to_stderr(
                                f"REQUEST FAILED\nCATEGORY: {category}\nURL: {url}\nERROR: {str(e)}\n\nTRACEBACK:\n{stack}"
                            )
                            raise e

                    return wrapped_fetch_url

            is_async = inspect.iscoroutinefunction(original_fetch_url)
            wrapped = get_wrapped_logic(is_async)
            wrapped.__is_fetch_url_debugger__ = True

            # Apply the patch
            builtin_tools.fetch_url = wrapped

            self._patched = True
            Filter._global_patched = True

            logger.info(
                "Fetch URL Debugger: Successfully patched open_webui.tools.builtin.fetch_url"
            )
            self._log_to_stderr(
                "SUCCESS: open_webui.tools.builtin.fetch_url has been monkey-patched."
            )

        except Exception as e:
            self._log_to_stderr(
                f"ERROR: Unexpected error during patching: {str(e)}\n{traceback.format_exc()}"
            )

        return body

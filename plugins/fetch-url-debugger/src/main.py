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

    _global_patched: bool = False

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
        # Heartbeat to UI to confirm filter is running
        if __event_emitter__:
            try:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "DEBUG: Fetch URL Debugger active - monitoring tool calls...",
                            "done": False,
                        },
                    }
                )
            except Exception:
                pass

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

        if Filter._global_patched:
            self._patched = True
            return body

        self._log_to_stderr("STARTING AGGRESSIVE PATCHING OF fetch_url...")

        try:
            # 1. Targeted Patching of Known Modules
            for import_path in [
                "open_webui.tools.builtin",
                "open_webui.apps.webui.tools.builtin",
            ]:
                try:
                    # Clear from sys.modules to ensure we get a fresh reference if it was partially loaded
                    mod = __import__(import_path, fromlist=["fetch_url"])
                    if hasattr(mod, "fetch_url"):
                        self._apply_patch(mod, "fetch_url")
                        self._log_to_stderr(f"Successfully patched {import_path}.fetch_url")
                except ImportError:
                    continue
                except Exception as e:
                    self._log_to_stderr(f"Failed to patch {import_path}: {e}")

            # 2. Aggressive Global Search in sys.modules
            # This handles cases where tools did 'from open_webui.tools.builtin import fetch_url'
            # We look for ANY module that has a 'fetch_url' attribute.
            modules_to_patch = []
            for name, mod in list(sys.modules.items()):
                if not mod:
                    continue
                if hasattr(mod, "fetch_url"):
                    attr = getattr(mod, "fetch_url")
                    # Check if it looks like the function we want to patch
                    if (
                        callable(attr)
                        and hasattr(attr, "__name__")
                        and attr.__name__ == "fetch_url"
                    ):
                        modules_to_patch.append((name, mod))

            for name, mod in modules_to_patch:
                try:
                    self._apply_patch(mod, "fetch_url")
                    self._log_to_stderr(f"Aggressively patched {name}.fetch_url")
                except Exception as e:
                    logger.debug(f"Failed aggressive patch on {name}: {e}")

            self._patched = True
            Filter._global_patched = True
            self._log_to_stderr("COMPLETED AGGRESSIVE PATCHING.")

        except Exception as e:
            self._log_to_stderr(
                f"ERROR: Unexpected error during aggressive patching: {str(e)}\n{traceback.format_exc()}"
            )

        return body

    def _apply_patch(self, module: Any, attr_name: str) -> None:
        """Helper to apply the wrapper to a specific module attribute."""
        original = getattr(module, attr_name)

        # Skip if already patched
        if getattr(original, "__is_fetch_url_debugger__", False):
            return

        is_async = inspect.iscoroutinefunction(original)
        wrapped = self._get_wrapper(original, is_async)
        wrapped.__is_fetch_url_debugger__ = True
        setattr(module, attr_name, wrapped)

    def _get_wrapper(self, original: Callable, is_async: bool) -> Callable:
        """Create the wrapper function."""
        if is_async:

            async def wrapped_fetch_url(*args: Any, **kwargs: Any) -> Any:
                url = args[0] if args else kwargs.get("url", "UNKNOWN")
                __event_emitter__ = kwargs.get("__event_emitter__")

                dns_info = self._dns_precheck(url)
                self._log_to_stderr(
                    f"REQUEST INITIATED (ASYNC)\nURL: {url}\n{dns_info}\nArgs: {args}\nKwargs: {kwargs}"
                )
                if __event_emitter__:
                    try:
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
                                    "description": f"DEBUG: Calling native fetch_url for {url}...",
                                    "done": False,
                                },
                            }
                        )
                    except Exception:
                        pass

                try:
                    start_req = time.perf_counter()
                    result = await original(*args, **kwargs)
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
                        try:
                            await __event_emitter__(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": f"DEBUG: fetch_url failed ({category}): {str(e)}",
                                        "done": False,
                                    },
                                }
                            )
                        except Exception:
                            pass
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
                    msg = {
                        "type": "status",
                        "data": {"description": f"DEBUG: {dns_info}", "done": False},
                    }
                    if inspect.iscoroutinefunction(__event_emitter__):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                loop.create_task(__event_emitter__(msg))
                            else:
                                loop.run_until_complete(__event_emitter__(msg))
                        except Exception:
                            pass
                    else:
                        try:
                            __event_emitter__(msg)
                        except Exception:
                            pass

                try:
                    start_req = time.perf_counter()
                    result = original(*args, **kwargs)
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

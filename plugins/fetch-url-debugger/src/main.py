from __future__ import annotations

import inspect
import logging
import socket
import sys
import time
import traceback
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ._valves import Valves

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ========================================================================
# FILTER CLASS
# ========================================================================


class Filter:
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
    ) -> Dict[str, Any]:
        """
        Inlet hook to perform the monkey-patching of fetch_url.
        """
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
            try:
                import open_webui.tools.builtin as builtin_tools
            except ImportError:
                # Fallback or check if it's under a different path in some versions
                self._log_to_stderr(
                    "WARNING: Could not import open_webui.tools.builtin. "
                    "This plugin might not be compatible with your Open WebUI version."
                )
                return body

            if not hasattr(builtin_tools, "fetch_url"):
                self._log_to_stderr("WARNING: fetch_url not found in open_webui.tools.builtin.")
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
                        dns_info = self._dns_precheck(url)
                        self._log_to_stderr(
                            f"REQUEST INITIATED (ASYNC)\nURL: {url}\n{dns_info}\nArgs: {args}\nKwargs: {kwargs}"
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
                            raise e

                    return wrapped_fetch_url
                else:

                    def wrapped_fetch_url(*args: Any, **kwargs: Any) -> Any:
                        url = args[0] if args else kwargs.get("url", "UNKNOWN")
                        dns_info = self._dns_precheck(url)
                        self._log_to_stderr(
                            f"REQUEST INITIATED (SYNC)\nURL: {url}\n{dns_info}\nArgs: {args}\nKwargs: {kwargs}"
                        )
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

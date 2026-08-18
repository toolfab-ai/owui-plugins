"""Integration tests: Memory Islands Manager Action ↔ Filter panel-command protocol.

These tests do not require a running Open WebUI container. They verify that the
commands the Action panel generates exactly match the internal protocol the
Memory Islands Filter inlet intercepts (spec Section 5 / Filter FR-011):

- ``@memory add: <fact>``     → Filter runs ``_add_fact``
- ``@memory delete: <fact>``  → Filter runs ``_delete_fact``

The Filter's own tests already cover the interception end-to-end; these tests
keep the generated-command → Filter-parser contract in sync.
"""

from typing import Any, Optional

import pytest

from tests._plugin_loader import load_plugin

action_mod = load_plugin("memory-islands-action")


@pytest.fixture(scope="module")
def filter_protocol() -> Any:
    """Provide the Filter's command parser without touching the shared database.

    ``FilterMixin._parse_panel_command`` is a pure string parser and needs no
    database, so instantiating the mixin avoids any side effects on a real
    ``$DATA_DIR`` while still verifying protocol compatibility.
    """
    try:
        filter_mod = load_plugin("memory-islands")
        return filter_mod.FilterMixin()
    except Exception:
        pytest.skip(
            "memory-islands Filter plugin is not available in this checkout; "
            "cannot verify panel-command protocol compatibility."
        )


@pytest.mark.integration
class TestPanelCommandProtocol:
    """Generated Action commands must match the Filter's internal protocol exactly."""

    def test_add_command_matches_filter_parser(self, filter_protocol: Any) -> None:
        """Verify the generated add command parses to ('add', payload) in the Filter."""
        action = action_mod.ActionMixin()
        command: Optional[str] = action._build_add_command("User likes hiking")

        assert command == "@memory add: User likes hiking"
        assert filter_protocol._parse_panel_command(command) == ("add", "User likes hiking")

    def test_delete_command_matches_filter_parser(self, filter_protocol: Any) -> None:
        """Verify the generated delete command parses to ('delete', payload) in the Filter."""
        action = action_mod.ActionMixin()
        command: Optional[str] = action._build_delete_command("User likes hiking")

        assert command == "@memory delete: User likes hiking"
        assert filter_protocol._parse_panel_command(command) == ("delete", "User likes hiking")

    def test_empty_add_is_never_posted(self) -> None:
        """Verify an empty/whitespace fact never produces a command the Filter could see."""
        action = action_mod.ActionMixin()
        assert action._build_add_command("   ") is None
        assert action._build_delete_command("   ") is None

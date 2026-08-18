from __future__ import annotations

from typing import Any, Dict, Optional

from ._action import ActionMixin
from ._database import DatabaseMixin
from ._updates import UpdateMixin
from ._valves import Valves


class Action(ActionMixin, DatabaseMixin, UpdateMixin):
    """Action — Memory Islands Manager: Rich UI panel to view/add/delete folder facts."""

    Valves = Valves

    def __init__(self) -> None:
        self.valves: Valves = self.Valves()
        self._init_databases()

    async def action(
        self,
        body: Dict[str, Any],
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Any = None,
        __event_call__: Any = None,
        __request__: Any = None,
        __metadata__: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Message-toolbar entry point; implementation lives in ``ActionMixin.action``."""
        return await super().action(
            body,
            __user__=__user__,
            __event_emitter__=__event_emitter__,
            __event_call__=__event_call__,
            __request__=__request__,
            __metadata__=__metadata__,
        )

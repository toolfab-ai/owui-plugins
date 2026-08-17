from __future__ import annotations

from ._commands import CommandsMixin
from ._database import DatabaseMixin
from ._filters import FilterMixin
from ._updates import UpdateMixin
from ._valves import Valves


class Filter(FilterMixin, CommandsMixin, DatabaseMixin, UpdateMixin):
    """Filter — Implements Memory Islands folder-scoped context isolation."""

    Valves = Valves

    def __init__(self) -> None:
        FilterMixin.__init__(self)
        self.valves: Valves = self.Valves()
        self._init_databases()

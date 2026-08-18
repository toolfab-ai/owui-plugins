from __future__ import annotations

import logging

from shared.update_notifier.notifier import UpdateMixin

logger = logging.getLogger(__name__)


class UpdateMixin(UpdateMixin):
    """Mixin for background checking of new releases on GitHub."""

    _RELEASE_TAG_PREFIX: str = "memory-islands/"

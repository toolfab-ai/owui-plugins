from __future__ import annotations

import logging

from shared.update_notifier.notifier import UpdateMixin

logger = logging.getLogger(__name__)


class UpdateMixin(UpdateMixin):
    """Mixin for background checking of new releases on GitHub.

    Uses the ``memory-islands-action/`` release tag prefix so the Manager
    Action only sees its own releases (the Filter uses ``memory-islands/``).
    """

    _RELEASE_TAG_PREFIX: str = "memory-islands-action/"

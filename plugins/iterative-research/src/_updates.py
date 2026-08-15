from __future__ import annotations

import logging

from shared.update_notifier.notifier import UpdateMixin

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ========================================================================
# UPDATE CHECK MIXIN
# ========================================================================


class UpdateMixin(UpdateMixin):
    """Mixin for background checking of new releases on GitHub."""

    _RELEASE_TAG_PREFIX: str = "iterative-research/"

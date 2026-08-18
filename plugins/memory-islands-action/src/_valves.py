from __future__ import annotations

from pydantic import BaseModel, Field


class Valves(BaseModel):
    """Admin-configurable settings for the Memory Islands Manager Action."""

    ENABLE_UPDATE_NOTIFICATIONS: bool = Field(
        default=True, description="Enable background checking for plugin updates."
    )
    CHECK_PREVIEW_RELEASES: bool = Field(
        default=False, description="Whether to include pre-releases in update checks."
    )

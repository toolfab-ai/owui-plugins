from __future__ import annotations

from pydantic import BaseModel, Field


class Valves(BaseModel):
    """Admin-configurable settings for Memory Islands."""

    ISOLATE_BY_DEFAULT: bool = Field(
        default=True, description="Enable strict isolation for all folders."
    )
    AUTO_LEARN_MEMORIES: bool = Field(
        default=True, description="Automatically extract and save new memories from chats."
    )
    ENABLE_UPDATE_NOTIFICATIONS: bool = Field(
        default=True, description="Enable background checking for plugin updates."
    )
    CHECK_PREVIEW_RELEASES: bool = Field(
        default=False, description="Whether to include pre-releases in update checks."
    )

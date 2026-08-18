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
    EXTRACTION_MODEL: str = Field(
        default="",
        description="Model id used for background fact extraction. Leave empty to reuse the chat's model.",
    )
    EXTRACTION_INTERVAL: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Analyze the chat for new facts every N exchanges.",
    )
    ENABLE_UPDATE_NOTIFICATIONS: bool = Field(
        default=True, description="Enable background checking for plugin updates."
    )
    CHECK_PREVIEW_RELEASES: bool = Field(
        default=False, description="Whether to include pre-releases in update checks."
    )

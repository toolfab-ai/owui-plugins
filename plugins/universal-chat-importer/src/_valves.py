from __future__ import annotations

from pydantic import BaseModel, Field


class Valves(BaseModel):
    """Admin-configurable settings for the Universal Chat Importer."""

    ENABLE_UPDATE_NOTIFICATIONS: bool = Field(
        default=True,
        description="If enabled, the plugin will check GitHub in the background for new releases and notify the admin.",
    )
    CHECK_PREVIEW_RELEASES: bool = Field(
        default=False,
        description="If enabled, check for preview/dev/pre-release versions on GitHub as well.",
    )
    DEFAULT_MODEL: str = Field(
        default="gpt-4o",
        description="The model name to assign to imported chats if not specified.",
    )

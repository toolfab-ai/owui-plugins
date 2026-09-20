from __future__ import annotations

from pydantic import BaseModel, Field


class Valves(BaseModel):
    """Admin-configurable settings for the Universal Chat Importer."""

    DEFAULT_MODEL: str = Field(
        default="gpt-4o",
        description="The model name to assign to imported chats if not specified.",
    )

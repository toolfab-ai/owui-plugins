from pydantic import BaseModel, Field


class Valves(BaseModel):
    """Admin-configurable settings for the Iterative Research Pipe."""

    ENABLE_UPDATE_NOTIFICATIONS: bool = Field(
        default=True,
        description="If enabled, the plugin will check GitHub in the background for new releases and notify the admin.",
    )
    CHECK_PREVIEW_RELEASES: bool = Field(
        default=False,
        description="If enabled, check for preview/dev/pre-release versions on GitHub as well.",
    )
    SEARXNG_URL: str = Field(
        default="",
        description="The base URL of your SearXNG instance (e.g., http://searxng:8080). "
        "Used as a search engine for discovering new information.",
    )
    TAVILY_API_KEY: str = Field(
        default="",
        description="API key for Tavily Search (https://tavily.com). "
        "If provided, Tavily will be used as the primary or fallback search engine.",
    )
    MODEL: str = Field(
        default="",
        description="The internal LLM model ID to use for research planning, gap analysis, "
        "and final synthesis. If left empty, the plugin will attempt to auto-detect "
        "an available model from the workspace.",
    )
    MAX_STEPS: int = Field(
        default=3,
        description="Maximum number of iterative search-and-scraping loops to perform. "
        "Higher values lead to deeper research but take more time.",
        ge=1,
        le=10,
    )
    MAX_PAGES_TO_SCRAPE: int = Field(
        default=3,
        description="Maximum number of new web pages to scrape and analyze in each research step.",
        ge=1,
        le=10,
    )
    CO_STORM_STEERING: bool = Field(
        default=False,
        description="If enabled, the agent will pause after the first research step to "
        "allow the user to provide interactive steering feedback (Co-STORM style).",
    )


class UserValves(BaseModel):
    """Per-user settings for the Iterative Research Pipe."""

    max_steps: str = Field(
        default="default",
        description="Maximum iterative search steps (e.g., 5). Variants: 1-10. Use 'default' to inherit admin setting.",
    )
    max_pages_to_scrape: str = Field(
        default="default",
        description="Max pages to scrape per iteration (e.g., 5). Variants: 1-10. Use 'default' to inherit admin setting.",
    )
    co_storm_steering: str = Field(
        default="default",
        description="Enable Co-STORM steering pause (e.g., true). Variants: true, false. Use 'default' to inherit admin setting.",
    )

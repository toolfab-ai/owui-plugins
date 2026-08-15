## Quick start

1. Configure either **Tavily API Key** or **SearXNG URL** in the plugin's Valves settings.
2. Select the **Iterative Deep Research Agent** model from your Open WebUI chat dropdown.
3. Submit a complex research prompt (e.g., "Analyze the differences between Rust and Go for building high-throughput microservices in 2026, focusing on memory overhead and developer velocity").
4. Watch the step-by-step thinking block as the agent plans searches, scrapes pages, and compiles the final report with references!

## Description

The **Iterative Deep Research Agent** is an autonomous multi-turn web search & scraping pipe plugin for Open WebUI. It executes multi-step research loops to discover, crawl, and synthesize detailed reports complete with in-text citations.

Key features include:
- **Autonomous Planning & Gap Analysis**: Formulates search plans, executes searches, identifies gaps, and iterates dynamically.
- **Parallel Web Scraping**: Safely downloads page contents in parallel with built-in SSRF protection, parses clean text, and digests it.
- **Human-in-the-Loop Steering (Co-STORM style)**: Optionally pauses after the first iteration to receive interactive steering feedback from the user.
- **Automatic Cite Generation**: Emits proper Open WebUI citation events to link seamlessly to scraped sources.
- **Background Update Notifications**: Queries GitHub API in the background to alert administrators when new releases are available.

## Problem Statement

Standard LLM interfaces rely on static knowledge and single-shot web searches. Even with search integration, they typically perform a single query, download a handful of pages, and summarize them in one go. This single-turn process lacks:
1. The ability to identify information gaps after reading search results.
2. The feedback loop to run follow-up searches for missing details.
3. Robust SSRF protection for safe and parallelized internal web scraping.
4. Interactive human steering during long-running research loops.

This results in superficial summaries and missing nuances for multi-faceted topics.

## Valves (Configuration)

- **ENABLE_UPDATE_NOTIFICATIONS** (bool, default: `True`): If enabled, the plugin will check GitHub in the background for new releases and notify the admin.
- **CHECK_PREVIEW_RELEASES** (bool, default: `False`): If enabled, checks for preview/dev/pre-release versions on GitHub as well.
- **SEARXNG_URL** (str, default: `""`): The base URL of your SearXNG instance (e.g., `http://searxng:8080`). Used as a search engine for discovering new information.
- **TAVILY_API_KEY** (str, default: `""`): API key for Tavily Search (https://tavily.com). If provided, Tavily will be used as the primary or fallback search engine.
- **MODEL** (str, default: `""`): The internal LLM model ID to use for research planning, gap analysis, and final synthesis. If left empty, the plugin will attempt to auto-detect an available model from the workspace.
- **MAX_STEPS** (int, default: `3`, min: `1`, max: `10`): Maximum number of iterative search-and-scraping loops to perform. Higher values lead to deeper research but take more time.
- **MAX_PAGES_TO_SCRAPE** (int, default: `3`, min: `1`, max: `10`): Maximum number of new web pages to scrape and analyze in each research step.
- **CO_STORM_STEERING** (bool, default: `False`): If enabled, the agent will pause after the first research step to allow the user to provide interactive steering feedback (Co-STORM style).

## Installation

- **Via GitHub (recommended)**:
  Copy the contents of `plugin.py` or import it directly inside Open WebUI Admin Settings -> Functions.
- **Via Community**:
  Download and install the plugin from the Open WebUI Community directory once published.

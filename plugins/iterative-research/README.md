## Quick start

To start using the **Iterative Deep Research** plugin in your Open WebUI workspace, follow these simple steps:

1. **Enable and Configure Web Search**: Go to Open WebUI **Admin Settings** -> **Functions** -> **Iterative Research** -> **Valves**.
   - Input your self-hosted **SearXNG URL** (e.g., `http://localhost:8080` or `http://searxng:8080`) or provide a **Tavily API Key** (https://tavily.com).
2. **Select the Model**: In your chat model dropdown, select the newly registered **Iterative Research** or **Deep Research Agent** model.
3. **Submit a Deep Research Prompt**: Enter a complex, multi-layered query that requires deep investigation. For example:
   > *"Compare recent financial earnings of Apple and Microsoft for the latest quarter in 2026, analyzing key revenue drivers and operating margins."*
4. **Monitor Live Iterative Reasoning**: Watch the real-time collapsible `<thinking>` blocks stream into the interface using the `event_emitter` protocol. You will see the planning queries, specific web links currently being crawled in parallel, and intermediate gap analyses.
5. **Human-in-the-Loop Steering (Optional)**: If `CO_STORM_STEERING` is enabled in your Valves, look for the interactive pause prompt after the first iteration. Provide steering instructions to pivot the agent’s research direction before it resumes.

---

## Description

The **Iterative Deep Research Agent** is a next-generation autonomous web search, scraping, and synthesis `Pipe` plugin designed for the Open WebUI platform. It transforms standard chat completions into a powerful, multi-step deep research process, elevating Open WebUI from a simple chat interface into a fully extensible **Agentic Workspace** (fully compliant with OWUI v0.11.0+ and Model Context Protocol standards).

Unlike standard tools, this plugin acts as a custom model endpoint that orchestrates a sophisticated search-reason-act loop using native backend completions, keeping the integration **completely paste-and-play with zero external scraping dependencies**.

### Key Features
- **Autonomous Multi-Turn Gap Analysis**: The agent doesn't just search once. It plans searches, executes queries, digests full web page contents, evaluates gathered context, identifies remaining informational gaps, and performs follow-up searches dynamically.
- **High-Fidelity Transparency via `event_emitter`**: Eliminates the typical "black box" search experience. It streams real-time collapsible `<thinking>` blocks containing current search plans, links being scraped, and intermediate reasoning.
- **Zero-External-Dependency Parallel Scraping**: Features a robust, async web scraper using standard libraries (`httpx` and `beautifulsoup4`) that fetches multiple pages concurrently (via `asyncio.gather`). It avoids expensive paid crawl/reader APIs.
- **SSRF and Rate-Limit Protection**: Implements strict security validations to prevent Server-Side Request Forgery (SSRF) against private subnets and enforces a rigid `5.0-second` scrape timeout to ensure maximum performance.
- **Human-in-the-Loop Co-STORM Steering**: Offers optional interactive steering. When enabled, the research loop pauses after the first step to prompt the user for direction, adjusting its investigative focus dynamically.
- **Clean Chat History & Database Integration**: Keeps database history clean by hiding messy crawling steps, raw snippets, and logs from the persistent chat history. Only the beautifully synthesized Markdown report with fully linked in-text citations is saved.
- **Automated Update Notifications**: Periodically checks the upstream GitHub repository in the background to alert system administrators when a new version or release becomes available.

---

## Problem Statement

As Open WebUI enters the "Platform Era" of agentic workspaces, the limitations of built-in search tools have become highly visible:
1. **The "Black Box" Search Problem**: Standard web search integrations operate on a single-shot mechanism. The user asks a question, the system runs one query, reads a few short snippets, and attempts a summary. There is no iterative reasoning, leaving users with superficial or inaccurate answers on complex subjects.
2. **The Information Gap**: Short snippets returned by search search APIs are rarely sufficient for professional research. Critical nuances, tables, and timelines are buried in full-text pages that standard tools fail to crawl.
3. **Lack of Transparency**: Users are kept in the dark about *how* search terms were derived, *what* sources were crawled, and *why* specific analytical conclusions were reached. This lack of intermediate thinking visibility breeds trust issues.
4. **Database Pollution & Bloat**: Typical multi-turn agent scripts dump raw links, JSON arrays, and scrape scrapings directly into the chat log database. This causes significant bloat and pollutes the persistent context.
5. **Security and SSRF Vulnerabilities**: Naive python-based scrapers run the risk of scanning internal corporate networks (private IP addresses), introducing severe security gaps if exposed to adversarial user prompts.

The **Iterative Deep Research Agent** solves these limitations by providing a transparent, self-correcting, secure, and deeply rigorous research loop native to the Open WebUI experience.

---

## Requirements

This plugin requires one of the following search providers to be configured:

- **SearXNG**: A self-hosted SearXNG instance URL (e.g., `http://localhost:8080`).
- **Tavily AI**: A valid Tavily API key (get one at [tavily.com](https://tavily.com)).

---

## Admin Valves (global configuration)

The plugin can be fully configured by administrators through the Open WebUI Admin interface using the following Valves:

| Valve Name | Type | Default | Description |
|------------|------|---------|-------------|
| **ENABLE_UPDATE_NOTIFICATIONS** | `bool` | `True` | Checks GitHub in the background and notifies admins of new releases. |
| **CHECK_PREVIEW_RELEASES** | `bool` | `False` | Also checks for pre-release, dev, and preview tags on GitHub. |
| **SEARXNG_URL** | `str` | `""` | The base URL of your SearXNG instance (e.g., `http://searxng:8080`) for private, self-hosted web search. |
| **TAVILY_API_KEY** | `str` | `""` | API key for Tavily Search (alternative or primary search engine API). |
| **MODEL** | `str` | `""` | The internal LLM model ID used for planning, reasoning, and synthesis. (Left blank to auto-detect from active models). |
| **MAX_STEPS** | `int` | `3` | Maximum number of search-reasoning loops to perform (range: `1` to `10`). |
| **MAX_PAGES_TO_SCRAPE** | `int` | `3` | Maximum number of new web pages to crawl and digest concurrently per iteration (range: `1` to `10`). |
| **CO_STORM_STEERING** | `bool` | `False` | Pauses the research loop after Step 1 to allow interactive user feedback (Co-STORM style). |

---

## User Valves (per-user overrides)

Users can customize the agent's behavior for their own chats without affecting global settings. All fields default to `"default"`, which means they **inherit the value from the Admin Valves**.

| Valve Name | Type | Default | Description |
|------------|------|---------|-------------|
| **max_steps** | `str` | `"default"` | Max research steps (e.g., `5`). Variants: `1-10`. |
| **max_pages_to_scrape** | `str` | `"default"` | Max pages to scrape per iteration (e.g., `5`). Variants: `1-10`. |
| **co_storm_steering** | `str` | `"default"` | Enable Co-STORM steering pause (e.g., `true`). Variants: `true`, `false`. |

---

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/open-webui/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** (or **Tools**) -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Iterative Deep Research Agent** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

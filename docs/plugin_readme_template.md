## Quick start

{ Step by step guide how to use plugin }

## Description

{ Short description, answering the questions:
What is it for?
What are its unique features }

## Problem Statement

{ Short description of a problem that plugin is solving }

## Requirements (Optional)

{ list of any external dependencies, API keys, or self-hosted services required for the plugin to function }

## Valves (Configuration)

{ list of all admin valves with their description and possible values }

> [!TIP]
> If your plugin makes external requests or generates links, ensure you document the `proxy_url` and `base_url` valves for VPS/enterprise users.

## User Valves (per-user overrides)

{ list of user-configurable overrides available in the chat interface. All fields default to "default", which means they inherit the value from the Admin Valves. }

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/open-webui/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** (or **Tools**) -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **{Plugin Name}** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.

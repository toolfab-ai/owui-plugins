## Quick start

1. Admin must enable **models access** permission and enable the **Clone Model** function globally.
2. In any chat with a model you want to duplicate, click the **Clone Model** button in the message action toolbar.
3. The cloned model will instantly appear in your workspace where you can customize its parameters, system prompt, and configuration.

## Description

**Clone Model** is an Open WebUI action plugin that allows users to duplicate any accessible model into their personal Workspace. It creates an exact copy of the source model's parameters, system prompt, and metadata, giving users complete freedom to customize and iterate on shared models without administrative intervention.

## Problem Statement

In Open WebUI, when users are granted read-only access to shared models, they cannot modify or customize them to suit their specific workflows. The only workaround has been to manually copy and paste all parameters, prompts, and settings into a brand-new model, which is tedious, error-prone, and inconvenient. 

This plugin solves the issue by enabling a single-click cloning action, streamlining model customization and sharing.

## Installation

### Via URL (Recommended)
1. Navigate to the [Releases](https://github.com/open-webui/owui-plugins/releases) page.
2. Copy the URL of the `plugin.py` file from the latest release of this plugin.
3. In Open WebUI, navigate to **Admin Settings** -> **Functions** (or **Tools**) -> **+ New Function** -> **Install from URL**.
4. Paste the URL and click **Install**.

### Via Open WebUI Community
1. Search for **Clone Model** on the [Open WebUI Community](https://openwebui.com).
2. Click **Install** to import it directly into your instance.
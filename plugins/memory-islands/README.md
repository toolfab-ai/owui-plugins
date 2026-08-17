# Memory Islands Plugin

Version: 0.1.0

Memory Islands provides dynamic, folder-scoped context isolation and memory management for Open WebUI. It ensures that each project folder maintains its own custom instructions and learned memories, preventing cross-talk between contexts.

## Installation

1. Copy the `memory-islands` directory into your `plugins` folder of Open WebUI.
2. Restart Open WebUI server.

## Configuration

Configure plugin settings in the OWUI callbacks configuration:

- `ISOLATE_BY_DEFAULT`: bool — Enforce isolation when no folder is assigned.
- `AUTO_LEARN_MEMORIES`: bool — Enable automatic memory extraction.
- `ENABLE_UPDATE_NOTIFICATIONS`: bool — Enable background checking for plugin updates.
- `CHECK_PREVIEW_RELEASES`: bool — Include pre-releases in update checks.

## Usage

- The plugin hooks into every chat request (`inlet`) and response (`outlet`).
- Contextual folder guidelines and memories are injected at the start of the chat.
- New facts from the conversation are asynchronously extracted and stored per folder.

## Slash Commands

Since there is no admin panel UI required, you can configure and manage each folder's memory island directly from your chat using the following interactive slash commands:

- `/island-help`: Displays the help guide explaining available commands.
- `/island-guidelines <text>`: Sets or updates custom instructions/guidelines for the current folder.
- `/island-status`: Displays the active guidelines and list of auto-learned facts for the current folder.
- `/island-clear-guidelines`: Clears or wipes the custom folder guidelines.
- `/island-clear-facts`: Clears or wipes all auto-learned facts for the current folder.
## Database

- `folder_memories.db` is created under `$DATA_DIR/memory-islands/` (defaults to `~/.openwebui/memory-islands/`).
- Stores `folder_id`, `guidelines`, and `facts` for each folder.

## License

MIT

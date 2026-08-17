from __future__ import annotations

from typing import Any, Dict, List, Optional


class CommandsMixin:
    """Slash-command handling for configuring Memory Islands from chat."""

    def _handle_command(
        self,
        body: Dict[str, Any],
        last_msg: Dict[str, Any],
        messages: List[Dict[str, Any]],
        folder_id: Optional[str],
        content: str,
    ) -> bool:
        """Process an /island-* command. Returns True if handled (caller should return)."""
        parts = content.split(" ", 1)
        cmd = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ""
        last_msg["role"] = "system"

        if not folder_id:
            last_msg["content"] = (
                f"System instruction: The user tried to execute the command '{cmd}' "
                "outside of any folder. Please politely explain that Memory Islands "
                "commands are only active within chats located inside a folder. "
                "Let them know they are currently in the Global Workspace."
            )
            return True

        if cmd == "/island-help":
            last_msg["content"] = (
                "System instruction: The user requested help for Memory Islands. "
                "Please respond with a beautifully formatted markdown guide explaining "
                "what Memory Islands does (folder-scoped context and memory isolation) "
                "and detailing the available commands:\n\n"
                "1. `/island-guidelines <text>`: Set custom instructions/rules for this folder.\n"
                "2. `/island-status`: Show the active guidelines and auto-learned facts for this folder.\n"
                "3. `/island-clear-guidelines`: Wipe the folder-specific instructions.\n"
                "4. `/island-clear-facts`: Delete all auto-learned memories/facts for this folder.\n"
                "5. `/island-help`: Show this help menu.\n\n"
                "Keep your response warm, professional, and clear."
            )
            return True

        if cmd == "/island-guidelines":
            if not arg:
                last_msg["content"] = (
                    "System instruction: The user tried to use `/island-guidelines` "
                    "without providing any rules text. Please politely explain how to use "
                    "it: `/island-guidelines <your custom instructions here>`."
                )
                return True
            self._save_guidelines(folder_id, arg)
            last_msg["content"] = (
                f"System instruction: The user has updated the folder guidelines "
                f"for this folder to: '{arg}'. Please respond with a professional, "
                "enthusiastic confirmation message stating that the new custom folder "
                "guidelines have been successfully saved and are now active for all "
                "chats inside this folder."
            )
            return True

        if cmd == "/island-status":
            guidelines, facts = self._load_folder_data(folder_id)
            facts_str = "\n".join([f"- {f}" for f in facts]) if facts else "(none)"
            guidelines_str = guidelines if guidelines else "No guidelines configured."
            last_msg["content"] = (
                f"System instruction: The user requested the status of the current folder's "
                f"Memory Island. Here is the active folder data:\n\n"
                f"**Folder ID**: `{folder_id}`\n"
                f"**Custom Guidelines**:\n{guidelines_str}\n\n"
                f"**Learned Facts**:\n{facts_str}\n\n"
                "Please format this information beautifully in markdown and present it to "
                "the user. Add a short note explaining that memories are isolated to "
                "this folder."
            )
            return True

        if cmd == "/island-clear-facts":
            self._clear_facts(folder_id)
            last_msg["content"] = (
                "System instruction: The user has cleared all auto-learned facts/memories "
                "for this folder. Please write a polite confirmation confirming that all "
                "learned facts have been successfully wiped from this folder's memory "
                "island, while custom guidelines (if any) remain active."
            )
            return True

        if cmd == "/island-clear-guidelines":
            self._clear_guidelines(folder_id)
            last_msg["content"] = (
                "System instruction: The user has cleared the custom folder guidelines. "
                "Please write a polite confirmation confirming that folder-specific instructions "
                "have been removed, while auto-learned facts (if any) remain intact."
            )
            return True

        last_msg["content"] = (
            f"System instruction: The user entered an unknown command: '{cmd}'. "
            "Please write a polite response letting them know this command is not "
            "recognized, and suggest typing `/island-help` to see the available options."
        )
        return True

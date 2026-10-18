"""Notes MCP client wrapper for AI Personal Task Executor.

Provides:
- save_note(title, content, filename, destination_dir) -> Dict[str, Any] (Side-effecting)

Adheres to:
- PRD.md & ARCHITECTURE.md: MCP tool access for local notes storage.
- RULES.md: Side-effecting operations only execute via Action Agent after human approval.
"""

import os
from typing import Any, Dict, Optional


class NotesMCP:
    """Notes MCP client wrapper for persisting local Markdown notes."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        simulate_failure_count: int = 0,
    ):
        self.storage_path = storage_path or os.getenv("NOTES_STORAGE_PATH") or "notes"
        self._simulate_failure_count = simulate_failure_count

    def save_note(
        self,
        title: str,
        content: str,
        filename: Optional[str] = None,
        destination_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save formatted note to local disk storage.

        Side-effecting operation: executed only after human approval.
        """
        if self._simulate_failure_count > 0:
            self._simulate_failure_count -= 1
            raise IOError("Notes MCP disk I/O write failure")

        if not content:
            raise ValueError("Note content cannot be empty.")

        target_dir = destination_dir or self.storage_path
        os.makedirs(target_dir, exist_ok=True)

        target_file = filename or "note.md"
        if not target_file.endswith(".md"):
            target_file += ".md"

        full_path = os.path.join(target_dir, target_file)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Verify disk write physically succeeded
        if not os.path.exists(full_path) or os.path.getsize(full_path) < len(content.encode("utf-8")):
            raise IOError(f"Disk write verification failed for note: {full_path}")

        return {
            "status": "success",
            "title": title or "Note",
            "filename": target_file,
            "path": full_path,
            "bytes_written": len(content.encode("utf-8")),
            "message": f"Successfully saved note to {full_path}.",
        }


# Default module-level client
_default_notes_client = NotesMCP()


def save_note(
    title: str,
    content: str,
    filename: Optional[str] = None,
    destination_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Module-level save_note helper."""
    return _default_notes_client.save_note(
        title=title,
        content=content,
        filename=filename,
        destination_dir=destination_dir,
    )

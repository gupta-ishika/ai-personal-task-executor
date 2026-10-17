"""Tests for Notes MCP client wrapper."""

import os
import shutil
import pytest
from src.mcp.notes_mcp import NotesMCP, save_note

TEST_NOTES_DIR = "test_scratch_notes"


class TestNotesMCP:
    """Test suite for Notes MCP operations."""

    @classmethod
    def teardown_class(cls):
        if os.path.exists(TEST_NOTES_DIR):
            shutil.rmtree(TEST_NOTES_DIR, ignore_errors=True)

    def test_save_note_success(self):
        client = NotesMCP(storage_path=TEST_NOTES_DIR)
        result = client.save_note(
            title="Cafe Research",
            content="# Best Cafes\n\n1. Third Wave Coffee",
            filename="best_cafes.md",
        )
        assert result["status"] == "success"
        assert os.path.exists(result["path"])
        with open(result["path"], "r", encoding="utf-8") as f:
            saved = f.read()
        assert "Third Wave Coffee" in saved

    def test_save_note_empty_content_raises_value_error(self):
        client = NotesMCP(storage_path=TEST_NOTES_DIR)
        with pytest.raises(ValueError):
            client.save_note(title="Empty Note", content="")

    def test_notes_mcp_simulated_failure(self):
        client = NotesMCP(storage_path=TEST_NOTES_DIR, simulate_failure_count=1)
        with pytest.raises(IOError):
            client.save_note(title="Fail Test", content="Content here")
        # Second attempt succeeds
        res = client.save_note(title="Fail Test", content="Content here")
        assert res["status"] == "success"

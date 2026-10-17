"""Basic setup and environment verification tests."""

import importlib
import pytest


def test_dependencies_importable():
    """Verify that required core dependencies can be imported."""
    modules = [
        "langgraph",
        "langchain_core",
        "pydantic",
        "dotenv",
        "mcp",
        "src",
        "src.agents",
        "src.mcp",
        "src.graph",
        "src.services",
        "src.utils",
    ]
    for mod in modules:
        imported = importlib.import_module(mod)
        assert imported is not None


def test_env_example_exists():
    """Verify that env.example exists and contains required keys."""
    import os
    assert os.path.exists("env.example"), "env.example should exist in the root directory"
    with open("env.example", "r", encoding="utf-8") as f:
        content = f.read()
    assert "LLM_API_KEY=" in content
    assert "SEARCH_MCP_API_KEY=" in content
    assert "CALENDAR_MCP_CLIENT_ID=" in content

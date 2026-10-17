"""Tests for Search MCP client wrapper."""

import pytest
from src.mcp.search_mcp import SearchMCP, search, fetch_page


class TestSearchMCP:
    """Test suite for SearchMCP operations."""

    def test_search_returns_results(self):
        results = search("Find cafe in Indiranagar")
        assert isinstance(results, list)
        assert len(results) > 0
        first = results[0]
        assert "title" in first
        assert "snippet" in first
        assert "url" in first
        assert "source" in first
        assert first["source"] == "Search MCP"

    def test_search_respects_num_results(self):
        results = search("cafe", num_results=2)
        assert len(results) <= 2

    def test_search_empty_or_invalid_query_does_not_crash(self):
        assert search("") == []
        assert search("   ") == []
        assert search(None) == []

    def test_search_fallback_for_unrecognized_query(self):
        results = search("obscure non-existent topic xyz 9999")
        assert isinstance(results, list)
        assert len(results) > 0
        assert "obscure" in results[0]["title"].lower()

    def test_fetch_page_known_url(self):
        content = fetch_page("https://example.com/third-wave-indiranagar")
        assert "Third Wave" in content
        assert "Indiranagar" in content

    def test_fetch_page_empty_or_invalid_url(self):
        content = fetch_page("")
        assert "Error" in content
        content_none = fetch_page(None)
        assert "Error" in content_none

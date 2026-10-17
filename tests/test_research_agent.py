"""Tests for Research Agent and ReAct tool loop."""

import pytest
from src.agents.research_agent import (
    ResearchAgent,
    extract_keywords,
    research_agent_node,
)
from src.graph.graph import create_task_graph
from src.graph.state import AgentState


class TestResearchAgent:
    """Test suite for ResearchAgent logic and ReAct loop."""

    def test_extract_keywords(self):
        req = "Find a cafe for 4 people this Saturday evening, under ₹3000, in Indiranagar"
        keywords = extract_keywords(req)
        assert "cafe" in keywords
        assert "Indiranagar" in keywords
        assert "find" not in [k.lower() for k in keywords]

    def test_research_agent_run_returns_structured_findings(self):
        agent = ResearchAgent(max_iterations=3)
        findings = agent.run("Find 3 good cafes in Indiranagar")
        assert isinstance(findings, list)
        assert len(findings) > 0
        assert len(findings) <= 3

        for item in findings:
            assert "title" in item
            assert "details" in item
            assert "url" in item
            assert "source" in item
            assert item["source"] == "Search MCP"
            assert isinstance(item["details"], str)

    def test_research_agent_handles_empty_or_none(self):
        agent = ResearchAgent()
        assert agent.run("") == []
        assert agent.run("   ") == []
        assert agent.run(None) == []

    def test_research_agent_terminates_within_max_iterations(self):
        agent = ResearchAgent(max_iterations=1)
        findings = agent.run("Explore cafes in Bangalore")
        assert isinstance(findings, list)

    def test_research_agent_node_updates_state(self):
        state: AgentState = {
            "user_request": "Research best noise-cancelling headphones",
            "task_type": "research_and_save",
        }
        updates = research_agent_node(state)
        assert "research_results" in updates
        assert isinstance(updates["research_results"], list)
        assert len(updates["research_results"]) > 0

    def test_graph_integration_populates_research_results(self):
        graph = create_task_graph()
        config = {"configurable": {"thread_id": "test_research_flow"}}
        result = graph.invoke(
            {"user_request": "Find 3 good cafes in Indiranagar and save the options"},
            config=config,
        )
        assert result["task_type"] == "research_and_save"
        assert "research_results" in result
        assert isinstance(result["research_results"], list)
        assert len(result["research_results"]) > 0
        assert any("Indiranagar" in item.get("title", "") or "Coffee" in item.get("title", "") for item in result["research_results"])

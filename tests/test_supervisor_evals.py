"""Supervisor evaluation benchmark suite for tricky requests and classification drift.

Tests edge cases, ambiguous phrasing, compound intents, negative instructions,
and conversational reference queries against both heuristic classifier and LLM.
"""

import pytest
from unittest.mock import patch

from src.agents.supervisor import (
    classify_task_type,
    classify_task_with_llm,
    supervisor_node,
    TASK_TYPE_SCHEDULE,
    TASK_TYPE_RESEARCH_AND_SAVE,
    TASK_TYPE_RESEARCH_AND_ACTION,
)
from src.graph.state import AgentState


# Comprehensive benchmark dataset of tricky user requests
SUPERVISOR_EVAL_DATASET = [
    # --- Category 1: Direct Scheduling with tricky "find/book" phrasing ---
    {
        "query": "Find me a slot tomorrow to meet with Sarah",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "'Find slot' refers to calendar time, not web search",
    },
    {
        "query": "Find a free 30-min window for lunch next Monday",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "'Find window' refers to calendar scheduling",
    },
    {
        "query": "Schedule a meeting with Rahul tomorrow at 5 PM",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "Standard direct calendar meeting request",
    },
    {
        "query": "Can we book 30 mins with Alex next Tuesday at 3pm",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "'Book 30 mins' is direct calendar scheduling",
    },
    {
        "query": "Put team standup on my calendar every morning at 10am",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "Direct calendar entry instruction",
    },
    {
        "query": "Add dentist appointment next Friday at 2 PM to my calendar",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "Direct appointment calendar entry",
    },
    {
        "query": "Call with mentor this Thursday at 4 PM",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "Implicit meeting/call scheduling with temporal cue",
    },

    # --- Category 2: Research & Save with tricky calendar mentions or negative constraints ---
    {
        "query": "Research the history of the Gregorian calendar and save notes",
        "expected": TASK_TYPE_RESEARCH_AND_SAVE,
        "rationale": "'Calendar' is the subject of research, not an action destination",
    },
    {
        "query": "Don't schedule anything, just find some good laptop stands",
        "expected": TASK_TYPE_RESEARCH_AND_SAVE,
        "rationale": "Explicit negative instruction overriding calendar scheduling",
    },
    {
        "query": "Find 3 good cafes in Indiranagar and save the options",
        "expected": TASK_TYPE_RESEARCH_AND_SAVE,
        "rationale": "Research venue options and save to notes",
    },
    {
        "query": "Look up the best mechanical keyboards under ₹5000",
        "expected": TASK_TYPE_RESEARCH_AND_SAVE,
        "rationale": "Pure product lookup without calendar action",
    },
    {
        "query": "Compare iPhone 16 and Pixel 9 and write down the pros and cons",
        "expected": TASK_TYPE_RESEARCH_AND_SAVE,
        "rationale": "Comparison and note taking",
    },
    {
        "query": "Search for top hiking trails near Bangalore and store the list",
        "expected": TASK_TYPE_RESEARCH_AND_SAVE,
        "rationale": "Research and save information",
    },
    {
        "query": "No need to schedule, find 5 budget hotels in Goa and note them",
        "expected": TASK_TYPE_RESEARCH_AND_SAVE,
        "rationale": "Negative schedule phrase with research & note intent",
    },

    # --- Category 3: Compound Research and Action ---
    {
        "query": "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar",
        "expected": TASK_TYPE_RESEARCH_AND_ACTION,
        "rationale": "Primary compound flow: research first then schedule",
    },
    {
        "query": "Look up Italian restaurants near MG Road and book a table for 8pm this Saturday",
        "expected": TASK_TYPE_RESEARCH_AND_ACTION,
        "rationale": "Research restaurant options and book/schedule event",
    },
    {
        "query": "Find 3 coffee shops in Koramangala and put the best one on my schedule for Sunday 5 PM",
        "expected": TASK_TYPE_RESEARCH_AND_ACTION,
        "rationale": "Search coffee shops and schedule calendar event",
    },
    {
        "query": "Search for co-working spaces in HSR and create a calendar event for a trial visit tomorrow",
        "expected": TASK_TYPE_RESEARCH_AND_ACTION,
        "rationale": "Search spaces and create event",
    },

    # --- Category 4: Multi-turn Follow-up Reference Queries ---
    {
        "query": "Schedule a visit to the first cafe from earlier research this Friday at 4pm",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "Follow-up scheduling referencing existing research without new search",
    },
    {
        "query": "Book the second option tomorrow at 5 PM",
        "expected": TASK_TYPE_SCHEDULE,
        "rationale": "Direct booking of an earlier option",
    },
]


class TestSupervisorEvaluationSuite:
    """Benchmark evaluation tests for supervisor classification accuracy."""

    @pytest.mark.parametrize(
        "case",
        SUPERVISOR_EVAL_DATASET,
        ids=[c["query"][:40] for c in SUPERVISOR_EVAL_DATASET],
    )
    def test_heuristic_classification_eval(self, case):
        """Test that heuristic classifier accurately categorizes tricky requests."""
        actual = classify_task_type(case["query"])
        assert actual == case["expected"], (
            f"Classification failed for: '{case['query']}'\n"
            f"Expected: {case['expected']}, Got: {actual}\n"
            f"Rationale: {case['rationale']}"
        )

    def test_supervisor_node_end_to_end_on_eval_cases(self):
        """Test supervisor_node execution across key tricky edge cases."""
        tricky_cases = [
            ("Find me a slot tomorrow to meet with Sarah", TASK_TYPE_SCHEDULE),
            ("Research the history of the Gregorian calendar and save notes", TASK_TYPE_RESEARCH_AND_SAVE),
            ("Don't schedule anything, just find some good laptop stands", TASK_TYPE_RESEARCH_AND_SAVE),
            ("Schedule a visit to the first cafe from earlier research this Friday at 4pm", TASK_TYPE_SCHEDULE),
        ]
        for query, expected in tricky_cases:
            state: AgentState = {"user_request": query}
            updates = supervisor_node(state)
            assert updates["task_type"] == expected, f"Failed for '{query}': expected {expected}, got {updates['task_type']}"

    @patch("src.agents.supervisor.is_ollama_available", return_value=True)
    @patch("src.agents.supervisor.query_ollama")
    def test_llm_classification_evaluation_with_mock(self, mock_query, mock_avail):
        """Test that classify_task_with_llm parses model response cleanly."""
        mock_query.return_value = "'schedule'"
        res = classify_task_with_llm("Find a free slot tomorrow at 3 PM")
        assert res == TASK_TYPE_SCHEDULE

        mock_query.return_value = "research_and_save"
        res = classify_task_with_llm("Look up keyboard reviews and save notes")
        assert res == TASK_TYPE_RESEARCH_AND_SAVE

        mock_query.return_value = "  'research_and_action'  "
        res = classify_task_with_llm("Find restaurants and book a table for tomorrow")
        assert res == TASK_TYPE_RESEARCH_AND_ACTION

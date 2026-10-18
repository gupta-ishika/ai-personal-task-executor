"""Research Agent for AI Personal Task Executor.

Responsible for:
1. Gathers external information using Search MCP tools (search(), fetch_page()).
2. Runs a keyword-scoped ReAct-style tool loop:
   - Reason: Identify required info, keywords, and criteria from user request
   - Act: Call Search MCP tools
   - Observe: Filter and evaluate result relevance
   - Repeat until sufficient findings gathered or max iterations reached
3. Formats and returns structured findings to AgentState (short list with sources, no raw dumps).
4. Handles empty or ambiguous queries gracefully without crashing.
"""

import re
from typing import Any, Dict, List, Optional
from src.graph.state import AgentState
from src.mcp.search_mcp import search, fetch_page, score_relevance, sanitize_untrusted_content

DEFAULT_MAX_ITERATIONS = 3


def extract_keywords(user_request: str) -> List[str]:
    """Extract salient search keywords from user request."""
    # Remove filler / command phrasing
    cleaned = re.sub(
        r"\b(find|search|look up|research|explore|schedule|put on my calendar|add to my calendar|save|note|options|me|a|an|the|for|and|in|on|at|with)\b",
        " ",
        user_request,
        flags=re.IGNORECASE,
    )
    words = re.findall(r"\b[a-zA-Z0-9₹\-]{2,}\b", cleaned)
    return words


class ResearchAgent:
    """Research agent running a ReAct-style tool loop with Search MCP."""

    def __init__(self, max_iterations: int = DEFAULT_MAX_ITERATIONS):
        self.max_iterations = max_iterations

    def run(self, user_request: Optional[str]) -> List[Dict[str, Any]]:
        """Execute the ReAct research loop for a given user request.

        Args:
            user_request: Raw user input text.

        Returns:
            Structured list of research findings.
        """
        if not user_request or not isinstance(user_request, str) or not user_request.strip():
            return []

        req = user_request.strip()
        keywords = extract_keywords(req)

        # Formulate primary and refined query candidates
        primary_query = " ".join(keywords[:5]) if keywords else req
        queries = [primary_query]

        # Add location/entity-focused secondary query if available
        if len(keywords) > 2:
            queries.append(" ".join(keywords[:3]))

        findings: List[Dict[str, Any]] = []
        visited_urls = set()
        iterations = 0

        for query in queries:
            if iterations >= self.max_iterations:
                break

            # --- ReAct Step: Reason ---
            thought = f"Searching external sources for query: '{query}'"
            iterations += 1

            # --- ReAct Step: Act (Call search tool) ---
            raw_results = search(query=query, num_results=3)

            # --- ReAct Step: Observe ---
            for res in raw_results:
                url = res.get("url", "")
                if url in visited_urls:
                    continue
                visited_urls.add(url)

                title = res.get("title", "Untitled finding")
                snippet = res.get("snippet", "")
                source = res.get("source", "Search MCP")

                # If snippet is brief and page content is available, do a fetch_page observation
                details = snippet
                if len(snippet) < 80 and iterations < self.max_iterations:
                    page_text = fetch_page(url)
                    iterations += 1
                    if page_text and not page_text.startswith("Error"):
                        details = page_text[:300]
                else:
                    details = sanitize_untrusted_content(snippet)

                findings.append({
                    "title": title,
                    "details": details,
                    "url": url,
                    "source": source,
                })

                # Check if we have gathered sufficient findings (typically 2-3 top candidates)
                if len(findings) >= 3:
                    break

            if len(findings) >= 3:
                break

        # Sort findings by relevance to the user's explicit request criteria
        findings.sort(key=lambda item: score_relevance(req, item), reverse=True)
        return findings


def research_agent_node(state: AgentState) -> Dict[str, Any]:
    """Research Agent node for LangGraph workflow.

    Reads user_request from state, executes ReAct search loop,
    and returns structured findings into state.
    """
    user_request = state.get("user_request")
    agent = ResearchAgent()
    findings = agent.run(user_request)

    return {"research_results": findings}

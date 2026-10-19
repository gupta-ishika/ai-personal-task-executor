"""Research Agent for AI Personal Task Executor.

Responsible for:
1. Gathers external information using Search MCP tools (search(), fetch_page()).
2. Runs an adaptive ReAct tool loop:
   - Reason: Analyze findings against user criteria to dynamically determine missing info.
   - Act: Call Search MCP tools with distinct operation budgets (search vs page fetch).
   - Observe: Validate URLs, defensively extract keyword-relevant page excerpts, score relevance.
   - Dynamic Next Step: Formulate adaptive follow-up queries or terminate when findings are sufficient.
3. Formats and returns structured findings to AgentState (short list with sources, no raw dumps).
4. Handles empty queries, tool exceptions, network errors, and malformed inputs gracefully.
"""

import re
from typing import Any, Dict, List, Optional, Set
from src.graph.state import AgentState
from src.mcp.search_mcp import search, fetch_page, score_relevance, sanitize_untrusted_content
from src.utils.llm import is_ollama_available, query_ollama

DEFAULT_MAX_SEARCH_CALLS = 2
DEFAULT_MAX_PAGE_FETCHES = 3


def extract_keywords(user_request: str) -> List[str]:
    """Extract salient search keywords from user request."""
    cleaned = re.sub(
        r"\b(find|search|look up|research|explore|schedule|put on my calendar|add to my calendar|save|note|options|me|a|an|the|for|and|in|on|at|with)\b",
        " ",
        user_request,
        flags=re.IGNORECASE,
    )
    words = re.findall(r"\b[a-zA-Z0-9₹\-]{2,}\b", cleaned)
    return words


def is_valid_url(url: Optional[str]) -> bool:
    """Validate that a URL is a non-empty, well-formed web address."""
    if not url or not isinstance(url, str):
        return False
    cleaned = url.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        return False
    if "." not in cleaned and "localhost" not in cleaned:
        return False
    return len(cleaned) >= 10


def extract_relevant_excerpt(page_text: str, query_keywords: List[str], max_chars: int = 350) -> str:
    """Extract a context-aware snippet from page text containing the query keywords.

    Instead of naively taking the first 300 characters (which often contain header/cookie junk),
    finds sentences/paragraphs that contain query terms and extracts a coherent window.
    """
    if not page_text or not page_text.strip():
        return ""

    clean_text = page_text.strip()
    chunks = [c.strip() for c in re.split(r"(?<=[.!?\n])\s+", clean_text) if len(c.strip()) > 20]

    if not chunks:
        return clean_text[:max_chars].strip()

    keyword_set = {k.lower() for k in query_keywords}
    best_chunk_idx = 0
    best_score = -1

    for idx, chunk in enumerate(chunks):
        chunk_words = set(re.findall(r"\b\w+\b", chunk.lower()))
        overlap = len(chunk_words.intersection(keyword_set))
        if any(sym in chunk for sym in ["₹", "$", "Rs", "rs", "pm", "am", "hours", "open"]):
            overlap += 1
        if overlap > best_score:
            best_score = overlap
            best_chunk_idx = idx

    if best_score > 0:
        selected_text = chunks[best_chunk_idx]
        if len(selected_text) < max_chars and best_chunk_idx + 1 < len(chunks):
            selected_text += " " + chunks[best_chunk_idx + 1]
        return selected_text[:max_chars].strip()

    return clean_text[:max_chars].strip()


class ResearchAgent:
    """Research agent running a dynamic ReAct-style tool loop with Search MCP."""

    def __init__(
        self,
        max_iterations: Optional[int] = None,
        max_search_calls: int = DEFAULT_MAX_SEARCH_CALLS,
        max_page_fetches: int = DEFAULT_MAX_PAGE_FETCHES,
    ):
        # Support max_iterations for backward compatibility
        if max_iterations is not None:
            self.max_search_calls = max_iterations
            self.max_page_fetches = max_iterations
        else:
            self.max_search_calls = max_search_calls
            self.max_page_fetches = max_page_fetches

    def _decide_next_query(
        self,
        user_request: str,
        current_findings: List[Dict[str, Any]],
        executed_queries: Set[str],
        keywords: List[str],
    ) -> Optional[str]:
        """Dynamically reason about what query to run next based on gathered findings."""
        if len(current_findings) >= 3:
            return None

        # Dynamic reasoning via local Ollama LLM if available
        if is_ollama_available():
            try:
                findings_summary = "; ".join(
                    [f"{f.get('title')}: {f.get('details')[:100]}" for f in current_findings]
                ) or "None yet"
                prompt = (
                    f"User Request: {user_request}\n"
                    f"Current Findings: {findings_summary}\n"
                    f"Previous Queries: {', '.join(executed_queries)}\n\n"
                    "Do we have sufficient specific options to answer the user request? "
                    "If yes, reply with 'DONE'. If no, formulate ONE short, targeted search query "
                    "to find the missing information (do not repeat previous queries). "
                    "Reply ONLY with the query or 'DONE'."
                )
                response = query_ollama(prompt=prompt, timeout=8.0)
                if response:
                    clean_resp = response.strip().replace('"', '').replace("'", "")
                    if "DONE" in clean_resp.upper() or len(clean_resp) < 3:
                        return None
                    if clean_resp.lower() not in {q.lower() for q in executed_queries}:
                        return clean_resp
            except Exception:
                pass

        # Heuristic dynamic query formulation fallback
        if len(current_findings) == 0:
            if len(keywords) > 2:
                broader = " ".join(keywords[:2])
                if broader.lower() not in {q.lower() for q in executed_queries}:
                    return broader
        elif len(current_findings) < 3:
            if len(keywords) > 2:
                alternative = " ".join(keywords[:3])
                if alternative.lower() not in {q.lower() for q in executed_queries}:
                    return alternative

        return None

    def run(self, user_request: Optional[str]) -> List[Dict[str, Any]]:
        """Execute the dynamic ReAct research loop for a given user request.

        Args:
            user_request: Raw user input text.

        Returns:
            Structured, relevance-ranked list of research findings.
        """
        if not user_request or not isinstance(user_request, str) or not user_request.strip():
            return []

        req = user_request.strip()
        keywords = extract_keywords(req)

        current_query: Optional[str] = " ".join(keywords[:5]) if keywords else req
        executed_queries: Set[str] = set()
        visited_urls: Set[str] = set()
        findings: List[Dict[str, Any]] = []

        search_calls_count = 0
        page_fetches_count = 0

        while current_query and search_calls_count < self.max_search_calls:
            # --- ReAct Step 1: Reason ---
            executed_queries.add(current_query)
            search_calls_count += 1

            # --- ReAct Step 2: Act (Search call with defensive exception handling) ---
            try:
                raw_results = search(query=current_query, num_results=3)
            except Exception:
                raw_results = []

            # --- ReAct Step 3: Observe & Validate Candidates ---
            for res in raw_results:
                if not isinstance(res, dict):
                    continue

                raw_url = res.get("url")
                if not is_valid_url(raw_url):
                    continue

                url = str(raw_url).strip()
                if url in visited_urls:
                    continue
                visited_urls.add(url)

                raw_title = str(res.get("title") or "").strip()
                raw_snippet = str(res.get("snippet") or "").strip()
                source = str(res.get("source") or "Search MCP").strip()

                if not raw_title and not raw_snippet:
                    continue

                title = raw_title or "Untitled finding"
                snippet = raw_snippet

                # Compute relevance early
                temp_item = {"title": title, "snippet": snippet}
                relevance = score_relevance(req, temp_item)

                # If snippet is brief and page fetch budget allows, perform contextual fetch
                details = snippet
                if len(snippet) < 80 and page_fetches_count < self.max_page_fetches:
                    page_fetches_count += 1
                    try:
                        page_text = fetch_page(url)
                        if page_text and not page_text.startswith("Error"):
                            excerpt = extract_relevant_excerpt(page_text, keywords)
                            details = excerpt or page_text[:300]
                    except Exception:
                        details = snippet

                # Sanitize against prompt injection before retaining
                sanitized_details = sanitize_untrusted_content(details)

                findings.append({
                    "title": title,
                    "details": sanitized_details,
                    "url": url,
                    "source": source,
                    "relevance_score": relevance,
                })

            # Check if we have gathered at least 3 high-relevance findings
            high_quality = [f for f in findings if f.get("relevance_score", 0) > 0]
            if len(high_quality) >= 3:
                break

            # --- ReAct Step 4: Dynamic Reflection for Next Action ---
            current_query = self._decide_next_query(
                user_request=req,
                current_findings=findings,
                executed_queries=executed_queries,
                keywords=keywords,
            )

        # Sort findings by relevance to the user's explicit request criteria (highest relevance first)
        findings.sort(key=lambda item: item.get("relevance_score", 0), reverse=True)
        findings = findings[:3]

        for item in findings:
            item.pop("relevance_score", None)

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

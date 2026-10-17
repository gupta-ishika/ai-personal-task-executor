"""LLM client integration for AI Personal Task Executor.

Supports local inference using Ollama (defaulting to llama3.2:3b)
with automatic fallback to deterministic behavior when offline or running tests.
"""

import os
import re
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")


def is_ollama_available(base_url: Optional[str] = None, timeout: float = 1.0) -> bool:
    """Check if the local Ollama daemon is reachable.

    Automatically returns False during pytest execution to keep the test suite
    deterministic, instant, and offline, unless FORCE_LLM_IN_TESTS=true is set.

    Args:
        base_url: Ollama HTTP base URL.
        timeout: Network timeout in seconds for ping check.

    Returns:
        True if reachable and healthy, False otherwise.
    """
    if os.getenv("PYTEST_CURRENT_TEST") and os.getenv("FORCE_LLM_IN_TESTS", "").lower() != "true":
        return False

    url = (base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/") + "/api/tags"
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def query_ollama(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 40.0,
) -> Optional[str]:
    """Query local Ollama instance for text generation.

    Args:
        prompt: User prompt text.
        system: Optional system instruction prompt.
        model: Model tag (defaults to OLLAMA_MODEL or llama3.2:3b).
        base_url: Ollama server URL.
        timeout: Generation request timeout in seconds.

    Returns:
        Generated text string or None on failure/timeout.
    """
    target_model = model or DEFAULT_OLLAMA_MODEL
    url = (base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/") + "/api/generate"

    payload: Dict[str, Any] = {
        "model": target_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
        },
    }
    if system:
        payload["system"] = system

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", "").strip()
    except Exception:
        pass
    return None


def llm_synthesize_findings(
    query: str,
    num_results: int = 3,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Synthesize realistic research findings for arbitrary queries using local Ollama.

    Args:
        query: User search query string.
        num_results: Target number of items to produce.
        model: Optional model name.

    Returns:
        List of structured search finding dictionaries.
    """
    target_model = model or DEFAULT_OLLAMA_MODEL
    system_prompt = (
        "You are a helpful research and search assistant. Given the user query, provide accurate, "
        "realistic recommendations or informative points.\n"
        "Format each finding strictly on a single line starting with 'Item: <Name or Title> - <Detailed Snippet>'.\n"
        "Do not include any greeting, preamble, or conversational filler."
    )
    user_prompt = f"Provide {num_results} top findings/recommendations for: {query}"

    response_text = query_ollama(prompt=user_prompt, system=system_prompt, model=target_model, timeout=35.0)
    if not response_text:
        return []

    findings: List[Dict[str, Any]] = []
    lines = [line.strip() for line in response_text.splitlines() if line.strip()]

    for line in lines:
        cleaned = re.sub(r"^(?:Item:\s*|\d+[\.\)]\s*|\-\s*)", "", line).strip()
        if not cleaned:
            continue
        parts = cleaned.split(" - ", 1)
        if len(parts) == 2:
            title = parts[0].strip()
            snippet = parts[1].strip()
        else:
            title = cleaned[:50].strip()
            snippet = cleaned

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
        findings.append({
            "title": title,
            "snippet": snippet,
            "url": f"https://local-intel.ai/{slug}",
            "source": f"Ollama ({target_model})",
        })
        if len(findings) >= num_results:
            break

    return findings


def llm_generate_note_content(
    user_request: str,
    research_results: List[Dict[str, Any]],
    model: Optional[str] = None,
) -> Optional[str]:
    """Generate a high-quality Markdown research document using local Ollama.

    Args:
        user_request: The user research topic.
        research_results: List of gathered findings.
        model: Optional model name.

    Returns:
        Markdown-formatted string or None if generation failed.
    """
    findings_summary = "\n".join(
        f"- {r.get('title', 'Item')}: {r.get('details', r.get('snippet', ''))} (Source: {r.get('url', 'N/A')})"
        for r in research_results
    )
    prompt = (
        f"You are a personal productivity executive assistant. Write a clean, professional Markdown report "
        f"summarizing research for the following user request:\n\n"
        f"Request: \"{user_request}\"\n\n"
        f"Discovered Findings:\n{findings_summary}\n\n"
        f"Include a concise executive summary, detailed breakdown of recommendations, and key takeaway advice.\n"
        f"Return ONLY valid Markdown without backtick code-block fences."
    )
    res = query_ollama(prompt=prompt, model=model, timeout=40.0)
    if res and len(res) > 50:
        # Strip code block fences if returned
        res = re.sub(r"^```markdown\s*", "", res, flags=re.IGNORECASE)
        res = re.sub(r"^```\s*", "", res)
        res = re.sub(r"\s*```$", "", res)
        return res.strip()
    return None


def llm_generate_executive_summary(
    user_request: str,
    action_type: str,
    action_summary: str,
    execution_status: str,
    model: Optional[str] = None,
) -> Optional[str]:
    """Generate a dynamic, natural language final summary of the completed task.

    Args:
        user_request: Original user request.
        action_type: Executed action type.
        action_summary: Proposed action summary.
        execution_status: Status ('success', 'rejected', etc.).
        model: Optional model name.

    Returns:
        Short conversational summary string.
    """
    prompt = (
        f"You are a personal productivity assistant. Write a direct 1 to 2 sentence confirmation to the user.\n"
        f"User Request: {user_request}\n"
        f"Action: {action_summary}\n"
        f"Status: {execution_status}\n"
        f"Speak directly to the user (e.g. 'I have researched... and scheduled...'). Do NOT include any intro like 'Here is...' or quotation marks."
    )
    ans = query_ollama(prompt=prompt, model=model, timeout=25.0)
    if ans:
        cleaned = re.sub(r'^(?:Here is|Sure,|Certainly)[^\n]*\n+', '', ans, flags=re.IGNORECASE).strip()
        cleaned = cleaned.strip('"').strip("'")
        return cleaned
    return None

"""Main CLI entrypoint for AI Personal Task Executor.

Provides an interactive REPL chat mode and command-line interface to research,
plan, pause for human approval, and execute personal productivity tasks.
"""

import sys
import uuid
import argparse
from typing import Any, Dict, Optional

# Ensure UTF-8 output encoding across Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.graph.graph import create_task_graph
from src.utils.llm import is_ollama_available, DEFAULT_OLLAMA_MODEL


def print_help():
    """Display interactive CLI commands and usage guidance."""
    print("\n" + "=" * 65)
    print("  AI PERSONAL TASK EXECUTOR — REPL COMMANDS & USAGE")
    print("=" * 65)
    print("Commands:")
    print("  /help     : Display this help message")
    print("  /status   : View active session ID, checkpointer, and memory state")
    print("  /history  : View conversation history & executed actions in this session")
    print("  /clear    : Reset conversation state and start a fresh session")
    print("  /exit     : Cleanly exit the chat session (also /quit)")
    print("\nWorkflow Examples:")
    print("  1. Research & Save Note:")
    print("     \"Find 3 good cafes in Indiranagar and save the options\"")
    print("  2. Conversational Follow-up (Multi-turn):")
    print("     \"Now schedule a meeting at the first one this Saturday at 5 PM\"")
    print("  3. Direct Scheduling:")
    print("     \"Schedule a team sync with Priya tomorrow at 11 AM\"")
    print("  4. Compound Research & Scheduling:")
    print("     \"Find Italian restaurants near MG Road and book a table for 8 PM\"")
    print("  5. Plan Revisions at Approval Gate:")
    print("     Type 'm: change time to 6:30 PM' or 'reject' to explore alternative options.")
    print("=" * 65 + "\n")


def print_status(graph, config: Dict[str, Any]):
    """Display current session state and diagnostic information."""
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    state = graph.get_state(config)
    values = state.values if state else {}

    ollama_online = is_ollama_available()
    llm_info = f"Ollama ({DEFAULT_OLLAMA_MODEL}) [ONLINE]" if ollama_online else "Deterministic / Heuristics [OFFLINE]"

    research_results = values.get("research_results") or []
    history = values.get("conversation_history") or []
    last_action = values.get("proposed_action") or {}

    print("\n" + "=" * 65)
    print("  ACTIVE SESSION STATUS")
    print("=" * 65)
    print(f"Session Thread ID   : {thread_id}")
    print(f"Checkpointer        : Active (MemorySaver)")
    print(f"LLM Engine          : {llm_info}")
    print(f"Total Turns Run     : {len(history)}")
    print(f"Cached Findings     : {len(research_results)} item(s) in session memory")
    if research_results:
        for idx, item in enumerate(research_results, 1):
            print(f"  [{idx}] {item.get('title')} ({item.get('url', 'no url')})")
    if last_action:
        print(f"Last Action Summary : {last_action.get('summary', 'None')} (Rev #{last_action.get('revision', 1)})")
        print(f"Approval Status     : {values.get('approval_status', 'None')}")
    print("=" * 65 + "\n")


def print_history(graph, config: Dict[str, Any]):
    """Display the chronological conversation history and action records."""
    state = graph.get_state(config)
    values = state.values if state else {}
    history = values.get("conversation_history") or []

    print("\n" + "=" * 65)
    print(f"  SESSION CONVERSATION HISTORY ({len(history)} turn{'s' if len(history) != 1 else ''})")
    print("=" * 65)

    if not history:
        print("  No conversation turns completed yet in this session.")
    else:
        for idx, turn in enumerate(history, 1):
            user_req = turn.get("user_request", "")
            task_type = turn.get("task_type", "")
            proposed = turn.get("proposed_action") or {}
            exec_res = turn.get("execution_result") or {}
            status = exec_res.get("status") or turn.get("approval_status") or "completed"

            print(f"\n[Turn #{idx}]")
            print(f"  Request  : \"{user_req}\"")
            print(f"  Type     : {task_type}")
            print(f"  Action   : {proposed.get('summary', 'N/A')}")
            print(f"  Status   : {status.upper()}")

    print("=" * 65 + "\n")


def execute_turn(graph, config: Dict[str, Any], user_request: str, auto_decision: Optional[str] = None):
    """Execute a single conversational turn in the LangGraph workflow.

    Maintains accumulated research findings across turns while refreshing
    per-turn ephemeral flags.
    """
    ollama_online = is_ollama_available()
    llm_info = f"Ollama ({DEFAULT_OLLAMA_MODEL})" if ollama_online else "Deterministic / Heuristics"

    print("\n" + "-" * 65)
    print(f"[Turn Request]: \"{user_request}\"")
    print(f"[LLM Engine]  : {llm_info}")
    print("-" * 65)

    # Initialize / refresh turn state while preserving research_results
    turn_input: Dict[str, Any] = {
        "user_request": user_request,
        "task_type": None,
        "approval_status": "pending",
        "proposed_action": None,
        "execution_result": None,
        "final_summary": None,
        "error": None,
    }

    print("\n>>> Routing request & executing agents...")
    graph.invoke(turn_input, config=config)

    # Loop to handle approval gate and potential re-planning cycles
    while True:
        state = graph.get_state(config)

        # Check if paused at human-in-the-loop approval gate
        if state.next and state.next[0] == "approval_node":
            interrupt_data = state.tasks[0].interrupts[0].value
            proposed_action = interrupt_data.get("proposed_action", {})
            action_type = proposed_action.get("action_type") or proposed_action.get("type", "unknown")
            revision = proposed_action.get("revision", 1)

            print("\n" + "-" * 65)
            print(f"🚨 HUMAN APPROVAL GATE (Revision #{revision})")
            print("-" * 65)
            print(f"Action Type : {action_type}")
            print(f"Summary     : {proposed_action.get('summary', '')}")
            print("Details     :")
            for k, v in proposed_action.get("details", {}).items():
                if k == "content":
                    print(f"  - {k}: (Markdown note content with {proposed_action['details'].get('item_count', 0)} items)")
                else:
                    print(f"  - {k}: {v}")
            print("-" * 65)

            # Determine decision
            feedback = None
            if auto_decision == "reject_once":
                decision = "rejected"
                auto_decision = "approved"
                print(f"[Automated Decision]: REJECTED (Simulating human rejection)")
            elif auto_decision:
                decision = auto_decision
                print(f"[Automated Decision]: {decision.upper()}")
            else:
                try:
                    user_choice = input(
                        "\nDo you approve this action? ([A]pprove / [R]eject / [M]odify <notes>): "
                    ).strip()
                    choice_lower = user_choice.lower()
                    if choice_lower in {"a", "approve", "yes", "y"}:
                        decision = "approved"
                    elif choice_lower in {"r", "reject", "no", "n"}:
                        decision = "rejected"
                    elif choice_lower.startswith("m:") or choice_lower.startswith("modify"):
                        decision = "rejected"
                        # Extract feedback after prefix
                        if ":" in user_choice:
                            feedback = user_choice.split(":", 1)[1].strip()
                        else:
                            parts = user_choice.split(None, 1)
                            feedback = parts[1].strip() if len(parts) > 1 else "Please revise options"
                        print(f"[Revision Requested]: \"{feedback}\"")
                    else:
                        print("Unrecognized response; defaulting safely to REJECT.")
                        decision = "rejected"
                except (EOFError, KeyboardInterrupt):
                    print("\nInput closed; defaulting safely to REJECT.")
                    decision = "rejected"

            if decision == "rejected":
                print("\n>>> Proposal rejected. Routing back to Planning Agent for alternative options...")
                resume_payload: Any = {"decision": "rejected", "feedback": feedback} if feedback else "rejected"
                graph.invoke(Command(resume=resume_payload), config=config)
                if auto_decision == "reject_once":
                    auto_decision = "approved"
            else:
                print("\n>>> Proposal APPROVED! Action Agent executing side-effecting MCP tools...")
                graph.invoke(Command(resume="approved"), config=config)
                break
        else:
            # Graph finished without pausing (or already completed)
            break

    # Get final result and display summary
    final_state = graph.get_state(config)
    final_summary = final_state.values.get("final_summary", {})

    print("\n" + "=" * 65)
    print("  TURN RUN SUMMARY")
    print("=" * 65)
    if final_summary and final_summary.get("executive_summary"):
        print(f"\n[AI Assistant Summary]:\n{final_summary['executive_summary']}\n")
    if final_summary and "text" in final_summary:
        print(final_summary["text"])
    else:
        print(final_state.values)
    print("=" * 65 + "\n")


def run_task(user_request: str, auto_decision: Optional[str] = None):
    """Run a single personal productivity task through the LangGraph pipeline."""
    thread_id = f"session-{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = create_task_graph(checkpointer=MemorySaver())
    execute_turn(graph, config, user_request, auto_decision=auto_decision)


def interactive_session():
    """Interactive continuous conversation loop (REPL)."""
    thread_id = f"session-{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = create_task_graph(checkpointer=MemorySaver())

    ollama_online = is_ollama_available()
    llm_info = f"Ollama ({DEFAULT_OLLAMA_MODEL})" if ollama_online else "Deterministic / Heuristics"

    print("\n" + "=" * 65)
    print("  AI PERSONAL TASK EXECUTOR — INTERACTIVE CHAT MODE")
    print(f"  Session ID : {thread_id}")
    print(f"  LLM Engine : {llm_info}")
    print("  Type your request, or commands: /help, /history, /status, /clear, /exit")
    print("=" * 65 + "\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in {"/exit", "/quit", "exit", "quit"}:
            print("Session ended. Goodbye!")
            break
        elif cmd == "/help":
            print_help()
        elif cmd == "/status":
            print_status(graph, config)
        elif cmd == "/history":
            print_history(graph, config)
        elif cmd == "/clear":
            thread_id = f"session-{uuid.uuid4().hex[:6]}"
            config = {"configurable": {"thread_id": thread_id}}
            graph = create_task_graph(checkpointer=MemorySaver())
            print(f"\nSession state cleared. Starting new conversation (Session ID: {thread_id}).\n")
        else:
            execute_turn(graph, config, user_input)


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="AI Personal Task Executor CLI")
    parser.add_argument(
        "--request",
        "-r",
        type=str,
        help="Custom productivity request to run (single-shot)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Start continuous interactive chat mode (REPL)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the primary demo flow with automated approval",
    )
    parser.add_argument(
        "--demo-replan",
        action="store_true",
        help="Run the primary demo flow rejecting the first proposal to demonstrate re-planning",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve actions without prompting",
    )
    args = parser.parse_args()

    if args.interactive:
        interactive_session()
        return

    if args.demo:
        demo_request = (
            "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar"
        )
        run_task(demo_request, auto_decision="approved")
        return

    if args.demo_replan:
        demo_request = (
            "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar"
        )
        run_task(demo_request, auto_decision="reject_once")
        return

    if args.request:
        decision = "approved" if args.auto_approve else None
        run_task(args.request, auto_decision=decision)
        return

    # Interactive menu
    print("\n" + "=" * 65)
    print("  AI PERSONAL TASK EXECUTOR — SELECT A WORKFLOW")
    print("=" * 65)
    print("1. Interactive Continuous Chat (REPL Mode - Multi-turn Conversation)")
    print("2. Primary Demo: Research + Plan + Approve + Schedule Cafe Event")
    print("3. Variant 1: Direct Calendar Scheduling (Schedule meeting with Rahul)")
    print("4. Variant 2: Research & Save Note (Find cafes & save Markdown note)")
    print("5. Re-planning Demo (Reject first proposal -> Plan alternative -> Approve)")
    print("6. Single Custom Request")
    print("=" * 65)

    try:
        choice = input("\nEnter choice (1-6) [Default: 1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if choice == "2":
        run_task(
            "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar",
            auto_decision="approved" if args.auto_approve else None,
        )
    elif choice == "3":
        run_task(
            "Schedule a meeting with Rahul tomorrow at 5 PM",
            auto_decision="approved" if args.auto_approve else None,
        )
    elif choice == "4":
        run_task(
            "Find 3 good cafes in Indiranagar and save the options",
            auto_decision="approved" if args.auto_approve else None,
        )
    elif choice == "5":
        run_task(
            "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar",
            auto_decision="reject_once",
        )
    elif choice == "6":
        try:
            custom_req = input("\nEnter your request: ").strip()
        except (EOFError, KeyboardInterrupt):
            custom_req = ""
        if custom_req:
            run_task(custom_req, auto_decision="approved" if args.auto_approve else None)
        else:
            print("No request entered.")
    else:
        # Default: 1 -> Interactive Continuous Chat REPL
        interactive_session()


if __name__ == "__main__":
    main()

"""Main CLI entrypoint for AI Personal Task Executor.

Provides an interactive and command-line interface to research, plan,
pause for human approval, and execute personal productivity tasks.
"""

import sys
import uuid
import argparse
from typing import Optional

# Ensure UTF-8 output encoding across Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.graph.graph import create_task_graph


def run_task(user_request: str, auto_decision: Optional[str] = None):
    """Run a single personal productivity task through the LangGraph pipeline.

    Args:
        user_request: The user task string.
        auto_decision: Optional automated approval decision ('approve' or 'reject')
                       for non-interactive / automated demo runs.
    """
    print("\n" + "=" * 65)
    print("  AI PERSONAL TASK EXECUTOR")
    print("=" * 65)
    print(f"\n[Incoming Request]: \"{user_request}\"")

    thread_id = f"session-{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = create_task_graph(checkpointer=MemorySaver())

    print("\n>>> Running Supervisor and Research...")
    graph.invoke({"user_request": user_request}, config=config)

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
            if auto_decision == "reject_once":
                decision = "rejected"
                auto_decision = "approved"
                print(f"[Automated Decision]: REJECTED (Simulating human rejection)")
            elif auto_decision:
                decision = auto_decision
                print(f"[Automated Decision]: {decision.upper()}")
            else:
                try:
                    user_choice = input("\nDo you approve this action? ([A]pprove / [R]eject): ").strip().lower()
                    if user_choice in {"a", "approve", "yes", "y"}:
                        decision = "approved"
                    elif user_choice in {"r", "reject", "no", "n"}:
                        decision = "rejected"
                    else:
                        print("Unrecognized response; defaulting safely to REJECT.")
                        decision = "rejected"
                except (EOFError, KeyboardInterrupt):
                    print("\nInput closed; defaulting safely to REJECT.")
                    decision = "rejected"

            if decision == "rejected":
                print("\n>>> Proposal rejected. Routing back to Planning Agent for alternative options...")
                graph.invoke(Command(resume="rejected"), config=config)
                # If auto-decision was provided, switch to approve on next cycle so demo concludes
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
    print("  FINAL RUN SUMMARY")
    print("=" * 65)
    if final_summary and "text" in final_summary:
        print(final_summary["text"])
    else:
        print(final_state.values)
    print("=" * 65 + "\n")


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="AI Personal Task Executor CLI")
    parser.add_argument(
        "--request",
        "-r",
        type=str,
        help="Custom productivity request to run",
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
    print("1. Primary Demo: Research + Plan + Approve + Schedule Cafe Event")
    print("2. Variant 1: Direct Calendar Scheduling (Schedule meeting with Rahul)")
    print("3. Variant 2: Research & Save Note (Find cafes & save Markdown note)")
    print("4. Re-planning Demo (Reject first proposal -> Plan alternative -> Approve)")
    print("5. Enter Custom Request")
    print("=" * 65)

    try:
        choice = input("\nEnter choice (1-5) [Default: 1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if choice == "2":
        run_task("Schedule a meeting with Rahul tomorrow at 5 PM", auto_decision="approved" if args.auto_approve else None)
    elif choice == "3":
        run_task("Find 3 good cafes in Indiranagar and save the options", auto_decision="approved" if args.auto_approve else None)
    elif choice == "4":
        run_task("Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar", auto_decision="reject_once")
    elif choice == "5":
        try:
            custom_req = input("\nEnter your request: ").strip()
        except (EOFError, KeyboardInterrupt):
            custom_req = ""
        if custom_req:
            run_task(custom_req, auto_decision="approved" if args.auto_approve else None)
        else:
            print("No request entered.")
    else:
        # Default: 1
        run_task(
            "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar",
            auto_decision="approved" if args.auto_approve else None,
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CLI entrypoint for running jcode through AgentGUI's runner without the server.

Examples:
    python3 tools/run_jcode_cli.py /path/to/repo "Add a README"
    python3 tools/run_jcode_cli.py /path/to/repo "Add a README" --model glm-5.2 --tool-profile minimal --timeout 300
    python3 -m core.jcode_runner /path/to/repo "Add a README" --model qwen2.5-coder:7b
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is importable when run as script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.jcode_runner import run_jcode, get_jcode_status, kill_jcode_run


def main():
    parser = argparse.ArgumentParser(description="Run jcode via AgentGUI runner from the terminal.")
    parser.add_argument("repo_path", help="Path to the repository/workspace")
    parser.add_argument("task", help="Task/prompt to pass to jcode")
    parser.add_argument("--model", "-m", default=None, help="AgentGUI model ID (mapped to jcode model)")
    parser.add_argument("--tool-profile", "-t", default=None, help="jcode tool profile (minimal/full/none)")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default 600)")
    parser.add_argument("--poll", type=float, default=1.0, help="Poll interval for status in seconds (default 1.0)")
    parser.add_argument("--no-follow", action="store_true", help="Start run and print run_id without waiting")
    args = parser.parse_args()

    run_id = run_jcode(
        repo_path=args.repo_path,
        task=args.task,
        model=args.model,
        tool_profile=args.tool_profile,
        timeout=args.timeout,
    )
    print(f"[run_id] {run_id}")

    if args.no_follow:
        return

    try:
        while True:
            state = get_jcode_status(run_id)
            if not state:
                print("[error] run state disappeared", file=sys.stderr)
                sys.exit(1)
            # Print any new stdout/stderr since last poll by reading the log file
            log_file = Path(state.get("log_file", "")) if state.get("log_file") else None
            if log_file and log_file.exists():
                text = log_file.read_text(encoding="utf-8", errors="replace")
                print(text, end="")
            if state.get("status") in {"completed", "error", "cancelled"}:
                rc = state.get("returncode")
                print(f"\n[exit: {rc}, status={state['status']}]")
                sys.exit(rc if rc is not None else 1)
            time.sleep(args.poll)
    except KeyboardInterrupt:
        print("\n[interrupt] killing jcode run...")
        kill_jcode_run(run_id)
        time.sleep(1)
        state = get_jcode_status(run_id)
        print(f"[exit: {state.get('returncode')}, status={state.get('status')}]")
        sys.exit(130)


if __name__ == "__main__":
    main()

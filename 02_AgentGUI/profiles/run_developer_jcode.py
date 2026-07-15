#!/usr/bin/env python3
"""
AgentGUI Profile Runner — developer via jcode.

Reads the task file created by dispatch_task, delegates execution to
jcode_runner.run_jcode, forwards stdout/stderr in real time, and writes
the done flag when finished.
"""

import sys
import os
import json
import time
import signal
from pathlib import Path

# --- Auto-injected Global Logger ---
try:
    from core.logger_config import setup_global_logging
    setup_global_logging(str(Path(__file__).parent.parent / "logs"))
except Exception as e:
    print(f"Failed to initialize logger: {e}")
# -------------------------------------

BASE_DIR = Path(os.environ.get("AGENTUI_DIR", "/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI"))
DATA_DIR = BASE_DIR / "data"
PROFILE_NAME = "developer"

# Ensure project root is importable
sys.path.insert(0, str(BASE_DIR))
from core.jcode_runner import run_jcode, get_jcode_status, kill_jcode_run


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 run_developer_jcode.py <agent_id>")
        sys.exit(1)

    agent_id = sys.argv[1]
    task_file = DATA_DIR / f"{agent_id}_task.json"
    done_flag = DATA_DIR / f"{agent_id}_done.flag"

    if not task_file.exists():
        print(f"[{agent_id}] Task file nao encontrado: {task_file}")
        done_flag.write_text("1")
        sys.exit(1)

    task_data = json.loads(task_file.read_text())
    goal = task_data.get("goal", "")
    model = task_data.get("model")
    repo_path = task_data.get("repo_path") or "/media/sf_AI_Ecosystem/10_Projects/"
    tool_profile = task_data.get("tool_profile")
    timeout = int(task_data.get("timeout", 600))

    print(f"[{agent_id}] Profile: {PROFILE_NAME} (jcode path)")
    print(f"[{agent_id}] Model: {model or 'default'}")
    print(f"[{agent_id}] Repo: {repo_path}")
    print(f"[{agent_id}] Task: {goal[:100]}...")

    run_id = run_jcode(
        repo_path=repo_path,
        task=goal,
        model=model,
        tool_profile=tool_profile,
        timeout=timeout,
        agent_id=agent_id,
    )
    print(f"[{agent_id}] jcode run_id: {run_id}")

    last_len = 0
    returncode = None
    try:
        while True:
            state = get_jcode_status(run_id)
            if not state:
                print(f"[{agent_id}] Run state desapareceu")
                returncode = 1
                break

            log_file = Path(state.get("log_file", "")) if state.get("log_file") else None
            if log_file and log_file.exists():
                text = log_file.read_text(encoding="utf-8", errors="replace")
                if len(text) > last_len:
                    chunk = text[last_len:]
                    print(chunk, end="")
                    last_len = len(text)

            status = state.get("status")
            if status in {"completed", "error", "cancelled"}:
                returncode = state.get("returncode", 1 if status != "completed" else 0)
                break

            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n[{agent_id}] Interrompido pelo utilizador. A cancelar jcode...")
        kill_jcode_run(run_id)
        time.sleep(1)
        state = get_jcode_status(run_id)
        returncode = state.get("returncode", 130)

    # Write result.json for loop closure (FASE 2)
    from datetime import datetime
    result_data = {
        "agent_id": agent_id,
        "profile": PROFILE_NAME,
        "exit_code": returncode,
        "output": f"[jcode run_id={run_id}] exit={returncode}. See jcode log for full output.",
        "duration": "jcode",
        "timestamp": datetime.now().isoformat()
    }
    result_file = DATA_DIR / f"{agent_id}_result.json"
    result_file.write_text(json.dumps(result_data, indent=2, ensure_ascii=False))

    # FASE 4: Send result via message bus
    try:
        sys.path.insert(0, str(BASE_DIR))
        from core.message_bus import send_message
        caller = task_data.get("caller_profile", "orchestrator")
        send_message(
            from_profile=PROFILE_NAME,
            to_profile=caller,
            content=result_data["output"][:2000],
            msg_type="result",
            task_id=agent_id,
        )
    except Exception as mb_e:
        print(f"[{agent_id}] message_bus send failed: {mb_e}")

    done_flag.write_text(str(returncode))
    if returncode == 0:
        print(f"\n[{agent_id}] Tarefa concluida")
    else:
        print(f"\n[{agent_id}] Tarefa terminou com erro (exit {returncode})")


if __name__ == "__main__":
    main()

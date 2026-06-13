"""
AgentGUI Core — Centralized JSON state manager.
Tracks agent lifecycle: queued → running → completed | error.
"""

import json
import time
import threading
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

STATE_FILE = Path(__file__).parent.parent / "data" / "agent_state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

def _ensure_file():
    if not STATE_FILE.exists():
        _write_state({"agents": {}, "last_update": datetime.now().isoformat()})

def _read_state() -> dict:
    _ensure_file()
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def _write_state(state: dict):
    state["last_update"] = datetime.now().isoformat()
    with _lock:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

def register_agent(agent_id: str, profile: str, goal: str, command: str) -> dict:
    """Register a new agent run."""
    state = _read_state()
    state["agents"][agent_id] = {
        "id": agent_id,
        "profile": profile,
        "goal": goal,
        "command": command,
        "status": "queued",
        "progress": 0,
        "message": "Aguardo lançamento...",
        "output": "",
        "error": None,
        "started_at": None,
        "finished_at": None,
        "pid": None,
        "tmux_session": f"agentgui_{agent_id}"
    }
    _write_state(state)
    return state["agents"][agent_id]

def update_agent(agent_id: str, status: Optional[str] = None,
                 progress: Optional[int] = None,
                 message: Optional[str] = None,
                 output_append: Optional[str] = None,
                 error: Optional[str] = None,
                 pid: Optional[int] = None) -> Optional[dict]:
    """
    Atomically update an agent's state.
    Use output_append to append to the output buffer (truncated at 10k chars).
    """
    state = _read_state()
    if agent_id not in state["agents"]:
        return None

    agent = state["agents"][agent_id]

    if status is not None:
        agent["status"] = status
        if status == "running" and agent["started_at"] is None:
            agent["started_at"] = datetime.now().isoformat()
        if status in ("completed", "error", "cancelled"):
            agent["finished_at"] = datetime.now().isoformat()

    if progress is not None:
        agent["progress"] = max(0, min(100, progress))

    if message is not None:
        agent["message"] = message

    if output_append is not None:
        agent["output"] = (agent.get("output", "") + output_append)[-10000:]

    if error is not None:
        agent["error"] = error
        agent["status"] = "error"

    if pid is not None:
        agent["pid"] = pid

    _write_state(state)
    return agent

def get_agent(agent_id: str) -> Optional[dict]:
    state = _read_state()
    return state["agents"].get(agent_id)

def list_agents(profile_filter: Optional[str] = None, status_filter: Optional[str] = None) -> list:
    state = _read_state()
    agents = list(state["agents"].values())
    if profile_filter:
        agents = [a for a in agents if a["profile"] == profile_filter]
    if status_filter:
        agents = [a for a in agents if a["status"] == status_filter]
    # Sort by started_at descending, then by id
    return sorted(agents, key=lambda a: (a.get("started_at") or "", a["id"]), reverse=True)

def cleanup_old_agents(max_age_hours: int = 24) -> int:
    """Remove agents older than max_age_hours that are finished. Returns count removed."""
    state = _read_state()
    now = datetime.now()
    removed = 0
    for agent_id in list(state["agents"].keys()):
        agent = state["agents"][agent_id]
        if agent["status"] in ("completed", "error", "cancelled"):
            finished = agent.get("finished_at")
            if finished:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(finished)
                    if (now - dt).total_seconds() > max_age_hours * 3600:
                        del state["agents"][agent_id]
                        removed += 1
                except ValueError:
                    pass
    _write_state(state)
    return removed

def get_last_update_timestamp() -> str:
    state = _read_state()
    return state.get("last_update", "")

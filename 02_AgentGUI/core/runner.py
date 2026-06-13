"""
AgentGUI Core — tmux-based agent launcher and lifecycle manager.
"""

import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, Dict
from .state import register_agent, update_agent, get_agent

TMUX_PREFIX = "agentgui_"

def _tmux_cmd(*args) -> str:
    """Execute a tmux command and return stdout."""
    result = subprocess.run(
        ["tmux"] + list(args),
        capture_output=True,
        text=True
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def _session_exists(session_name: str) -> bool:
    """Check if a tmux session exists."""
    _, _, rc = _tmux_cmd("has-session", "-t", session_name)
    return rc == 0

def launch_agent(profile: str, goal: str, prompt: str, agent_id: str = None, timeout_minutes: int = 30) -> Dict:
    """
    Launch a new Hermes agent via tmux.
    If agent_id is provided, uses it (must already be registered in state).
    Otherwise generates a new one.
    Returns the agent dict.
    """
    if agent_id is None:
        agent_id = f"{profile}_{uuid.uuid4().hex[:8]}"
    session_name = f"{TMUX_PREFIX}{agent_id}"
    profile_dir = Path.home() / ".hermes" / "profiles" / profile
    soul_file = profile_dir / "SOUL.md"

    # Build the command to run inside tmux
    runner_script = Path(__file__).parent.parent / "profiles" / f"run_{profile}.py"

    if runner_script.exists():
        cmd = f"cd {Path(__file__).parent.parent} && python3 {runner_script} {agent_id}"
    else:
        # Fallback: run hermes chat with prompt
        log_file = Path(__file__).parent.parent / 'data' / f'{agent_id}.log'
        escaped_prompt = prompt.replace("'", "'\\''")
        cmd = (
            f"export AGENT_ID={agent_id} AGENTUI_DIR={Path(__file__).parent.parent} "
            f"&& cat {soul_file} | hermes chat -q '{escaped_prompt}' "
            f"> {log_file} 2>&1"
        )

    # Create tmux session and run command
    _, err, rc = _tmux_cmd("new-session", "-d", "-s", session_name, "-x", "120", "-y", "40", cmd)

    if rc != 0:
        return {
            "error": f"Failed to create tmux session: {err}",
            "agent_id": agent_id
        }

    # Get PID of the tmux session
    pid, _, _ = _tmux_cmd("list-panes", "-t", session_name, "-F", "#{pane_pid}")
    try:
        pid = int(pid)
    except ValueError:
        pid = None

    # Update state to running
    update_agent(agent_id, status="running", pid=pid, message="Agent lancado em tmux")

    return get_agent(agent_id) or {"agent_id": agent_id, "error": "Agent not found in state"}


def get_agent_output(agent_id: str, lines: int = 100) -> str:
    """Capture last N lines from the tmux session."""
    session_name = f"{TMUX_PREFIX}{agent_id}"
    if not _session_exists(session_name):
        agent = get_agent(agent_id)
        if agent and agent.get("output"):
            return agent["output"]
        return "[Sessão tmux não encontrada — pode ter terminado]"

    out, err, rc = _tmux_cmd("capture-pane", "-t", session_name, "-p", "-S", f"-{lines}")
    if rc != 0:
        return f"[Erro ao capturar output: {err}]"
    return out

def send_keys_to_agent(agent_id: str, text: str) -> bool:
    """Send keystrokes to a running agent in tmux (for interaction)."""
    session_name = f"{TMUX_PREFIX}{agent_id}"
    if not _session_exists(session_name):
        return False

    _, err, rc = _tmux_cmd("send-keys", "-t", session_name, *text.split(" "), "Enter")
    return rc == 0

def kill_agent(agent_id: str) -> bool:
    """Force-kill a tmux session."""
    session_name = f"{TMUX_PREFIX}{agent_id}"
    if not _session_exists(session_name):
        # Already gone
        update_agent(agent_id, status="cancelled", message="Agent cancelado (sessão já inexistente)")
        return True

    _, err, rc = _tmux_cmd("kill-session", "-t", session_name)
    if rc == 0:
        update_agent(agent_id, status="cancelled", message="Agent cancelado pelo utilizador")
        return True
    return False

def get_running_sessions() -> list:
    """List all agentgui tmux sessions currently active."""
    out, err, rc = _tmux_cmd("list-sessions", "-F", "#{session_name}")
    if rc != 0:
        return []
    return [s for s in out.split("\n") if s.startswith(TMUX_PREFIX)]

def sync_running_agents():
    """
    Background sync: mark agents as completed/error if tmux session is gone.
    Should be called periodically.
    """
    from .state import list_agents, update_agent

    running = get_running_sessions()
    active_ids = set(s.replace(TMUX_PREFIX, "") for s in running)

    for agent in list_agents(status_filter="running"):
        if agent["id"] not in active_ids:
            # Session gone — agent finished
            update_agent(
                agent_id=agent["id"],
                status="completed",
                message="Agent terminado",
                progress=100
            )

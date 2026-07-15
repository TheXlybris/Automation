"""
AgentGUI Core — Abstract Agent Interface (FASE 6).

Provides a unified interface for dispatching tasks to any agent —
Hermes profiles (via tmux) or external agents (Claude Code, Codex, etc).

Interface:
  - Agent.dispatch(task) → agent_id
  - Agent.status(agent_id) → status dict
  - Agent.result(agent_id) → result dict

Implementations:
  - HermesAgent: wraps the existing tmux-based launch_agent + runner.py
  - ClaudeCodeAgent: wrapper around `claude --print` CLI
  - CodexAgent: wrapper around `codex` CLI
  - GenericCLIAgent: generic wrapper for any CLI-based coding agent
"""

import json
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
REGISTRY_FILE = DATA_DIR / "agents_registry.json"


def load_registry() -> dict:
    """Load the agents registry."""
    if not REGISTRY_FILE.exists():
        return {"agents": []}
    try:
        return json.loads(REGISTRY_FILE.read_text())
    except Exception:
        return {"agents": []}


def save_registry(data: dict):
    """Save the agents registry."""
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def list_registered_agents() -> list:
    """Return all registered agents (Hermes profiles + external)."""
    return load_registry().get("agents", [])


def find_agent(agent_name: str) -> Optional[dict]:
    """Find an agent in the registry by name."""
    for a in load_registry().get("agents", []):
        if a["name"] == agent_name:
            return a
    return None


def register_agent_entry(name: str, agent_type: str, capabilities: list,
                         model: str = "", endpoint: str = "", command: str = "",
                         enabled: bool = True) -> dict:
    """Register or update an agent in the registry."""
    registry = load_registry()
    agents = registry.get("agents", [])
    # Remove existing with same name
    agents = [a for a in agents if a["name"] != name]
    entry = {
        "name": name,
        "type": agent_type,
        "capabilities": capabilities,
        "model": model,
        "endpoint": endpoint,
        "command": command,
        "enabled": enabled,
        "registered_at": datetime.now().isoformat(),
    }
    agents.append(entry)
    registry["agents"] = agents
    save_registry(registry)
    return entry


# ─── Abstract Interface ──────────────────────────────

class Agent(ABC):
    """Abstract agent interface."""

    @abstractmethod
    def dispatch(self, task: str, repo_path: str = None, timeout: int = 600) -> Dict:
        """Dispatch a task. Returns {agent_id, status}."""
        pass

    @abstractmethod
    def status(self, agent_id: str) -> Dict:
        """Get current status of a dispatched task."""
        pass

    @abstractmethod
    def result(self, agent_id: str) -> Dict:
        """Get the final result of a completed task."""
        pass

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Return the agent type identifier."""
        pass


# ─── Hermes Agent (existing tmux-based) ───────────────

class HermesAgent(Agent):
    """Wraps the existing Hermes profile dispatch via AgentGUI server."""

    def __init__(self, profile: str, server_url: str = "http://192.168.0.188:5020"):
        self.profile = profile
        self.server_url = server_url

    @property
    def agent_type(self) -> str:
        return "hermes"

    def dispatch(self, task: str, repo_path: str = None, timeout: int = 600) -> Dict:
        import requests
        payload = {
            "target_profile": self.profile,
            "task": task,
            "caller_profile": "orchestrator",
            "timeout": timeout,
        }
        if repo_path:
            payload["repo_path"] = repo_path
        resp = requests.post(f"{self.server_url}/api/dispatch", json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "agent_id": data.get("id", data.get("agent_id", "unknown")),
            "status": "running",
            "agent_type": self.agent_type,
            "profile": self.profile,
        }

    def status(self, agent_id: str) -> Dict:
        import requests
        resp = requests.get(f"{self.server_url}/api/agents", timeout=5)
        agents = resp.json()
        if isinstance(agents, dict):
            agents = agents.get("agents", [])
        for a in agents:
            if a.get("id") == agent_id:
                return {"agent_id": agent_id, "status": a.get("status", "unknown")}
        return {"agent_id": agent_id, "status": "unknown"}

    def result(self, agent_id: str) -> Dict:
        import requests
        resp = requests.get(f"{self.server_url}/api/agents/{agent_id}/result", timeout=10)
        return resp.json()


# ─── External CLI Agents ──────────────────────────────

class GenericCLIAgent(Agent):
    """Generic wrapper for any CLI-based agent (claude, codex, etc).

    Runs `<command> "<task>"` in a subprocess, captures output,
    writes result.json + done.flag (same pattern as Hermes runners).
    """

    def __init__(self, name: str, command: str, model: str = "",
                 repo_path: str = None, timeout: int = 600):
        self._name = name
        self._command = command
        self._model = model
        self._default_repo = repo_path
        self._timeout = timeout

    @property
    def agent_type(self) -> str:
        return "external_cli"

    def dispatch(self, task: str, repo_path: str = None, timeout: int = 600) -> Dict:
        agent_id = f"{self._name}_{uuid.uuid4().hex[:8]}"
        effective_timeout = timeout or self._timeout
        effective_repo = repo_path or self._default_repo or "."

        # Build command
        cmd_parts = self._command.split()
        if self._model:
            cmd_parts.extend(["--model", self._model])
        cmd_parts.append(task)

        # Write task file for compatibility with runner.py sync
        task_file = DATA_DIR / f"{agent_id}_task.json"
        task_data = {
            "id": agent_id,
            "profile": self._name,
            "goal": task,
            "model": self._model,
            "command": self._command,
            "caller_profile": "orchestrator",
            "created_at": datetime.now().isoformat(),
        }
        task_file.write_text(json.dumps(task_data, indent=2))

        # Launch in background via subprocess (non-blocking)
        # The actual execution happens in a thread or tmux session
        import threading
        thread = threading.Thread(
            target=self._run_cli,
            args=(agent_id, cmd_parts, effective_repo, effective_timeout),
            daemon=True,
        )
        thread.start()

        return {
            "agent_id": agent_id,
            "status": "running",
            "agent_type": self.agent_type,
            "profile": self._name,
        }

    def _run_cli(self, agent_id: str, cmd_parts: list, repo_path: str, timeout: int):
        """Run the CLI command and write result.json + done.flag."""
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=repo_path if Path(repo_path).exists() else None,
                stdin=subprocess.DEVNULL,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            output = f"[Timeout after {timeout}s]"
            exit_code = 1
        except FileNotFoundError:
            output = f"[Error: command not found: {cmd_parts[0]}]"
            exit_code = 127
        except Exception as e:
            output = f"[Error: {e}]"
            exit_code = 1

        duration = time.time() - start_time
        result_data = {
            "agent_id": agent_id,
            "profile": self._name,
            "exit_code": exit_code,
            "output": output,
            "duration": round(duration, 2),
            "timestamp": datetime.now().isoformat(),
        }
        result_file = DATA_DIR / f"{agent_id}_result.json"
        result_file.write_text(json.dumps(result_data, indent=2, ensure_ascii=False))

        # Write done flag for sync_running_agents
        done_flag = DATA_DIR / f"{agent_id}_done.flag"
        done_flag.write_text(str(exit_code))

        # Send via message bus
        try:
            from core.message_bus import send_message
            send_message(
                from_profile=self._name,
                to_profile="orchestrator",
                content=output[:2000],
                msg_type="result",
                task_id=agent_id,
            )
        except Exception:
            pass

    def status(self, agent_id: str) -> Dict:
        result_path = DATA_DIR / f"{agent_id}_result.json"
        done_path = DATA_DIR / f"{agent_id}_done.flag"
        if result_path.exists():
            return {"agent_id": agent_id, "status": "completed"}
        if not done_path.exists():
            return {"agent_id": agent_id, "status": "running"}
        return {"agent_id": agent_id, "status": "error"}

    def result(self, agent_id: str) -> Dict:
        result_path = DATA_DIR / f"{agent_id}_result.json"
        if result_path.exists():
            return json.loads(result_path.read_text())
        return {"agent_id": agent_id, "error": "No result yet"}


class ClaudeCodeAgent(GenericCLIAgent):
    """Claude Code CLI adapter."""

    def __init__(self, model: str = "", repo_path: str = None, timeout: int = 600):
        super().__init__(
            name="claude-code",
            command="claude --print",
            model=model,
            repo_path=repo_path,
            timeout=timeout,
        )

    @property
    def agent_type(self) -> str:
        return "claude_code"


class CodexAgent(GenericCLIAgent):
    """OpenAI Codex CLI adapter."""

    def __init__(self, model: str = "", repo_path: str = None, timeout: int = 600):
        super().__init__(
            name="codex",
            command="codex --quiet",
            model=model,
            repo_path=repo_path,
            timeout=timeout,
        )

    @property
    def agent_type(self) -> str:
        return "codex"


# ─── Factory ─────────────────────────────────────────

def create_agent(agent_name: str) -> Optional[Agent]:
    """Create an Agent instance from the registry.

    Returns None if agent not found or not enabled.
    """
    entry = find_agent(agent_name)
    if not entry or not entry.get("enabled", True):
        return None

    agent_type = entry.get("type", "hermes")

    if agent_type == "hermes":
        return HermesAgent(profile=entry["name"])

    elif agent_type in ("claude_code", "codex", "external_cli"):
        return GenericCLIAgent(
            name=entry["name"],
            command=entry.get("command", ""),
            model=entry.get("model", ""),
            repo_path=entry.get("endpoint", ""),  # reuse endpoint field for repo
            timeout=600,
        )

    return None


def route_task(task: str, preferred_agent: str = None) -> Optional[Agent]:
    """Route a task to the best available agent.

    If preferred_agent is specified and available, use it.
    Otherwise, use simple heuristics based on agent capabilities.
    """
    agents = list_registered_agents()
    enabled = [a for a in agents if a.get("enabled", True)]

    if preferred_agent:
        for a in enabled:
            if a["name"] == preferred_agent:
                return create_agent(a["name"])

    # Default: use first enabled Hermes agent (developer)
    for a in enabled:
        if a.get("type") == "hermes" and a["name"] == "developer":
            return create_agent("developer")

    # Fallback: first enabled agent
    if enabled:
        return create_agent(enabled[0]["name"])

    return None
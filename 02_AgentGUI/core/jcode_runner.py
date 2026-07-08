"""
jcode runner for AgentGUI — backend subprocess + Socket.IO streaming.

Can also be executed as a module for CLI parity:
    python3 -m core.jcode_runner /path/to/repo "task" [--model MODEL] [--tool-profile PROFILE]
"""

import os
import re
import json
import time
import uuid
import signal
import shutil
import subprocess
import threading
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

try:
    from flask_socketio import SocketIO
except ImportError:
    SocketIO = None

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
JCODE_MAP_FILE = PROJECT_ROOT / "config" / "jcode_model_map.json"
JCODE_RUNS_DIR = PROJECT_ROOT / "data" / "jcode"
JCODE_LOGS_DIR = PROJECT_ROOT / "logs" / "jcode"

JCODE_RUNS_DIR.mkdir(parents=True, exist_ok=True)
JCODE_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory run registry (PID + thread)
_jcode_runs: Dict[str, dict] = {}
_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jcode_map() -> dict:
    if not JCODE_MAP_FILE.exists():
        return {}
    try:
        return json.loads(JCODE_MAP_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_jcode_model(agentgui_model: str) -> tuple[str, str, str]:
    """
    Map an AgentGUI model ID to (jcode_model, provider_profile, tool_profile).
    Falls back to qwen2.5-coder:7b / ollama-local if not found.
    """
    cfg = load_jcode_map()
    models = cfg.get("models", {})
    fallback_model = cfg.get("fallback_model", "qwen2.5-coder:7b")
    default_tool = cfg.get("default_tool_profile", "minimal")

    entry = models.get(agentgui_model)
    if not entry:
        # Try stripping :cloud suffix or adding it
        if agentgui_model.endswith(":cloud"):
            entry = models.get(agentgui_model.replace(":cloud", ""))
        else:
            entry = models.get(agentgui_model + ":cloud")

    if entry:
        jcode_model = entry.get("jcode_model", agentgui_model)
        provider = entry.get("provider_profile", cfg.get("local_provider_profile", "ollama-local"))
    else:
        jcode_model = agentgui_model
        # Auto-detect provider by cloud suffix
        cloud_suffix = cfg.get("cloud_suffix", ":cloud")
        if cloud_suffix and jcode_model.endswith(cloud_suffix):
            provider = cfg.get("cloud_provider_profile", "ollama-cloud")
        else:
            provider = cfg.get("local_provider_profile", "ollama-local")

    # Validate model is known to jcode; otherwise fallback
    known_models = {m.get("jcode_model") for m in models.values()}
    if jcode_model not in known_models and agentgui_model not in known_models:
        jcode_model = fallback_model
        provider = cfg.get("local_provider_profile", "ollama-local")

    return jcode_model, provider, default_tool


def sanitize_repo_path(repo_path: str) -> Path:
    """Ensure repo_path is under one of the allowed roots."""
    cfg = load_jcode_map()
    allowed = cfg.get("allowed_repo_roots", [str(PROJECT_ROOT.parent / "10_Projects"), str(Path.home() / "projects")])
    target = Path(repo_path).resolve()
    for root in allowed:
        root_p = Path(root).resolve()
        if target == root_p or str(target).startswith(str(root_p) + os.sep):
            return target
    raise ValueError(f"repo_path {repo_path} is outside allowed roots: {allowed}")


def _mask_secrets(text: str) -> str:
    """Mask API keys and tokens in streamed output."""
    if not text:
        return text
    # Mask common key patterns
    patterns = [
        (r'(api[_-]?key\s*[:=]\s*)["\']?[a-zA-Z0-9_\-]{20,}["\']?', r'\1***'),
        (r'(Authorization\s*[:=]\s*[Bb]earer\s+)[a-zA-Z0-9_\-.]{20,}', r'\1***'),
        (r'(sk-[a-zA-Z0-9]{20,})', r'***'),
    ]
    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text)
    return text


def _emit_chunk(run_id: str, chunk: str, socketio: Optional[SocketIO] = None, on_chunk=None):
    """Emit a stream chunk via Socket.IO and/or callback."""
    with _lock:
        run = _jcode_runs.get(run_id)
        if run:
            run.setdefault("chunks", []).append(chunk)
            # Keep chunks bounded in memory; full log is on disk.
            if len(run["chunks"]) > 5000:
                run["chunks"] = run["chunks"][-4000:]
    if socketio:
        try:
            socketio.emit("jcode_stream", {"run_id": run_id, "chunk": _mask_secrets(chunk)}, broadcast=True)
        except Exception:
            pass
    if on_chunk:
        try:
            on_chunk(run_id, chunk)
        except Exception:
            pass
    if _chunk_callback:
        try:
            _chunk_callback(run_id, chunk)
        except Exception:
            pass


# Global optional callbacks for alternative transports (e.g. native WebSocket)
_status_callback = None
_chunk_callback = None

def set_status_callback(fn):
    global _status_callback
    _status_callback = fn

def set_chunk_callback(fn):
    global _chunk_callback
    _chunk_callback = fn


def _emit_status(run_id: str, state: dict, socketio: Optional[SocketIO] = None):
    """Emit a status change event via Socket.IO."""
    if socketio:
        try:
            payload = {
                "run_id": run_id,
                "status": state.get("status"),
                "returncode": state.get("returncode"),
                "updated_at": state.get("updated_at"),
                "repo_path": state.get("repo_path"),
                "jcode_model": state.get("jcode_model"),
                "agent_id": state.get("agent_id"),
            }
            socketio.emit("jcode_status", payload, broadcast=True)
        except Exception:
            pass
    if _status_callback:
        try:
            _status_callback(run_id, dict(state))
        except Exception:
            pass


def _save_run_state(run_id: str, state: dict):
    run_file = JCODE_RUNS_DIR / f"{run_id}.json"
    run_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def run_jcode(
    repo_path: str,
    task: str,
    model: Optional[str] = None,
    tool_profile: Optional[str] = None,
    timeout: int = 600,
    agent_id: Optional[str] = None,
    socketio: Optional[SocketIO] = None,
    on_chunk=None,
) -> str:
    """
    Launch a jcode run in a background thread and return the run_id.
    """
    run_id = f"jcode_{uuid.uuid4().hex[:10]}"
    if agent_id:
        run_id = f"{agent_id}_{run_id}"

    cfg = load_jcode_map()
    jcode_model, provider_profile, default_tool = resolve_jcode_model(model or "")
    tool_profile = tool_profile or default_tool

    repo = sanitize_repo_path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(f"repo_path does not exist: {repo}")
    if not repo.is_dir():
        raise NotADirectoryError(f"repo_path is not a directory: {repo}")

    # Resolve jcode binary path (server may not have ~/.local/bin in PATH)
    jcode_bin = "jcode"
    for candidate in [
        os.path.expanduser("~/.local/bin/jcode"),
        os.path.expanduser("~/.jcode/current/jcode"),
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            jcode_bin = candidate
            break

    cmd = [jcode_bin, "run", "--provider-profile", provider_profile]
    if jcode_model:
        cmd.extend(["--model", jcode_model])
    if tool_profile:
        cmd.extend(["--tool-profile", tool_profile])
    cmd.append(task)

    env = os.environ.copy()
    # jcode uses JCODE_OLLAMA_API_KEY; copy from OLLAMA_API_KEY if set
    if not env.get("JCODE_OLLAMA_API_KEY") and env.get("OLLAMA_API_KEY"):
        env["JCODE_OLLAMA_API_KEY"] = env["OLLAMA_API_KEY"]

    log_file = JCODE_LOGS_DIR / f"{run_id}.log"
    state = {
        "run_id": run_id,
        "agent_id": agent_id,
        "repo_path": str(repo),
        "task": task,
        "agentgui_model": model,
        "jcode_model": jcode_model,
        "provider_profile": provider_profile,
        "tool_profile": tool_profile,
        "status": "running",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "chunks": [],
        "log_file": str(log_file),
    }
    _save_run_state(run_id, state)
    with _lock:
        _jcode_runs[run_id] = state

    def _reader(pipe, key: str):
        try:
            for line in iter(pipe.readline, b""):
                decoded = line.decode("utf-8", errors="replace")
                with _lock:
                    state[key] += decoded
                _emit_chunk(run_id, decoded, socketio, on_chunk)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(decoded)
        finally:
            pipe.close()

    def _run():
        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(repo),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                bufsize=1,
            )
            with _lock:
                state["pid"] = proc.pid

            t_out = threading.Thread(target=_reader, args=(proc.stdout, "stdout"), daemon=True)
            t_err = threading.Thread(target=_reader, args=(proc.stderr, "stderr"), daemon=True)
            t_out.start()
            t_err.start()

            try:
                returncode = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                returncode = -1
                state["stderr"] += f"\n[jcode timed out after {timeout}s]\n"

            t_out.join(timeout=5)
            t_err.join(timeout=5)

            state["status"] = "completed" if returncode == 0 else "error"
            state["returncode"] = returncode
            state["updated_at"] = _now_iso()

        except Exception as e:
            state["status"] = "error"
            state["returncode"] = -2
            state["stderr"] += f"\n[runner error: {e}]\n"
            state["updated_at"] = _now_iso()
        finally:
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            _emit_chunk(run_id, f"\n[jcode finished: status={state['status']}, returncode={state['returncode']}]\n", socketio, on_chunk)
            _emit_status(run_id, state, socketio)
            _save_run_state(run_id, state)
            with _lock:
                _jcode_runs[run_id] = state

    threading.Thread(target=_run, daemon=True).start()
    return run_id


def get_jcode_status(run_id: str) -> Optional[dict]:
    with _lock:
        state = _jcode_runs.get(run_id)
    if state:
        return dict(state)
    run_file = JCODE_RUNS_DIR / f"{run_id}.json"
    if run_file.exists():
        try:
            return json.loads(run_file.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def kill_jcode_run(run_id: str, socketio: Optional[SocketIO] = None) -> bool:
    with _lock:
        state = _jcode_runs.get(run_id)
    if not state:
        # Try loading from disk in case process died but state exists
        state = get_jcode_status(run_id)
        if not state:
            return False
    pid = state.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            # Recheck status from in-memory copy if still running
            with _lock:
                live = _jcode_runs.get(run_id)
            if live and live.get("status") == "running":
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            pass
    state["status"] = "cancelled"
    state["returncode"] = -1
    state["updated_at"] = _now_iso()
    state["stderr"] += "\n[jcode run cancelled by user]\n"
    _save_run_state(run_id, state)
    with _lock:
        _jcode_runs[run_id] = state
    _emit_status(run_id, state, socketio)
    return True


def list_jcode_runs(agent_id: Optional[str] = None) -> list:
    """List persisted jcode runs, optionally filtered by agent_id prefix."""
    runs = []
    for run_file in sorted(JCODE_RUNS_DIR.glob("*.json"), reverse=True):
        try:
            run = json.loads(run_file.read_text(encoding="utf-8"))
            if agent_id is None or run.get("agent_id") == agent_id or run.get("run_id", "").startswith(agent_id):
                runs.append(run)
        except Exception:
            pass
    return runs


def summarize_run(run: dict) -> dict:
    """Return a compact summary of a jcode run for frontend lists."""
    created = run.get("created_at", "")
    updated = run.get("updated_at", "")
    duration = None
    if created and updated:
        try:
            t0 = datetime.fromisoformat(created.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            duration = max(0, int((t1 - t0).total_seconds()))
        except Exception:
            pass
    stdout = run.get("stdout", "")
    # Extract first non-empty line up to 120 chars
    preview = ""
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped:
            preview = stripped[:120]
            break
    # Count file operation markers written by jcode
    writes = stdout.count("[write]") + stdout.count("[edit]") + stdout.count("[apply]")
    return {
        "run_id": run.get("run_id"),
        "agent_id": run.get("agent_id"),
        "status": run.get("status"),
        "returncode": run.get("returncode"),
        "repo_path": run.get("repo_path"),
        "jcode_model": run.get("jcode_model"),
        "tool_profile": run.get("tool_profile"),
        "preview": preview,
        "duration_seconds": duration,
        "file_ops": writes,
        "created_at": created,
        "updated_at": updated,
    }


def list_jcode_run_summaries(agent_id: Optional[str] = None, limit: int = 50) -> list:
    """List compact summaries of jcode runs, newest first."""
    runs = list_jcode_runs(agent_id=agent_id)
    return [summarize_run(r) for r in runs[:limit]]


def _cli_main():
    """Module-level CLI: python3 -m core.jcode_runner ..."""
    parser = argparse.ArgumentParser(description="Run jcode via AgentGUI runner.")
    parser.add_argument("repo_path", help="Path to the repository/workspace")
    parser.add_argument("task", help="Task/prompt to pass to jcode")
    parser.add_argument("--model", "-m", default=None, help="AgentGUI model ID")
    parser.add_argument("--tool-profile", "-t", default=None, help="jcode tool profile")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds")
    parser.add_argument("--poll", type=float, default=1.0, help="Status poll interval")
    parser.add_argument("--no-follow", action="store_true", help="Start run and print run_id")
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

    last_len = 0
    try:
        while True:
            state = get_jcode_status(run_id)
            if not state:
                print("[error] run state disappeared", file=sys.stderr)
                sys.exit(1)
            log_file = Path(state.get("log_file", "")) if state.get("log_file") else None
            if log_file and log_file.exists():
                text = log_file.read_text(encoding="utf-8", errors="replace")
                if len(text) > last_len:
                    sys.stdout.write(text[last_len:])
                    sys.stdout.flush()
                    last_len = len(text)
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
    _cli_main()

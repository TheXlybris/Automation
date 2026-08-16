#!/usr/bin/env python3
"""
AgentGUI Server v3.0 — Flask + Socket.IO + Orchestrator + Cron + Real Model Selection.

Reconstructed 2026-06-24 with working model selection (frontend → backend → runner → hermes chat -m MODEL).
"""

import os
import sys
import json
import time
import uuid
import subprocess
import threading
import requests as _requests
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

from flask import Flask, jsonify, request, send_from_directory, send_file, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import psutil
try:
    import git
    HAS_GIT = True
except ImportError:
    HAS_GIT = False

# ─── Config ───────────────────────────────────────────
project_root = Path(__file__).parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

DATA_DIR = project_root / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load .env for OLLAMA_API_KEY
HERMES_ENV = Path.home() / ".hermes" / ".env"
if HERMES_ENV.exists():
    for line in HERMES_ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

app = Flask(__name__, static_folder='static', static_url_path='/')
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Error log (JSONL) ───────────────────────────────────
# ponytail: single errorhandler, append-only JSONL. No log rotation, no framework.
# Upgrade: rotate when file >10MB if disk matters.
from werkzeug.exceptions import HTTPException
import traceback as _tb

_ERROR_LOG = project_root / "logs" / "errors.jsonl"
_ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

@app.errorhandler(Exception)
def _log_unhandled(exc):
    if isinstance(exc, HTTPException):
        return exc  # let Flask handle 404/400 etc.
    # Category from URL prefix → agent can search_files by category
    path = request.path
    if "/api/video" in path: cat = "video"
    elif "/api/media" in path: cat = "media"
    elif "/api/agents" in path: cat = "agents"
    elif "/api/profiles" in path: cat = "profiles"
    elif "/api/cron" in path: cat = "cron"
    elif "/socket" in path: cat = "socket"
    else: cat = "other"
    entry = {
        "ts": datetime.now().isoformat(),
        "endpoint": path,
        "method": request.method,
        "category": cat,
        "error": str(exc),
        "traceback": _tb.format_exc(),
    }
    try:
        with open(_ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never crash the errorhandler
    return jsonify({"error": str(exc), "detail": _tb.format_exc()}), 500

@app.errorhandler(404)
def _log_404(exc):
    return jsonify({"error": "Not found", "path": request.path}), 404

# Import core modules
try:
    from core.state import (
        register_agent, update_agent, get_agent,
        list_agents, cleanup_old_agents, get_last_update_timestamp,
        delete_agent, delete_finished_agents
    )
    from core.runner import (
        launch_agent, get_agent_output, kill_agent,
        send_keys_to_agent, sync_running_agents
    )
    from core.jcode_runner import (
        run_jcode, get_jcode_status, kill_jcode_run, list_jcode_runs,
        load_jcode_map, resolve_jcode_model, list_jcode_run_summaries
    )
    from core.jcode_classifier import classify_task
except ImportError as e:
    print(f"Critical Error: Could not import core modules. {e}")

# ─── Profile Config (real model selection) ────────────
HERMES_PROFILES_DIR = Path.home() / ".hermes" / "profiles"
HERMES_SKILLS_DIR = Path.home() / ".hermes" / "skills"
BUNDLED_MANIFEST = HERMES_SKILLS_DIR / ".bundled_manifest"

def get_profile_config_path(profile_id: str) -> Path:
    return HERMES_PROFILES_DIR / profile_id / "agentgui_config.json"

def load_profile_config(profile_id: str) -> dict:
    p = get_profile_config_path(profile_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"model": None, "provider": None}

def _detect_provider(model_id: str) -> str:
    """Auto-detect provider from model ID suffix."""
    if not model_id:
        return None
    # Cloud suffixes: :cloud and -cloud
    if model_id.endswith(":cloud") or model_id.endswith("-cloud"):
        return "ollama-cloud"
    # Known cloud base names (without suffix)
    cloud_bases = {"kimi-k2.6", "glm-5.2", "deepseek-v4-pro", "qwen3-coder:480b",
                   "qwen3-vl:30b-a3b-instruct", "qwen3-vl:235b", "gpt-oss:120b"}
    base = model_id
    for suffix in (":cloud", "-cloud"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    if base in cloud_bases:
        return "ollama-cloud"
    return "ollama-local"

def save_profile_config(profile_id: str, config: dict):
    """Merge new config into existing config (preserves fields not in the update)."""
    profile_dir = HERMES_PROFILES_DIR / profile_id
    if not profile_dir.exists():
        raise ValueError(f"Profile '{profile_id}' does not exist. Cannot create profiles via API.")
    p = get_profile_config_path(profile_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Load existing config
    existing = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text())
        except Exception:
            pass
    # Merge: new values override existing, but existing values are preserved if not in new config
    merged = {**existing, **config}
    # Auto-detect provider whenever model is present — always recalculate to match current model
    if merged.get("model"):
        merged["provider"] = _detect_provider(merged["model"])
    p.write_text(json.dumps(merged, indent=2), encoding="utf-8")

def get_profile_skills_config_path(profile_id: str) -> Path:
    return HERMES_PROFILES_DIR / profile_id / "skills_config.json"

def load_skills_config(profile_id: str) -> dict:
    p = get_profile_skills_config_path(profile_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    # Auto-merge: all enabled by default
    all_skills = list_all_skills()
    return {"enabled": [s["name"] for s in all_skills], "disabled": []}

def save_skills_config(profile_id: str, config: dict):
    profile_dir = HERMES_PROFILES_DIR / profile_id
    if not profile_dir.exists():
        raise ValueError(f"Profile '{profile_id}' does not exist. Cannot create profiles via API.")
    p = get_profile_skills_config_path(profile_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2), encoding="utf-8")

def list_all_skills() -> list:
    """List all available skills from ~/.hermes/skills/ with category grouping."""
    skills = []
    # Check bundled manifest to distinguish builtin vs local
    builtin_names = set()
    if BUNDLED_MANIFEST.exists():
        for line in BUNDLED_MANIFEST.read_text().splitlines():
            if ":" in line:
                name = line.split(":")[0].strip()
                if name:
                    builtin_names.add(name)

    # Walk skills directory
    if HERMES_SKILLS_DIR.exists():
        for item in sorted(HERMES_SKILLS_DIR.iterdir()):
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            if item.is_dir():
                # Could be a category dir or a flat skill dir
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    # Flat skill (e.g., dogfood, yuanbao)
                    desc = extract_skill_description(skill_md)
                    skills.append({
                        "name": item.name,
                        "description": desc,
                        "source": "builtin" if item.name in builtin_names else "local"
                    })
                else:
                    # Category directory
                    for sub in sorted(item.iterdir()):
                        if sub.is_dir() and (sub / "SKILL.md").exists():
                            desc = extract_skill_description(sub / "SKILL.md")
                            skills.append({
                                "name": sub.name,
                                "description": desc,
                                "source": "builtin" if sub.name in builtin_names else "local"
                            })
    return skills

def extract_skill_description(skill_md_path: Path) -> str:
    try:
        content = skill_md_path.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            if line.strip() and not line.startswith("#") and not line.startswith("---") and not line.startswith("name:") and not line.startswith("category:"):
                return line.strip()[:120]
        return ""
    except Exception:
        return ""

def skills_grouped_by_category() -> dict:
    """Returns {category: [{name, description, source}, ...]}"""
    all_skills = list_all_skills()
    # Determine category from directory structure
    result = OrderedDict()
    if HERMES_SKILLS_DIR.exists():
        for item in sorted(HERMES_SKILLS_DIR.iterdir()):
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    # Flat skill — use "other" category
                    cat = "other"
                    s = next((x for x in all_skills if x["name"] == item.name), None)
                    if s:
                        result.setdefault(cat, []).append(s)
                else:
                    # Category dir
                    cat = item.name
                    for sub in sorted(item.iterdir()):
                        if sub.is_dir() and (sub / "SKILL.md").exists():
                            s = next((x for x in all_skills if x["name"] == sub.name), None)
                            if s:
                                result.setdefault(cat, []).append(s)
    return result

# ─── Model listing ────────────────────────────────────

OLLAMA_LOCAL_URL = "http://192.168.0.187:11434"

def list_models() -> dict:
    """Fetch available models from Ollama local + cloud defaults, deduped by base name."""
    models = []
    seen_base_names = set()

    # 1. Local Ollama
    try:
        r = _requests.get(f"{OLLAMA_LOCAL_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("models", []):
                name = m.get("name", "")
                if name.endswith(":latest"):
                    name = name.replace(":latest", "")
                # Track base name (strip :cloud / -cloud suffix) to dedup with cloud defaults
                base_name = name
                for suffix in (":cloud", "-cloud"):
                    if base_name.endswith(suffix):
                        base_name = base_name[: -len(suffix)]
                        break
                seen_base_names.add(base_name)
                models.append({
                    "id": m.get("name", ""),
                    "name": name,
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                    "source": "local"
                })
    except Exception:
        pass

    # 2. Cloud defaults — skip if local Ollama already has same base name
    cloud_defaults = [
        {"id": "kimi-k2.6", "name": "kimi-k2.6", "size": None, "source": "cloud"},
        {"id": "glm-5.2", "name": "glm-5.2", "size": None, "source": "cloud"},
        {"id": "deepseek-v4-pro", "name": "deepseek-v4-pro", "size": None, "source": "cloud"},
        {"id": "qwen3-coder:480b", "name": "qwen3-coder 480b", "size": None, "source": "cloud"},
        {"id": "qwen3.5:397b", "name": "qwen3.5 397b", "size": None, "source": "cloud"},
        {"id": "mistral-large-3:675b", "name": "mistral-large-3 675b", "size": None, "source": "cloud"},
        {"id": "minimax-m3", "name": "minimax-m3", "size": None, "source": "cloud"},
    ]
    for cm in cloud_defaults:
        if cm["id"] not in seen_base_names:
            models.append(cm)

    # Get default model from hermes config
    default_model = os.environ.get("HERMES_MODEL", "kimi-k2.6")
    return {"models": models, "default": default_model}

# ─── History ──────────────────────────────────────────

HISTORY_FILE = DATA_DIR / "history.json"

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return []

def save_history_entry(entry: dict):
    h = load_history()
    h.append(entry)
    HISTORY_FILE.write_text(json.dumps(h, indent=2, ensure_ascii=False))

# ─── Orchestrator state ───────────────────────────────

ORCH_INBOX_FILE = DATA_DIR / "orchestrator_inbox.json"
ORCH_STATE_FILE = DATA_DIR / "orchestrator_state.json"
ORCH_MODE_FILE = DATA_DIR / "orchestrator_mode.json"
ORCH_STATUS_CACHE = {"online": False, "mode": "brainstorm"}

def load_orch_inbox() -> list:
    if ORCH_INBOX_FILE.exists():
        try:
            return json.loads(ORCH_INBOX_FILE.read_text())
        except Exception:
            pass
    return []

def save_orch_inbox(inbox: list):
    ORCH_INBOX_FILE.write_text(json.dumps(inbox, indent=2), encoding="utf-8")

def load_orch_state() -> dict:
    if ORCH_STATE_FILE.exists():
        try:
            return json.loads(ORCH_STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_processed": 0, "processing": False}

def save_orch_state(state: dict):
    ORCH_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

# ─── Cron Tasks ───────────────────────────────────────

CRON_FILE = DATA_DIR / "cron_tasks.json"

def load_cron_tasks() -> list:
    if CRON_FILE.exists():
        try:
            return json.loads(CRON_FILE.read_text())
        except Exception:
            pass
    return []

def save_cron_tasks(tasks: list):
    CRON_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")

# ─── Windows resources ────────────────────────────────

windows_resources = {}
WINDOWS_RES_FILE = DATA_DIR / "windows_resources.json"

def load_windows_resources() -> dict:
    if WINDOWS_RES_FILE.exists():
        try:
            return json.loads(WINDOWS_RES_FILE.read_text())
        except Exception:
            pass
    return {}

# ─── Media temp ───────────────────────────────────────

MEDIA_TEMP_DIR = project_root / "temp"
MEDIA_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Clean temp on startup
for f in MEDIA_TEMP_DIR.iterdir():
    try:
        f.unlink()
    except Exception:
        pass

# ─── Media helpers ───────────────────────────────────

import mimetypes
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/webm", ".webm")
mimetypes.add_type("video/quicktime", ".mov")
mimetypes.add_type("audio/mpeg", ".mp3")
mimetypes.add_type("audio/wav", ".wav")

def _probe_duration(f):
    """ffprobe with 15s timeout (shared folders can be slow)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(f)],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
    except Exception:
        pass
    return None

def _human_size(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

# ─── REST API Routes ──────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "socket_io": True, "version": "3.0.0"})

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    full = app.static_folder / path
    if full.exists():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

# ── Agents ──

@app.route("/api/agents")
def api_list_agents():
    profile = request.args.get("profile")
    status = request.args.get("status")
    try:
        return jsonify(list_agents(profile_filter=profile, status_filter=status))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/launch", methods=["POST"])
def api_launch_agent():
    data = request.json or {}
    profile = data.get("profile", "developer")
    goal = data.get("goal", "")
    model = data.get("model")
    agent_id = data.get("id", f"{profile}_{uuid.uuid4().hex[:8]}")
    try:
        register_agent(agent_id, profile, goal, "")
        result = launch_agent(profile, goal, "", agent_id=agent_id, model=model)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/<agent_id>/output")
def api_agent_output(agent_id):
    lines = int(request.args.get("lines", 100))
    try:
        return jsonify({"output": get_agent_output(agent_id, lines)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/<agent_id>/result")
def api_agent_result(agent_id):
    """FASE 2: Return the full result of a completed agent (from result.json or state)."""
    try:
        # First try result.json on disk
        result_path = DATA_DIR / f"{agent_id}_result.json"
        if result_path.exists():
            import json as _json
            result = _json.loads(result_path.read_text())
            return jsonify(result)

        # Fallback: return what we have in agent state
        agent = get_agent(agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        return jsonify({
            "agent_id": agent_id,
            "profile": agent.get("profile", "?"),
            "status": agent.get("status", "unknown"),
            "exit_code": 0 if agent.get("status") == "completed" else 1,
            "output": agent.get("output", ""),
            "duration": "?",
            "timestamp": agent.get("finished_at", ""),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/<agent_id>/kill", methods=["POST"])
def api_kill_agent(agent_id):
    try:
        kill_agent(agent_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def api_delete_agent(agent_id):
    try:
        kill_agent(agent_id)  # kill if still running
        deleted = delete_agent(agent_id)
        if not deleted:
            return jsonify({"error": "Agent not found"}), 404
        socketio.emit("agents_updated", {"agents": list_agents()}, broadcast=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/delete_finished", methods=["POST"])
def api_delete_finished():
    try:
        count = delete_finished_agents()
        socketio.emit("agents_updated", {"agents": list_agents()}, broadcast=True)
        return jsonify({"deleted": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── History ──

@app.route("/api/history")
def api_history():
    return jsonify(load_history())

# ── Models (real listing) ──

@app.route("/api/models")
def api_models():
    return jsonify(list_models())

# ── Skills ──

@app.route("/api/skills")
def api_skills():
    profile = request.args.get("profile")
    cats = skills_grouped_by_category()
    return jsonify({"categories": cats})

@app.route("/api/profiles/<profile_id>/skills-config", methods=["GET", "POST"])
def api_skills_config(profile_id):
    if request.method == "GET":
        return jsonify(load_skills_config(profile_id))
    else:
        config = request.json or {}
        try:
            save_skills_config(profile_id, config)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        return jsonify({"success": True})

# ── Profile config (model selection — REAL) ──

@app.route("/api/profiles/<profile_id>/config", methods=["GET", "POST"])
def api_profile_config(profile_id):
    if request.method == "GET":
        return jsonify(load_profile_config(profile_id))
    else:
        config = request.json or {}
        try:
            save_profile_config(profile_id, config)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        # Also sync model to config.yaml so Hermes Dashboard picks it up
        _sync_model_to_config_yaml(profile_id, config)
        return jsonify({"success": True})

def _sync_model_to_config_yaml(profile_id: str, config: dict):
    """Write model+provider from agentgui_config into the profile's config.yaml."""
    import yaml as _yaml
    model = config.get("model")
    provider = config.get("provider", "ollama-cloud")
    if not model:
        return
    config_path = HERMES_PROFILES_DIR / profile_id / "config.yaml"
    data = {}
    if config_path.exists():
        try:
            data = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
    data.setdefault("model", {})
    data["model"]["default"] = model
    data["model"]["provider"] = provider
    data["model"].setdefault("base_url", "https://ollama.com/v1")
    data["model"].setdefault("context_length", 262144)
    config_path.write_text(_yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")

# ── Profile SOUL (system prompt editor) ──

def get_profile_soul_path(profile_id: str) -> Path:
    return HERMES_PROFILES_DIR / profile_id / "SOUL.md"

@app.route("/api/profiles/<profile_id>/soul", methods=["GET", "POST"])
def api_profile_soul(profile_id):
    soul_path = get_profile_soul_path(profile_id)
    if request.method == "GET":
        if soul_path.exists():
            return jsonify({"content": soul_path.read_text(encoding="utf-8"), "exists": True})
        return jsonify({"content": "", "exists": False})
    else:
        data = request.json or {}
        content = data.get("content", "")
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(content, encoding="utf-8")
        return jsonify({"success": True})

# ── Orchestrator ──

@app.route("/api/orchestrator/inbox")
def api_orch_inbox():
    return jsonify(load_orch_inbox())

@app.route("/api/orchestrator/response", methods=["POST"])
def api_orch_response():
    data = request.json or {}
    text = data.get("text", "") or data.get("message", "")
    profile = data.get("profile")
    inbox = load_orch_inbox()
    inbox.append({"text": text, "profile": profile, "time": datetime.now().isoformat()})
    save_orch_inbox(inbox)
    socketio.emit("orchestrator_message", {"text": text, "profile": profile})
    return jsonify({"success": True, "inbox_count": len(inbox)})

@app.route("/api/orchestrator/mark_processed", methods=["POST"])
def api_orch_mark_processed():
    data = request.json or {}
    count = data.get("count", 0)
    state = load_orch_state()
    state["last_processed"] = count
    save_orch_state(state)
    return jsonify({"success": True})

@app.route("/api/orchestrator/mode", methods=["GET", "POST"])
def api_orch_mode():
    if request.method == "POST":
        data = request.json or {}
        new_mode = data.get("mode", "brainstorm")
        ORCH_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ORCH_MODE_FILE.write_text(json.dumps({"mode": new_mode}))
        ORCH_STATUS_CACHE["mode"] = new_mode
        socketio.emit("orchestrator_status", ORCH_STATUS_CACHE)
        socketio.emit("orchestrator_mode_change", {"mode": new_mode})
        return jsonify({"success": True, "mode": new_mode})
    mode = "brainstorm"
    if ORCH_MODE_FILE.exists():
        try:
            mode = json.loads(ORCH_MODE_FILE.read_text()).get("mode", "brainstorm")
        except Exception:
            pass
    return jsonify({"mode": mode})

@app.route("/api/dispatch", methods=["POST"])
def api_dispatch():
    """REST fallback for dispatch_task (used by orchestrator agent and external callers)."""
    data = request.json or {}
    # Avoid emit inside REST context; call core logic directly if possible.
    result = _dispatch_task_impl(data)
    return jsonify(result)

@app.route("/api/orchestrator/state")
def api_orch_state():
    return jsonify(load_orch_state())

@app.route("/api/orchestrator/status")
def api_orch_status():
    mode = "brainstorm"
    if ORCH_MODE_FILE.exists():
        try:
            mode = json.loads(ORCH_MODE_FILE.read_text()).get("mode", "brainstorm")
        except Exception:
            pass
    # Also load current model from config
    orch_config = load_profile_config("orchestrator")
    return jsonify({
        "online": ORCH_STATUS_CACHE["online"],
        "mode": ORCH_STATUS_CACHE.get("mode", mode),
        "model": orch_config.get("model")
    })

# ── Cron Tasks ──

@app.route("/api/cron/tasks")
def api_cron_list():
    return jsonify(load_cron_tasks())

@app.route("/api/cron/tasks", methods=["POST"])
def api_cron_add():
    data = request.json or {}
    tasks = load_cron_tasks()
    task = {
        "id": uuid.uuid4().hex[:8],
        "profile": data.get("profile", "researcher"),
        "task": data.get("task", ""),
        "hour": int(data.get("hour", 12)),
        "minute": int(data.get("minute", 0)),
        "days": data.get("days", [0,1,2,3,4]),
        "repeat_type": data.get("repeat_type", "infinite"),
        "repeat_count": int(data.get("repeat_count", 1)),
        "runs_done": 0,
        "enabled": True,
        "created_at": datetime.now().isoformat()
    }
    tasks.append(task)
    save_cron_tasks(tasks)
    socketio.emit("cron_task_added", task)
    return jsonify(task)

@app.route("/api/cron/tasks/<task_id>", methods=["DELETE"])
def api_cron_delete(task_id):
    tasks = load_cron_tasks()
    tasks = [t for t in tasks if t["id"] != task_id]
    save_cron_tasks(tasks)
    socketio.emit("cron_task_removed", {"id": task_id})
    return jsonify({"success": True})

@app.route("/api/cron/tasks/<task_id>", methods=["PATCH"])
def api_cron_toggle(task_id):
    tasks = load_cron_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["enabled"] = not t.get("enabled", True)
            save_cron_tasks(tasks)
            socketio.emit("cron_task_toggled", t)
            return jsonify(t)
    return jsonify({"error": "not found"}), 404

# ── Resources ──

@app.route("/api/resources/windows", methods=["POST"])
def api_windows_resources():
    global windows_resources
    windows_resources = request.json or {}
    WINDOWS_RES_FILE.write_text(json.dumps(windows_resources, indent=2))
    return jsonify({"success": True})

# ── Media ──

@app.route("/api/media/upload", methods=["POST"])
def api_media_upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    dest = MEDIA_TEMP_DIR / f.filename
    f.save(str(dest))
    return jsonify({"success": True, "filename": f.filename})

@app.route("/api/media/list")
def api_media_list():
    files = []
    for f in sorted(MEDIA_TEMP_DIR.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            duration = _probe_duration(f)
            size = f.stat().st_size
            files.append({
                "name": f.name,
                "size": size,
                "size_human": _human_size(size),
                "duration": duration,
                "duration_human": f"{int(duration//60)}:{int(duration%60):02d}" if duration else None
            })
    return jsonify({"files": files})

@app.route("/api/media/file/<filename>")
def api_media_file(filename):
    f = MEDIA_TEMP_DIR / filename
    if not f.exists():
        return jsonify({"error": "not found"}), 404
    mime, _ = mimetypes.guess_type(str(f))
    if not mime:
        mime = "application/octet-stream"
    return send_file(str(f), mimetype=mime, conditional=True)

@app.route("/api/media/duration/<filename>")
def api_media_duration(filename):
    f = MEDIA_TEMP_DIR / filename
    if not f.exists():
        return jsonify({"error": "not found"}), 404
    duration = _probe_duration(f)
    if duration is not None:
        return jsonify({"duration": duration})
    return jsonify({"error": "ffprobe failed"}), 500

@app.route("/api/media/thumbnail/<filename>")
def api_media_thumbnail(filename):
    f = MEDIA_TEMP_DIR / filename
    if not f.exists():
        return jsonify({"error": "not found"}), 404
    thumb = MEDIA_TEMP_DIR / f"{filename}_thumb.jpg"
    if not thumb.exists():
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", "0.5", "-i", str(f), "-vframes", "1", "-q:v", "2", str(thumb)],
                capture_output=True, timeout=10
            )
        except Exception:
            pass
    if thumb.exists():
        return send_file(str(thumb), mimetype="image/jpeg")
    return jsonify({"error": "thumbnail failed"}), 500

@app.route("/api/media/delete/<filename>", methods=["DELETE"])
def api_media_delete(filename):
    f = MEDIA_TEMP_DIR / filename
    if f.exists():
        f.unlink()
    thumb = MEDIA_TEMP_DIR / f"{filename}_thumb.jpg"
    if thumb.exists():
        thumb.unlink()
    return jsonify({"success": True})

# ── Media Export (concat via FFmpeg with optional crossfade) ──

@app.route("/api/media/export", methods=["POST"])
def api_media_export():
    """Concatena clips da timeline num único ficheiro.
    Body: {"clips": [{"label": "file.mp4", "start": 0, "length": 5.0}, ...], "crossfade": 0.5}
    crossfade: duração em segundos do crossfade entre clips (default 0 = hard cut)
    """
    data = request.get_json(force=True)
    clips = data.get("clips", [])
    crossfade = float(data.get("crossfade", 0))
    if not clips:
        return jsonify({"error": "no clips"}), 400

    clips.sort(key=lambda c: c.get("start", 0))

    # Verificar ficheiros
    file_list = []
    for c in clips:
        fname = c.get("label", "")
        f = MEDIA_TEMP_DIR / fname
        if not f.exists():
            return jsonify({"error": f"file not found: {fname}"}), 404
        file_list.append(str(f))

    output_name = f"export_{int(time.time())}.mp4"
    output_path = MEDIA_TEMP_DIR / output_name

    if len(file_list) == 1 or crossfade <= 0:
        # Hard cut: concat demuxer (fast)
        list_file = MEDIA_TEMP_DIR / "_concat_list.txt"
        with open(list_file, "w") as lf:
            for fp in file_list:
                lf.write(f"file '{fp}'\n")
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                 "-c", "copy", str(output_path)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                     "-c:v", "libx264", "-c:a", "aac", "-preset", "fast", str(output_path)],
                    capture_output=True, text=True, timeout=600
                )
                if result.returncode != 0:
                    return jsonify({"error": "ffmpeg failed", "stderr": result.stderr[-500:]}), 500
        except subprocess.TimeoutExpired:
            return jsonify({"error": "timeout"}), 500
        list_file.unlink(missing_ok=True)
    else:
        # Crossfade: xfade filter chain
        # Build FFmpeg xfade chain: each transition overlaps by crossfade seconds
        # xfade=transition=fade:duration=X:offset=Y
        n = len(file_list)
        inputs = []
        for fp in file_list:
            inputs.extend(["-i", fp])

        # Get durations for offset calculation
        durations = []
        for fp in file_list:
            d = _probe_duration(Path(fp))
            durations.append(d if d else 5.0)

        # Build filter chain
        # ponytail: xfade chain O(n) filters, fine for <20 clips
        filter_parts = []
        prev_label = "[0:v]"
        cum_offset = 0.0
        for i in range(1, n):
            # offset = cumulative duration - crossfade (overlap)
            cum_offset += durations[i-1] - crossfade
            out_label = f"[v{i}]" if i < n-1 else "[vout]"
            filter_parts.append(
                f"{prev_label}[{i}]:v]xfade=transition=fade:duration={crossfade}:offset={cum_offset:.3f}{out_label}"
            )
            prev_label = f"[v{i}]"
        filter_complex = ";".join(filter_parts)

        # Audio: concat (crossfade only video, audio hard-cut for simplicity)
        audio_filter = ""
        if n > 1:
            audio_inputs = "".join(f"[{i}:a]" for i in range(n))
            audio_filter = f";{audio_inputs}concat=n={n}:v=0:a=1[aout]"

        full_filter = filter_complex + audio_filter
        cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", full_filter,
               "-map", "[vout]" if n > 1 else "[0:v]"]
        if audio_filter:
            cmd.extend(["-map", "[aout]"])
        else:
            cmd.extend(["-map", "0:a?"])
        cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-preset", "fast", str(output_path)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                return jsonify({"error": "ffmpeg xfade failed", "stderr": result.stderr[-800:]}), 500
        except subprocess.TimeoutExpired:
            return jsonify({"error": "timeout"}), 500

    return jsonify({"success": True, "filename": output_name, "url": f"/api/media/file/{output_name}"})

# ── ComfyUI Image Generation ──

COMFYUI_HOST = os.environ.get("COMFYUI_HOST", "http://192.168.0.187:8188")
WORKFLOWS_DIR = Path("/media/sf_AI_Ecosystem/03_Workflows/API")
COMFYUI_OUTPUT_DIR = Path("/media/sf_AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output")

# Workflow registry — maps frontend keys to workflow files + defaults
WORKFLOW_REGISTRY = {
    "fantasy": {
        "file": "Text2Image_Fantasy.json",
        "label": "Fantasy/Animation (SDXL)",
        "defaults": {"steps": 30, "cfg": 7, "width": 1024, "height": 576},
    },
    "realistic": {
        "file": "Text2Image.json",
        "label": "Realistic (SDXL)",
        "defaults": {"steps": 30, "cfg": 7, "width": 1024, "height": 576},
    },
}

@app.route("/api/image/workflows")
def api_image_workflows():
    """List available workflows with defaults."""
    workflows = []
    for key, info in WORKFLOW_REGISTRY.items():
        workflows.append({"key": key, "label": info["label"], "defaults": info["defaults"]})
    return jsonify(workflows)

@app.route("/api/image/generate", methods=["POST"])
def api_image_generate():
    """Submit a text2img workflow to ComfyUI."""
    data = request.json or {}
    wf_key = data.get("workflow", "realistic")
    wf_info = WORKFLOW_REGISTRY.get(wf_key, WORKFLOW_REGISTRY["realistic"])
    wf_path = WORKFLOWS_DIR / wf_info["file"]

    if not wf_path.exists():
        return jsonify({"error": f"Workflow file not found: {wf_path}"}), 500

    try:
        workflow = json.loads(wf_path.read_text(encoding="utf-8"))
    except Exception as e:
        return jsonify({"error": f"Failed to parse workflow: {e}"}), 500

    # Inject parameters into workflow nodes
    prompt_text = data.get("prompt", "")
    negative_text = data.get("negative", "text, watermark")
    width = int(data.get("width", wf_info["defaults"]["width"]))
    height = int(data.get("height", wf_info["defaults"]["height"]))
    steps = int(data.get("steps", wf_info["defaults"]["steps"]))
    cfg = float(data.get("cfg", wf_info["defaults"]["cfg"]))
    seed = int(data.get("seed", -1))
    batch_size = int(data.get("batch_size", 1))

    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)

    # Find nodes by class_type and inject
    for node_id, node in workflow.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})
        if ct == "CLIPTextEncode":
            # Node 6 = positive, Node 7 = negative (convention)
            if node_id == "6":
                # For fantasy workflow, prepend style modifiers to user prompt
                if wf_key == "fantasy":
                    inputs["text"] = "fantasy animation style, concept art, cartoon shading, whimsical, masterpiece, best quality, highly detailed, " + prompt_text
                else:
                    inputs["text"] = prompt_text
            elif node_id == "7":
                if wf_key == "fantasy":
                    inputs["text"] = negative_text if negative_text != "text, watermark" else "photorealistic, realistic, photo, photograph, 3d render, octane render, text, watermark, blurry, low quality, worst quality, deformed, ugly, realistic skin, real person"
                else:
                    inputs["text"] = negative_text
        elif ct == "EmptyLatentImage":
            inputs["width"] = width
            inputs["height"] = height
            inputs["batch_size"] = batch_size
        elif ct == "KSampler":
            inputs["seed"] = seed
            inputs["steps"] = steps
            inputs["cfg"] = cfg

    # Submit to ComfyUI
    client_id = uuid.uuid4().hex
    payload = {"prompt": workflow, "client_id": client_id}

    try:
        resp = _requests.post(f"{COMFYUI_HOST}/prompt", json=payload, timeout=30)
        result = resp.json()
    except Exception as e:
        return jsonify({"error": f"ComfyUI connection failed: {e}"}), 502

    if "node_errors" in result and result["node_errors"]:
        return jsonify({"error": f"Node errors: {json.dumps(result['node_errors'])}"}), 400

    prompt_id = result.get("prompt_id", "")
    total_steps = steps

    return jsonify({
        "success": True,
        "prompt_id": prompt_id,
        "seed": seed,
        "total_steps": total_steps,
    })

@app.route("/api/image/status/<prompt_id>")
def api_image_status(prompt_id):
    """Check ComfyUI job status and return images when done."""
    try:
        resp = _requests.get(f"{COMFYUI_HOST}/history/{prompt_id}", timeout=10)
        history = resp.json()
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 502

    if prompt_id not in history:
        return jsonify({"status": "queued"})

    entry = history[prompt_id]
    status = entry.get("status", {})
    status_str = status.get("status_str", "")
    completed = status.get("completed", False)

    if status_str == "error":
        return jsonify({"status": "error", "error": "Workflow execution failed"})

    if not completed:
        return jsonify({"status": "running"})

    # Extract output images
    images = []
    outputs = entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        for img in node_output.get("images", []):
            filename = img.get("filename", "")
            subfolder = img.get("subfolder", "")
            img_type = img.get("type", "output")
            view_url = f"{COMFYUI_HOST}/view?filename={filename}&subfolder={subfolder}&type={img_type}"
            # Proxy through AgentGUI to avoid CORS issues
            proxy_url = f"/api/image/view?filename={filename}&subfolder={subfolder}&type={img_type}"
            images.append({
                "url": proxy_url,
                "filename": filename,
                "server_path": str(COMFYUI_OUTPUT_DIR / filename) if COMFYUI_OUTPUT_DIR.exists() else filename,
            })

    return jsonify({"status": "done", "images": images})

@app.route("/api/image/view")
def api_image_view():
    """Proxy ComfyUI image output to avoid CORS issues."""
    filename = request.args.get("filename", "")
    subfolder = request.args.get("subfolder", "")
    img_type = request.args.get("type", "output")
    if not filename:
        return jsonify({"error": "filename required"}), 400

    try:
        resp = _requests.get(
            f"{COMFYUI_HOST}/view",
            params={"filename": filename, "subfolder": subfolder, "type": img_type},
            timeout=15,
        )
        if resp.status_code != 200:
            return jsonify({"error": "image not found"}), 404
        return Response(resp.content, content_type=resp.headers.get("Content-Type", "image/png"))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.route("/api/image/output-folder")
def api_image_output_folder():
    """Return the path to the ComfyUI output folder (both VM and Windows paths)."""
    vm_path = str(COMFYUI_OUTPUT_DIR)
    # Shared folder /media/sf_AI_Ecosystem/ maps to D:\AI_Ecosystem\ on Windows
    win_path = vm_path.replace("/media/sf_AI_Ecosystem/", "D:\\AI_Ecosystem\\").replace("/", "\\")
    return jsonify({"path": vm_path, "windows_path": win_path})

@app.route("/api/open-folder")
def api_open_folder():
    """Open a folder in the host file manager (VM: xdg-open, Windows: via shared folder)."""
    folder = request.args.get("path", "")
    if not folder:
        return jsonify({"error": "path required"}), 400
    p = Path(folder)
    if not p.exists():
        return jsonify({"error": f"Path not found: {folder}"}), 404
    try:
        subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Video Generation (Wan 2.2 pipeline) ──
try:
    from video_endpoints import register_video_endpoints
    register_video_endpoints(app)
except Exception as e:
    print(f"[WARN] video_endpoints import failed: {e}")

# ── Video Analyzer (video-analyze.py: motion / drift / sharpness) ──

VIDEO_ANALYZE_SCRIPT = Path("/media/sf_AI_Ecosystem/05_Scripts/video-analyze.py")
VIDEO_ANALYZE_PYTHON = "/usr/bin/python3"
VIDEO_OUTPUT_DIR = COMFYUI_OUTPUT_DIR / "video"

# In-memory job tracker for async analyzer runs
_analyze_jobs = {}  # job_id -> {status, output, plot_path, json_path, error, started, filename}
_analyze_jobs_lock = threading.Lock()


def _run_analyzer_thread(job_id, video_path, grid, content=False, model="qwen3.5:397b", frames=5):
    """Background worker that runs video-analyze.py and stores results."""
    try:
        cmd = [VIDEO_ANALYZE_PYTHON, str(VIDEO_ANALYZE_SCRIPT), "--json"]
        if grid and int(grid) > 0:
            cmd += ["--grid", str(int(grid))]
        if content:
            cmd += ["--content", "--model", model, "--frames", str(int(frames))]
        cmd.append(str(video_path))

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600 if not content else 900,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        rc = proc.returncode

        stem = os.path.splitext(str(video_path))[0]
        plot_path = stem + "_analysis.png"
        json_path = stem + "_analysis.json"

        with _analyze_jobs_lock:
            if rc == 0:
                _analyze_jobs[job_id] = {
                    "status": "done",
                    "output": stdout,
                    "stderr": stderr,
                    "plot_path": plot_path,
                    "json_path": json_path,
                    "plot_exists": os.path.exists(plot_path),
                    "json_exists": os.path.exists(json_path),
                    "filename": os.path.basename(str(video_path)),
                    "finished": time.time(),
                }
            else:
                _analyze_jobs[job_id] = {
                    "status": "error",
                    "output": stdout,
                    "stderr": stderr,
                    "error": f"Analyzer exited with code {rc}",
                    "plot_path": plot_path,
                    "json_path": json_path,
                    "plot_exists": os.path.exists(plot_path),
                    "filename": os.path.basename(str(video_path)),
                    "finished": time.time(),
                }
    except subprocess.TimeoutExpired:
        with _analyze_jobs_lock:
            _analyze_jobs[job_id] = {
                "status": "error",
                "error": "Analyzer timeout (900s)" if content else "Analyzer timeout (600s)",
                "filename": os.path.basename(str(video_path)),
                "finished": time.time(),
            }
    except Exception as e:
        with _analyze_jobs_lock:
            _analyze_jobs[job_id] = {
                "status": "error",
                "error": str(e),
                "filename": os.path.basename(str(video_path)),
                "finished": time.time(),
            }


@app.route("/api/video-analyze/list")
def api_video_analyze_list():
    """List .mp4 files in ComfyUI output/video/ sorted by mtime (newest first)."""
    if not VIDEO_OUTPUT_DIR.exists():
        return jsonify({"error": f"Output dir not found: {VIDEO_OUTPUT_DIR}", "videos": []}), 200
    try:
        videos = []
        for f in VIDEO_OUTPUT_DIR.iterdir():
            if f.is_file() and f.suffix.lower() == ".mp4":
                st = f.stat()
                videos.append({
                    "filename": f.name,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "mtime_iso": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                })
        videos.sort(key=lambda v: v["mtime"], reverse=True)
        return jsonify({"videos": videos, "path": str(VIDEO_OUTPUT_DIR)})
    except Exception as e:
        return jsonify({"error": str(e), "videos": []}), 500


@app.route("/api/video-analyze/run", methods=["POST"])
def api_video_analyze_run():
    """Start analyzer on a video. Returns job_id for polling."""
    data = request.json or {}
    filename = data.get("filename", "")
    manual_path = data.get("path", "")
    grid = int(data.get("grid", 0) or 0)
    content = bool(data.get("content", False))
    model = data.get("model", "qwen3.5:397b")
    frames = int(data.get("frames", 5) or 5)

    # Resolve video path
    if manual_path:
        video_path = Path(manual_path)
        if not video_path.exists():
            return jsonify({"error": f"File not found: {manual_path}"}), 404
    elif filename:
        video_path = VIDEO_OUTPUT_DIR / filename
        if not video_path.exists():
            return jsonify({"error": f"Video not found: {filename}"}), 404
    else:
        return jsonify({"error": "Provide 'filename' or 'path'"}), 400

    if not VIDEO_ANALYZE_SCRIPT.exists():
        return jsonify({"error": f"Analyzer script not found: {VIDEO_ANALYZE_SCRIPT}"}), 500

    job_id = uuid.uuid4().hex
    with _analyze_jobs_lock:
        _analyze_jobs[job_id] = {
            "status": "running",
            "filename": video_path.name,
            "started": time.time(),
        }

    t = threading.Thread(
        target=_run_analyzer_thread,
        args=(job_id, str(video_path), grid),
        kwargs={"content": content, "model": model, "frames": frames},
        daemon=True,
    )
    t.start()

    return jsonify({"success": True, "job_id": job_id, "filename": video_path.name})


@app.route("/api/video-analyze/status/<job_id>")
def api_video_analyze_status(job_id):
    """Poll analyzer job status."""
    with _analyze_jobs_lock:
        job = _analyze_jobs.get(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job)


@app.route("/api/video-analyze/plot")
def api_video_analyze_plot():
    """Serve the _analysis.png for a video filename."""
    filename = request.args.get("filename", "")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    # Security: only basename
    filename = os.path.basename(filename)
    stem = os.path.splitext(filename)[0]
    plot_path = VIDEO_OUTPUT_DIR / f"{stem}_analysis.png"
    if not plot_path.exists():
        return jsonify({"error": "plot not found"}), 404
    return send_file(str(plot_path), mimetype="image/png")


@app.route("/api/video-analyze/json")
def api_video_analyze_json():
    """Serve the _analysis.json for a video filename."""
    filename = request.args.get("filename", "")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    filename = os.path.basename(filename)
    stem = os.path.splitext(filename)[0]
    json_path = VIDEO_OUTPUT_DIR / f"{stem}_analysis.json"
    if not json_path.exists():
        return jsonify({"error": "json not found"}), 404
    try:
        return Response(json_path.read_text(), mimetype="application/json")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Restart ──

@app.route("/api/restart", methods=["POST"])
def api_restart():
    # Respond before dying
    socketio.emit("server_restarting", {})
    def delayed_restart():
        time.sleep(1.5)
        subprocess.Popen(["bash", str(project_root / "restart_server.sh")])
    threading.Thread(target=delayed_restart, daemon=True).start()
    return jsonify({"success": True, "message": "Restarting in 1.5s"})

# ─── jcode endpoints ───

def update_agent_from_jcode_stream(run_id: str, chunk: str):
    """Append a jcode stream chunk to the linked agent's output buffer."""
    # run_id may be prefixed with agent_id: <agent_id>_jcode_<hash>
    if not run_id.startswith("jcode_"):
        parts = run_id.split("_jcode_", 1)
        if len(parts) == 2:
            agent_id = parts[0]
            update_agent(agent_id, output_append=chunk)

@app.route("/api/jcode/run", methods=["POST"])
def api_jcode_run():
    data = request.get_json(force=True) or {}
    repo_path = data.get("repo_path")
    task = data.get("task")
    model = data.get("model")
    tool_profile = data.get("tool_profile")
    timeout = int(data.get("timeout", 600))
    agent_id = data.get("agent_id")

    if not repo_path or not task:
        return jsonify({"error": "repo_path and task are required"}), 400

    try:
        run_id = run_jcode(
            repo_path=repo_path,
            task=task,
            model=model,
            tool_profile=tool_profile,
            timeout=timeout,
            agent_id=agent_id,
            socketio=socketio,
            on_chunk=lambda rid, chunk: update_agent_from_jcode_stream(rid, chunk),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"run_id": run_id, "status": "running"}), 202


@app.route("/api/jcode/runs", methods=["GET"])
def api_jcode_runs():
    agent_id = request.args.get("agent_id")
    return jsonify(list_jcode_runs(agent_id=agent_id))


@app.route("/api/jcode/runs/summary", methods=["GET"])
def api_jcode_run_summaries():
    """Return compact summaries of jcode runs for visual history."""
    agent_id = request.args.get("agent_id")
    try:
        limit = max(1, min(200, int(request.args.get("limit", 50))))
    except ValueError:
        limit = 50
    return jsonify(list_jcode_run_summaries(agent_id=agent_id, limit=limit))


@app.route("/api/jcode/<run_id>", methods=["GET"])
def api_jcode_status(run_id: str):
    state = get_jcode_status(run_id)
    if not state:
        return jsonify({"error": "run not found"}), 404
    return jsonify(state)


@app.route("/api/jcode/<run_id>/kill", methods=["POST"])
def api_jcode_kill(run_id: str):
    if kill_jcode_run(run_id, socketio=socketio):
        return jsonify({"run_id": run_id, "status": "cancelled"})
    return jsonify({"error": "run not found or not running"}), 404


@socketio.on("kill_jcode_run")
def handle_kill_jcode_run(data):
    """Socket.IO kill for jcode runs (frontend real-time stop button)."""
    run_id = data.get("run_id", "")
    if not run_id:
        emit("error", {"message": "run_id required"})
        return
    if kill_jcode_run(run_id, socketio=socketio):
        emit("jcode_run_killed", {"run_id": run_id, "status": "cancelled"}, broadcast=True)
    else:
        emit("error", {"message": f"jcode run {run_id} not found or not running"})


@app.route("/api/jcode/repos", methods=["GET"])
def api_jcode_repos():
    """List allowed repository roots and their subdirectories for jcode."""
    cfg = load_jcode_map()
    roots = cfg.get("allowed_repo_roots", ["/media/sf_AI_Ecosystem/10_Projects/"])
    repos = []
    for root in roots:
        p = Path(root)
        if p.exists() and p.is_dir():
            try:
                seen = set()
                excluded = set(cfg.get("excluded_repo_names", []))
                for sub in sorted(p.iterdir()):
                    if sub.is_dir() and sub.name not in excluded and str(sub) not in seen:
                        repos.append({"path": str(sub), "name": sub.name, "root": root})
                        seen.add(str(sub))
            except Exception:
                pass
    return jsonify({"roots": roots, "repos": repos})


# ─── Message Bus (FASE 4) ──────────────────────────────

@app.route("/api/messages/send", methods=["POST"])
def api_message_send():
    """Send a message from one profile to another via the message bus."""
    try:
        data = request.get_json(force=True)
        from core.message_bus import send_message
        msg = send_message(
            from_profile=data.get("from", ""),
            to_profile=data.get("to", ""),
            content=data.get("content", ""),
            msg_type=data.get("type", "result"),
            task_id=data.get("task_id", ""),
        )
        socketio.emit("message_sent", msg)
        return jsonify(msg)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages/<profile>/inbox", methods=["GET"])
def api_message_inbox(profile):
    """Get messages addressed to a profile."""
    try:
        from core.message_bus import get_inbox
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        msgs = get_inbox(profile, unread_only=unread_only)
        return jsonify({"profile": profile, "count": len(msgs), "messages": msgs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages/<profile>/clear", methods=["POST"])
def api_message_clear(profile):
    """Clear all messages for a profile."""
    try:
        from core.message_bus import clear_inbox
        removed = clear_inbox(profile)
        return jsonify({"removed": removed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages", methods=["GET"])
def api_messages_all():
    """Get all messages in the bus (admin/debug)."""
    try:
        from core.message_bus import get_all_messages
        msgs = get_all_messages()
        return jsonify({"count": len(msgs), "messages": msgs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Agents Registry (FASE 6) ─────────────────────────

@app.route("/api/agents/registry", methods=["GET"])
def api_agents_registry():
    """List all registered agents (Hermes + external)."""
    try:
        from core.agent_interface import list_registered_agents
        agents = list_registered_agents()
        return jsonify({"count": len(agents), "agents": agents})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/registry", methods=["POST"])
def api_agents_register():
    """Register or update an external agent in the registry."""
    try:
        data = request.get_json(force=True)
        from core.agent_interface import register_agent_entry
        entry = register_agent_entry(
            name=data.get("name", ""),
            agent_type=data.get("type", "external_cli"),
            capabilities=data.get("capabilities", []),
            model=data.get("model", ""),
            endpoint=data.get("endpoint", ""),
            command=data.get("command", ""),
            enabled=data.get("enabled", True),
        )
        return jsonify(entry)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/registry/<agent_name>", methods=["DELETE"])
def api_agents_unregister(agent_name):
    """Remove an agent from the registry."""
    try:
        from core.agent_interface import load_registry, save_registry
        registry = load_registry()
        before = len(registry.get("agents", []))
        registry["agents"] = [a for a in registry.get("agents", []) if a["name"] != agent_name]
        save_registry(registry)
        removed = before - len(registry["agents"])
        return jsonify({"removed": removed, "name": agent_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/route", methods=["POST"])
def api_agents_route():
    """Route a task to the best available agent (FASE 6)."""
    try:
        data = request.get_json(force=True)
        task = data.get("task", "")
        preferred = data.get("preferred_agent")
        from core.agent_interface import route_task
        agent = route_task(task, preferred)
        if not agent:
            return jsonify({"error": "No suitable agent found"}), 404
        return jsonify({
            "agent_type": agent.agent_type,
            "dispatched": True,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Socket.IO Events ─────────────────────────────────

@socketio.on("connect")
def on_connect():
    emit("connected", {"agents": list_agents()})
    emit("orchestrator_status", ORCH_STATUS_CACHE)

@socketio.on("launch_agent")
def handle_launch_agent(data):
    profile = data.get("profile", "developer")
    goal = data.get("goal", "")
    model = data.get("model")
    agent_id = f"{profile}_{uuid.uuid4().hex[:8]}"
    try:
        register_agent(agent_id, profile, goal, "")
        # Load model from profile config if not provided
        if not model:
            config = load_profile_config(profile)
            model = config.get("model")
        result = launch_agent(profile, goal, "", agent_id=agent_id, model=model)
        emit("agent_launched", result, broadcast=True)
    except Exception as e:
        emit("error", {"message": str(e)})

@socketio.on("kill_agent")
def handle_kill_agent(data):
    agent_id = data.get("id", "")
    try:
        kill_agent(agent_id)
        emit("agent_killed", {"id": agent_id}, broadcast=True)
    except Exception as e:
        emit("error", {"message": str(e)})

def _dispatch_task_impl(data: dict) -> dict:
    """Core dispatch logic; can be called from REST or Socket.IO."""
    target_profile = data.get("target_profile", data.get("profile", "developer"))
    task_text = data.get("task", "")
    use_jcode = data.get("use_jcode", False)
    repo_path = data.get("repo_path")
    tool_profile = data.get("tool_profile")
    timeout = int(data.get("timeout", 600))
    caller_profile = data.get("caller_profile", "orchestrator")  # FASE 4: track who dispatched

    # IDs now match profile names directly (1:1, no mapping needed)
    profile = target_profile

    agent_id = f"{profile}_{uuid.uuid4().hex[:8]}"

    config = load_profile_config(profile)
    model = config.get("model")

    # developer always delegates to jcode
    use_jcode = (profile == "developer")
    classification = None

    task_file = DATA_DIR / f"{agent_id}_task.json"
    task_data = {
        "id": agent_id,
        "profile": profile,
        "goal": task_text,
        "model": model,
        "use_jcode": use_jcode,
        "repo_path": repo_path,
        "tool_profile": tool_profile,
        "timeout": timeout,
        "caller_profile": caller_profile,  # FASE 4: so runners know where to send result
        "created_at": datetime.now().isoformat()
    }
    task_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))

    register_agent(agent_id, profile, task_text, "")

    result = {}
    jcode_run_id = None

    if profile == "developer" and use_jcode:
        default_repo = "/media/sf_AI_Ecosystem/10_Projects/"
        target_repo = repo_path or default_repo
        try:
            jcode_run_id = run_jcode(
                repo_path=target_repo,
                task=task_text,
                model=model,
                tool_profile=tool_profile,
                timeout=timeout,
                agent_id=agent_id,
                socketio=socketio,
                on_chunk=lambda rid, chunk: update_agent_from_jcode_stream(rid, chunk),
            )
            update_agent(agent_id, status="running", message=f"jcode run {jcode_run_id}")
            result = {"agent_id": agent_id, "jcode_run_id": jcode_run_id, "status": "running"}
        except Exception as e:
            update_agent(agent_id, status="error", error=str(e), message="Falha ao iniciar jcode")
            result = {"error": str(e)}
    else:
        result = launch_agent(profile, task_text, "", agent_id=agent_id, model=model)

    save_history_entry({
        "id": agent_id,
        "profile": profile,
        "task": task_text,
        "model": model,
        "use_jcode": use_jcode,
        "jcode_classification": classification,
        "jcode_run_id": jcode_run_id,
        "timestamp": datetime.now().isoformat(),
        "status": "dispatched"
    })

    # Broadcast updated agents list so all tabs (COMANDO, TAREFAS) see the new agent immediately
    try:
        socketio.emit("agents_updated", {"agents": list_agents()})
    except Exception:
        pass  # don't fail the dispatch if socket emit fails

    return {
        "id": agent_id,
        "profile": profile,
        "task": task_text,
        "model": model,
        "use_jcode": use_jcode,
        "jcode_classification": classification,
        "jcode_run_id": jcode_run_id,
        **result
    }


@socketio.on("dispatch_task")
def handle_dispatch_task(data):
    """Socket.IO wrapper around _dispatch_task_impl."""
    result = _dispatch_task_impl(data)
    emit("task_dispatched", {
        "id": result["id"],
        "profile": result["profile"],
        "task": result["task"],
        "model": result["model"],
        "use_jcode": result["use_jcode"],
        "jcode_classification": result["jcode_classification"],
        "jcode_run_id": result["jcode_run_id"],
    })
    if "error" in result:
        emit("error", {"message": result["error"]})

@socketio.on("add_cron_task")
def handle_add_cron(data):
    tasks = load_cron_tasks()
    task = {
        "id": uuid.uuid4().hex[:8],
        "profile": data.get("profile", "researcher"),
        "task": data.get("task", ""),
        "hour": int(data.get("hour", 12)),
        "minute": int(data.get("minute", 0)),
        "days": data.get("days", [0,1,2,3,4]),
        "repeat_type": data.get("repeat_type", "infinite"),
        "repeat_count": int(data.get("repeat_count", 1)),
        "runs_done": 0,
        "enabled": True,
        "created_at": datetime.now().isoformat()
    }
    tasks.append(task)
    save_cron_tasks(tasks)
    emit("cron_task_added", task, broadcast=True)

@socketio.on("remove_cron_task")
def handle_remove_cron(data):
    task_id = data.get("id", "")
    tasks = load_cron_tasks()
    tasks = [t for t in tasks if t["id"] != task_id]
    save_cron_tasks(tasks)
    emit("cron_task_removed", {"id": task_id}, broadcast=True)

@socketio.on("toggle_cron_task")
def handle_toggle_cron(data):
    task_id = data.get("id", "")
    tasks = load_cron_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["enabled"] = not t.get("enabled", True)
            save_cron_tasks(tasks)
            emit("cron_task_toggled", t, broadcast=True)
            return

@socketio.on("list_cron_tasks")
def handle_list_cron():
    emit("cron_tasks_update", load_cron_tasks())

@socketio.on("orchestrator_message")
def handle_orch_message(data):
    text = data.get("text", "")
    if not text:
        return
    # Store in inbox
    inbox = load_orch_inbox()
    inbox.append({"text": text, "time": datetime.now().isoformat()})
    save_orch_inbox(inbox)
    emit("message_received", {"success": True})
    # The orchestrator_agent.py (subprocess) will pick this up via Socket.IO or inbox polling

@socketio.on("orchestrator_mode_change")
def handle_orch_mode_change(data):
    mode = data.get("mode", "brainstorm")
    ORCH_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ORCH_MODE_FILE.write_text(json.dumps({"mode": mode}))
    ORCH_STATUS_CACHE["mode"] = mode
    emit("orchestrator_status", ORCH_STATUS_CACHE, broadcast=True)

@socketio.on("orchestrator_summarize")
def handle_orch_summarize():
    # Forward to orchestrator agent if connected
    emit("orchestrator_summarize", {}, broadcast=True)

# Orchestrator agent → server events (re-broadcast to all clients)
@socketio.on("orchestrator_response")
def handle_orch_response_socket(data):
    emit("orchestrator_response", data, broadcast=True)

@socketio.on("orchestrator_typing")
def handle_orch_typing_socket(data):
    emit("orchestrator_typing", data, broadcast=True)

@socketio.on("orchestrator_ready")
def handle_orch_ready(data):
    global ORCH_STATUS_CACHE
    ORCH_STATUS_CACHE = {"online": True, "mode": data.get("mode", "brainstorm")}
    emit("orchestrator_status", ORCH_STATUS_CACHE, broadcast=True)

@socketio.on("get_output")
def handle_get_output(data):
    agent_id = data.get("id", "")
    lines = int(data.get("lines", 100))
    output = get_agent_output(agent_id, lines)
    emit("agent_output", {"id": agent_id, "output": output})

@socketio.on("send_input")
def handle_send_input(data):
    agent_id = data.get("id", "")
    text = data.get("text", "")
    send_keys_to_agent(agent_id, text)
    emit("input_sent", {"id": agent_id, "success": True})

@socketio.on("refresh_agents")
def handle_refresh():
    emit("agents_updated", {"agents": list_agents()}, broadcast=True)

# ─── Background Threads ───────────────────────────────
# ─── Background Threads ───────────────────────────────

def resources_worker():
    """Emit VM + Windows resources every 2 seconds."""
    while True:
        try:
            vm_res = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "cpu_count": psutil.cpu_count(),
                "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                "ram_percent": psutil.virtual_memory().percent,
                "ram_used": round(psutil.virtual_memory().used / (1024**3), 1),
                "ram_total": round(psutil.virtual_memory().total / (1024**3), 1),
                "disk_percent": psutil.disk_usage("/").percent,
                "disk_used": round(psutil.disk_usage("/").used / (1024**3), 1),
                "disk_total": round(psutil.disk_usage("/").total / (1024**3), 1),
            }
            socketio.emit("resources_update", {"vm": vm_res, "windows": windows_resources})
        except Exception as e:
            print(f"[resources_worker] Error: {e}")
        time.sleep(2)

def sync_worker():
    """Sync agent states every 5 seconds. Emits agent_completed for finished agents (FASE 2)."""
    while True:
        try:
            completed = sync_running_agents()
            for c in completed:
                # Broadcast completion event to all connected clients
                socketio.emit("agent_completed", c)
                # Broadcast updated agents list so TAREFAS/COMANDO tabs update in real-time
                try:
                    socketio.emit("agents_updated", {"agents": list_agents()})
                except Exception:
                    pass
                # FASE A: emit final stream output for Command Center
                agent_id = c.get("agent_id", "")
                if agent_id:
                    agent = get_agent(agent_id)
                    final_output = (agent or {}).get("output", c.get("output_summary", ""))
                    socketio.emit("agent_stream", {
                        "agent_id": agent_id,
                        "profile": c.get("profile", "?"),
                        "output": final_output,
                        "status": c.get("status", "completed"),
                        "timestamp": datetime.now().isoformat(),
                        "is_final": True,
                    })
                    # Clean stream cache
                    _stream_cache.pop(agent_id, None)
                try:
                    print(f"[sync_worker] Agent {c['agent_id']} → {c['status']} ({c['duration']}s)")
                except Exception:
                    pass  # stdout pipe may be broken — don't kill the worker
        except Exception as e:
            try:
                print(f"[sync_worker] Error: {e}")
            except Exception:
                pass  # swallow print errors to keep worker alive
        try:
            time.sleep(5)
        except Exception:
            pass  # sleep should never kill the worker

def cron_scheduler_worker():
    """Check cron tasks every 30 seconds."""
    while True:
        try:
            tasks = load_cron_tasks()
            now = datetime.now()
            current_day = now.weekday()  # 0=Monday, 6=Sunday
            current_hour = now.hour
            current_minute = now.minute
            
            for task in tasks:
                if not task.get("enabled", True):
                    continue
                if current_hour != task.get("hour", 0) or current_minute != task.get("minute", 0):
                    continue
                if current_day not in task.get("days", []):
                    continue
                
                # Check if already ran this minute
                last_run = task.get("last_run", "")
                if last_run and last_run.startswith(now.strftime("%Y-%m-%d %H:%M")):
                    continue
                
                # Launch agent
                profile = task.get("profile", "researcher")
                task_text = task.get("task", "")
                agent_id = f"cron_{task['id']}_{uuid.uuid4().hex[:4]}"
                
                task_file = DATA_DIR / f"{agent_id}_task.json"
                task_file.write_text(json.dumps({
                    "id": agent_id,
                    "profile": profile,
                    "goal": task_text,
                    "created_at": now.isoformat()
                }, indent=2))
                
                register_agent(agent_id, profile, task_text, "")
                config = load_profile_config(profile)
                launch_agent(profile, task_text, "", agent_id=agent_id, model=config.get("model"))
                
                # Update runs_done
                task["runs_done"] = task.get("runs_done", 0) + 1
                task["last_run"] = now.isoformat()
                if task.get("repeat_type") == "times" and task["runs_done"] >= task.get("repeat_count", 1):
                    task["enabled"] = False
                
                save_cron_tasks(tasks)
                socketio.emit("cron_task_executed", {"id": task["id"], "agent_id": agent_id})
                print(f"[CRON] Launched: {agent_id} for task {task['id']}")
        except Exception as e:
            print(f"[cron_worker] Error: {e}")
        time.sleep(30)

def orchestrator_subprocess_worker():
    """Start orchestrator_agent.py as subprocess."""
    orch_script = project_root / "orchestrator_agent.py"
    if not orch_script.exists():
        print("[orchestrator] Script not found, skipping subprocess")
        return
    
    log_file = "/tmp/orchestrator_agent.log"
    while True:
        try:
            print("[orchestrator] Starting subprocess...")
            with open(log_file, "a") as log:
                proc = subprocess.Popen(
                    [sys.executable, str(orch_script)],
                    stdout=log,
                    stderr=log,
                    env=os.environ.copy()
                )
                proc.wait()
                print(f"[orchestrator] Subprocess exited with code {proc.returncode}")
        except Exception as e:
            print(f"[orchestrator] Error: {e}")
        # Restart after 5s
        time.sleep(5)

# ─── Tools: Prompt Log & Prompt Builder ──────────────

COMFY_OUTPUT = Path("/media/sf_AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output")
PROMPTS_IMG_TXT = COMFY_OUTPUT / "prompts_img.txt"
PROMPTS_VID_TXT = COMFY_OUTPUT / "video" / "prompts_vid.txt"
PROMPT_LOG_JSON = Path("/media/sf_AI_Ecosystem/04_Data/prompt-log.json")


def _parse_prompt_txt(path: Path, entry_type: str):
    """Parse a prompts_*.txt file into a list of {type, positive, negative} dicts.

    Entries separated by lines of dashes. Each entry has 'Positivo:' and 'Negativo:' headers.
    Files use CRLF line endings.
    """
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[prompts] Error reading {path}: {e}")
        return []
    # Normalize line endings
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Split on separator lines (10+ dashes, possibly surrounded by blank lines)
    import re
    parts = re.split(r"(?:^|\n)-{5,}\s*(?:\n|$)", raw)
    entries = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Find Positivo: and Negativo: blocks
        pos = ""
        neg = ""
        # Use regex with DOTALL to capture multi-line blocks until the next header
        m_pos = re.search(r"Positivo:\s*(.*?)(?:\n\s*Negativo:|$)", part, re.DOTALL)
        m_neg = re.search(r"Negativo:\s*(.*?)$", part, re.DOTALL)
        if m_pos:
            pos = m_pos.group(1).strip()
        if m_neg:
            neg = m_neg.group(1).strip()
        # Skip fully-empty entries
        if not pos and not neg:
            continue
        entries.append({
            "type": entry_type,
            "positive": pos,
            "negative": neg,
            "source": str(path.name),
        })
    return entries


def _load_prompt_log_json():
    """Load the JSON prompt log (list of user-saved entries)."""
    if not PROMPT_LOG_JSON.exists():
        return []
    try:
        data = json.loads(PROMPT_LOG_JSON.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"[prompts] Error reading JSON log: {e}")
        return []


def _save_prompt_log_json(entries):
    """Persist the JSON prompt log."""
    PROMPT_LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_LOG_JSON.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@app.route("/api/tools/prompts/read")
def api_tools_prompts_read():
    """Return all prompt entries: image .txt + video .txt + JSON log (merged)."""
    try:
        entries = []
        entries.extend(_parse_prompt_txt(PROMPTS_IMG_TXT, "image"))
        entries.extend(_parse_prompt_txt(PROMPTS_VID_TXT, "video"))
        for e in _load_prompt_log_json():
            # Normalize JSON entries to include 'type' and 'positive'/'negative'
            entries.append({
                "type": e.get("type", "image"),
                "positive": e.get("positive", e.get("prompt", "")),
                "negative": e.get("negative", ""),
                "filename": e.get("filename", ""),
                "notes": e.get("notes", ""),
                "source": "prompt-log.json",
            })
        return jsonify({"count": len(entries), "entries": entries})
    except Exception as e:
        return jsonify({"error": str(e), "entries": []}), 500


@app.route("/api/tools/prompts/save", methods=["POST"])
def api_tools_prompts_save():
    """Append a new prompt entry to the JSON log."""
    try:
        data = request.get_json(force=True) or {}
        filename = (data.get("filename") or "").strip()
        ptype = (data.get("type") or "image").strip().lower()
        if ptype not in ("image", "video"):
            ptype = "image"
        positive = (data.get("positive") or "").strip()
        negative = (data.get("negative") or "").strip()
        notes = (data.get("notes") or "").strip()
        if not positive:
            return jsonify({"error": "positive prompt is required"}), 400
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "filename": filename,
            "type": ptype,
            "positive": positive,
            "negative": negative,
            "notes": notes,
        }
        entries = _load_prompt_log_json()
        entries.append(entry)
        _save_prompt_log_json(entries)
        return jsonify({"success": True, "entry": entry, "total": len(entries)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tools/prompts/lookup")
def api_tools_prompts_lookup():
    """Given a filename (image or video), find the best matching prompt entry.

    Strategy:
      1. Search JSON log for an exact filename match.
      2. Derive the index from a numeric prefix in the filename (e.g. ComfyUI_00007_.mp4 → index 6)
         and return the entry at that position from the relevant .txt file.
      3. Return null if nothing matches.
    """
    import re as _re
    try:
        filename = (request.args.get("filename") or "").strip()
        if not filename:
            return jsonify({"match": None, "reason": "no filename provided"})
        # Determine type from extension
        ext = os.path.splitext(filename)[1].lower()
        is_video = ext in (".mp4", ".webm", ".mov", ".avi", ".mkv")
        is_image = ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
        ptype = "video" if is_video else ("image" if is_image else "")

        # 1. JSON log exact match
        for e in _load_prompt_log_json():
            if e.get("filename", "").lower() == filename.lower():
                return jsonify({
                    "match": {
                        "type": e.get("type", ptype or "image"),
                        "positive": e.get("positive", e.get("prompt", "")),
                        "negative": e.get("negative", ""),
                        "filename": e.get("filename", filename),
                        "notes": e.get("notes", ""),
                        "source": "prompt-log.json",
                    },
                    "reason": "json-exact",
                })

        # 2. Numeric-index match against .txt files
        m = _re.search(r"(\d+)", os.path.basename(filename))
        if m:
            idx = int(m.group(1))
            # Choose file by type; if unknown, try both
            candidates = []
            if ptype == "video" or ptype == "":
                candidates.append((PROMPTS_VID_TXT, "video"))
            if ptype == "image" or ptype == "":
                candidates.append((PROMPTS_IMG_TXT, "image"))
            for path, etype in candidates:
                entries = _parse_prompt_txt(path, etype)
                # Numbering observed: ComfyUI_00007_ → 7, but list is 1-indexed in the file.
                # The .txt files appear to be appended in order, so index N (1-based) → entries[N-1].
                # If filename uses 0-padding, the numeric value maps directly. Try 1-based first,
                # then 0-based.
                for offset in (1, 0):
                    target = idx - offset
                    if 0 <= target < len(entries):
                        entry = entries[target]
                        if entry.get("positive") or entry.get("negative"):
                            return jsonify({
                                "match": {
                                    "type": etype,
                                    "positive": entry.get("positive", ""),
                                    "negative": entry.get("negative", ""),
                                    "filename": filename,
                                    "notes": "",
                                    "source": path.name,
                                    "index": target,
                                },
                                "reason": f"txt-index-{offset}",
                            })
        # 3. No match
        return jsonify({"match": None, "reason": "no match found"})
    except Exception as e:
        return jsonify({"error": str(e), "match": None}), 500


@app.route("/api/tools/prompt-builder/presets")
def api_tools_prompt_builder_presets():
    """Return presets for the Prompt Builder tool."""
    presets = {
        "camera_verbs": [
            "camera tilts up", "camera push in", "camera pull back",
            "camera pans left", "camera pans right",
            "camera orbits right", "camera orbits left", "fixed camera",
        ],
        "movement_verbs": [
            "surging", "churning", "crashing", "swirling",
            "drifting", "flowing", "exploding", "flying",
        ],
        "weak_verbs_warning": ["smooth", "calm", "gentle"],
        "motion_intensity": ["low", "medium", "high"],
        "style_presets": {
            "realistic": {
                "positive_prefix": "masterpiece, best quality, photorealistic, 8k, highly detailed, raw photo,",
                "negative": "(worst quality, low quality, bad quality:1.4), (blurry, blurred, out of focus:1.2), ugly, deformed, disfigured, extra limbs, bad anatomy, watermark, signature, text, jpeg artifacts, oversaturated, overexposed, illustration, painting, drawing, cartoon, 3d render, plastic, artificial",
            },
            "fantasy": {
                "positive_prefix": "fantasy animation style, concept art, cartoon shading, whimsical, masterpiece, best quality, highly detailed,",
                "negative": "photorealistic, realistic, photo, photograph, 3d render, octane render, text, watermark, blurry, low quality, worst quality, deformed, ugly, realistic skin, real person",
            },
            "animation": {
                "positive_prefix": "masterpiece, best quality, highly detailed, 2d animation, cel shading, vibrant colors, studio anime quality,",
                "negative": "photorealistic, realistic, photo, 3d render, text, watermark, blurry, low quality, worst quality, deformed, ugly",
            },
        },
    }
    return jsonify(presets)


# ─── AI Prompt Builder — Ollama-powered prompt transformation ───

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://192.168.0.187:11434")

def _build_prompt_system_message(ptype, style, camera_sel=None, movement_sel=None):
    """Build a system prompt for the LLM that knows how to generate detailed prompts."""
    type_desc = {
        "image": "static image (single frame, no motion, focus on composition and detail)",
        "video": "video (5 seconds, 81 frames, needs movement and camera motion)",
        "music": "music (audio generation, needs genre, mood, instruments, tempo)",
    }.get(ptype, "image")
    
    style_desc = {
        "realistic": "photorealistic, natural colors, real-world textures, 35mm lens quality, National Geographic style",
        "fantasy": "fantasy concept art, ethereal, magical, bioluminescent, glowing particles, floating runes, otherworldly, NOT photorealistic, clearly stylized",
        "animation": "2D animation, cel shading, vibrant colors, clean linework, studio anime quality",
    }.get(style, "realistic")
    
    camera_info = ""
    if ptype == "video" and camera_sel:
        camera_info = f"\n- Camera movement to include: {', '.join(camera_sel)}"
    
    movement_info = ""
    if ptype == "video" and movement_sel:
        movement_info = f"\n- Scene movement verbs to include: {', '.join(movement_sel)}"
    
    rules = f"""You are an expert prompt engineer for AI {'video' if ptype == 'video' else 'image'} generation using Wan 2.2 and SDXL models.

Transform the user's scene description into a detailed, optimized positive prompt.

CONTEXT:
- Content type: {type_desc}
- Visual style: {style_desc}{camera_info}{movement_info}

RULES FOR {'VIDEO' if ptype == 'video' else 'IMAGE'} PROMPTS:"""

    if ptype == "video":
        rules += """
- Add SPECIFIC movement verbs (surging, churning, crashing, swirling, drifting, exploding) — NEVER use smooth, calm, gentle (they kill motion)
- Add camera movement description (camera tilts up, camera push in, camera pull back, camera pans, camera orbits)
- Add stability terms: "consistent scene, stable composition"
- Add temporal continuity terms: "continuous movement, seamless motion"
- Describe DYNAMIC action, not static beauty
- Add atmosphere and lighting suitable for video"""
    else:
        rules += """
- Focus on composition, framing, and single-frame beauty
- Add lens details (35mm, macro, wide-angle, etc.)
- Add lighting (golden hour, volumetric light, soft light, etc.)
- Add texture details (extremely detailed, hyper-detailed)
- Add depth of field and focus descriptions
- No motion or camera movement terms"""
    
    if style == "fantasy":
        rules += """
- Add fantasy elements: glowing particles, bioluminescent flora, ethereal mist, magical lighting, floating runes
- Add "concept art, painterly, ethereal, magical, dreamlike atmosphere, clearly unrealistic, stylized"
- Add "not photorealistic, not live footage" to distinguish from realistic"""
    elif style == "realistic":
        rules += """
- Add "masterpiece, best quality, photorealistic, 8k, highly detailed, raw photo"
- Add natural textures: "extremely detailed textures of stone, wood, water, fabric"
- Add "natural colors" and avoid stylization terms"""
    elif style == "animation":
        rules += """
- Add "2d animation, cel shading, vibrant colors, clean linework, studio anime quality"
- Add "key visual quality, expressive composition"
- Avoid photorealistic or 3D render terms"""

    rules += """

OUTPUT FORMAT:
- Output ONLY the final positive prompt, nothing else
- No explanations, no labels, no "Prompt:" prefix
- Comma-separated tags and descriptive phrases
- Keep it under 300 words
- The prompt should be ready to paste directly into ComfyUI"""

    return rules


@app.route("/api/tools/prompt-builder/generate", methods=["POST"])
def api_tools_prompt_builder_generate():
    """Generate a detailed prompt using a local LLM via Ollama."""
    data = request.json or {}
    scene = (data.get("scene") or "").strip()
    ptype = data.get("type", "image")
    style = data.get("style", "realistic")
    camera_sel = data.get("camera", [])
    movement_sel = data.get("movement", [])
    
    if not scene:
        return jsonify({"error": "Scene description is required"}), 400
    
    system_msg = _build_prompt_system_message(ptype, style, camera_sel, movement_sel)
    
    # Build the user message with context
    user_msg = f"Scene description: {scene}"
    if camera_sel:
        user_msg += f"\nCamera: {', '.join(camera_sel)}"
    if movement_sel:
        user_msg += f"\nMovement: {', '.join(movement_sel)}"
    user_msg += f"\nStyle: {style}\nType: {ptype}"
    user_msg += "\n\nTransform this into a detailed positive prompt."
    
    payload = {
        "model": "glm-5.2:cloud",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 600},
    }
    
    try:
        resp = _requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=60,
        )
        result = resp.json()
        content = result.get("message", {}).get("content", "").strip()
        
        if not content:
            # Some models put output in "thinking" field
            thinking = result.get("message", {}).get("thinking", "")
            if thinking:
                # Extract the last paragraph that looks like a prompt
                lines = thinking.strip().split("\n")
                content = lines[-1].strip() if lines else ""
        
        if not content:
            return jsonify({"error": "LLM returned empty response"}), 502
        
        # Clean up: remove any "Prompt:" prefix or quotes
        content = content.strip('"').strip("'")
        for prefix in ["Prompt:", "Positive prompt:", "Positive:", "Here is", "Here's"]:
            if content.lower().startswith(prefix.lower()):
                content = content[len(prefix):].strip()
        
        # Generate negative prompt based on style
        negative_presets = {
            "realistic": "(worst quality, low quality, bad quality:1.4), (blurry, blurred, out of focus:1.2), ugly, deformed, disfigured, extra limbs, bad anatomy, watermark, signature, text, jpeg artifacts, oversaturated, overexposed, illustration, painting, drawing, cartoon, 3d render, plastic, artificial",
            "fantasy": "photorealistic, realistic, photo, photograph, 3d render, octane render, text, watermark, blurry, low quality, worst quality, deformed, ugly, realistic skin, real person",
            "animation": "photorealistic, realistic, photo, 3d render, text, watermark, blurry, low quality, worst quality, deformed, ugly",
        }
        negative = negative_presets.get(style, negative_presets["realistic"])
        
        if ptype == "video":
            negative += ", motion smear, motion artifacts, flickering, jitter, warp, distortion, static, frozen, no motion"
            if style == "fantasy":
                negative += ", continuous streaks, persistent glow lines, uniform vertical streaks, ordered pattern, energy drizzle, lingering lightning"
        
        return jsonify({
            "positive": content,
            "negative": negative,
            "model": result.get("model", "glm-5.2"),
            "tokens": result.get("eval_count", 0),
            "duration_s": round(result.get("total_duration", 0) / 1e9, 1),
        })
    except _requests.exceptions.Timeout:
        return jsonify({"error": "LLM timeout (model may be loading)"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Start background threads ─────────────────────────

# FASE A: Command Center — live terminal streaming
_stream_cache = {}  # agent_id → last output hash

def stream_worker():
    """Stream tmux pane output for all running agents via Socket.IO every 1.5s."""
    while True:
        try:
            from core.runner import get_agent_output, _session_exists, TMUX_PREFIX
            running = [a for a in list_agents() if a.get("status") == "running"]
            for agent in running:
                agent_id = agent["id"]
                session = f"{TMUX_PREFIX}{agent_id}"
                if not _session_exists(session):
                    continue
                output = get_agent_output(agent_id, lines=50)
                if not output:
                    continue
                # Hash to detect changes
                import hashlib
                h = hashlib.md5(output.encode("utf-8", errors="replace")).hexdigest()
                if _stream_cache.get(agent_id) == h:
                    continue  # no change
                _stream_cache[agent_id] = h
                try:
                    socketio.emit("agent_stream", {
                        "agent_id": agent_id,
                        "profile": agent.get("profile", "?"),
                        "output": output,
                        "status": "running",
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception:
                    pass  # don't kill the worker
        except Exception as e:
            try:
                print(f"[stream_worker] Error: {e}")
            except Exception:
                pass
        try:
            time.sleep(1.5)
        except Exception:
            pass

threading.Thread(target=resources_worker, daemon=True).start()
threading.Thread(target=sync_worker, daemon=True).start()
threading.Thread(target=stream_worker, daemon=True).start()
threading.Thread(target=cron_scheduler_worker, daemon=True).start()
threading.Thread(target=orchestrator_subprocess_worker, daemon=True).start()

# ── Scripts Panel (zero-token task management) ──

TASKS_DIR = Path("/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI/scripts")
TASKS_DIR.mkdir(parents=True, exist_ok=True)
_task_jobs = {}  # job_id -> {status, output, task_id, pid, finished}
_task_jobs_lock = threading.Lock()
_task_pids = {}  # task_id -> {pid, job_id}
_task_pids_lock = threading.Lock()

def _run_task_thread(job_id, task_id, script_path, lang):
    try:
        if lang == "bash":
            cmd = ["bash", str(script_path)]
        else:
            cmd = ["/usr/bin/python3", str(script_path)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        with _task_pids_lock:
            _task_pids[task_id] = {"pid": proc.pid, "job_id": job_id}
        stdout, _ = proc.communicate(timeout=3600)
        rc = proc.returncode
        with _task_jobs_lock:
            _task_jobs[job_id] = {
                "status": "done" if rc == 0 else "error",
                "output": stdout or "",
                "returncode": rc,
                "task_id": task_id,
                "finished": time.time(),
            }
        with _task_pids_lock:
            _task_pids.pop(task_id, None)
    except subprocess.TimeoutExpired:
        proc.kill()
        with _task_jobs_lock:
            _task_jobs[job_id] = {"status": "error", "output": "Timeout (3600s)", "task_id": task_id, "finished": time.time()}
        with _task_pids_lock:
            _task_pids.pop(task_id, None)
    except Exception as e:
        with _task_jobs_lock:
            _task_jobs[job_id] = {"status": "error", "output": str(e), "task_id": task_id, "finished": time.time()}
        with _task_pids_lock:
            _task_pids.pop(task_id, None)

def _detect_lang(name):
    if name.endswith(".sh") or name.endswith(".bash"): return "bash"
    return "python"

def _read_task_json(task_dir):
    tj = task_dir / "task.json"
    if not tj.exists():
        return None
    try:
        return json.loads(tj.read_text(errors="replace"))
    except:
        return None

def _is_task_running(task_id):
    with _task_pids_lock:
        info = _task_pids.get(task_id)
        if not info:
            return False
        # Check if process is still alive
        try:
            os.kill(info["pid"], 0)
            return True
        except (ProcessLookupError, PermissionError):
            _task_pids.pop(task_id, None)
            return False

@app.route("/api/scripts/list")
def api_scripts_list():
    try:
        tasks = []
        for d in TASKS_DIR.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue
            tj = _read_task_json(d)
            if not tj:
                continue
            st = d.stat()
            tasks.append({
                "id": d.name,
                "name": tj.get("name", d.name),
                "description": tj.get("description", ""),
                "entry_point": tj.get("entry_point", ""),
                "files": tj.get("files", []),
                "mtime": st.st_mtime,
                "running": _is_task_running(d.name),
            })
        tasks.sort(key=lambda x: x["mtime"], reverse=True)
        return jsonify({"tasks": tasks, "path": str(TASKS_DIR)})
    except Exception as e:
        return jsonify({"error": str(e), "tasks": []}), 500

@app.route("/api/scripts/read")
def api_scripts_read():
    task_id = os.path.basename(request.args.get("task", ""))
    filename = os.path.basename(request.args.get("file", ""))
    if not task_id or not filename:
        return jsonify({"error": "task and file required"}), 400
    p = TASKS_DIR / task_id / filename
    if not p.exists():
        return jsonify({"error": "not found"}), 404
    try:
        content = p.read_text(errors="replace")
        return jsonify({"content": content, "lang": _detect_lang(filename)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scripts/save", methods=["POST"])
def api_scripts_save():
    data = request.json or {}
    task_id = os.path.basename(data.get("task", ""))
    filename = os.path.basename(data.get("file", ""))
    content = data.get("content", "")
    if not task_id or not filename:
        return jsonify({"error": "task and file required"}), 400
    p = TASKS_DIR / task_id / filename
    try:
        p.write_text(content)
        return jsonify({"success": True, "size": p.stat().st_size})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scripts/create", methods=["POST"])
def api_scripts_create():
    data = request.json or {}
    name = data.get("name", "").strip()
    desc = data.get("description", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    task_id = name.lower().replace(" ", "-").replace("/", "-")
    d = TASKS_DIR / task_id
    if d.exists():
        return jsonify({"error": "already exists"}), 409
    d.mkdir(parents=True)
    entry = task_id.replace("-", "_") + ".py"
    (d / entry).write_text("#!/usr/bin/env python3\n# " + name + "\n")
    task_json = {
        "name": name,
        "description": desc,
        "entry_point": entry,
        "files": [{"path": entry, "desc": "Script principal"}],
    }
    (d / "task.json").write_text(json.dumps(task_json, indent=2))
    return jsonify({"success": True, "task_id": task_id})

@app.route("/api/scripts/delete")
def api_scripts_delete():
    task_id = os.path.basename(request.args.get("task", ""))
    if not task_id:
        return jsonify({"error": "task required"}), 400
    if _is_task_running(task_id):
        return jsonify({"error": "task is running"}), 409
    d = TASKS_DIR / task_id
    if not d.exists():
        return jsonify({"error": "not found"}), 404
    try:
        import shutil
        shutil.rmtree(d)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scripts/run", methods=["POST"])
def api_scripts_run():
    data = request.json or {}
    task_id = os.path.basename(data.get("task", ""))
    if not task_id:
        return jsonify({"error": "task required"}), 400
    if _is_task_running(task_id):
        return jsonify({"error": "already running"}), 409
    tj = _read_task_json(TASKS_DIR / task_id)
    if not tj:
        return jsonify({"error": "task.json not found"}), 404
    entry = tj.get("entry_point", "")
    script_path = TASKS_DIR / task_id / entry
    if not script_path.exists():
        return jsonify({"error": f"entry point not found: {entry}"}), 404
    lang = _detect_lang(entry)
    job_id = uuid.uuid4().hex
    with _task_jobs_lock:
        _task_jobs[job_id] = {"status": "running", "task_id": task_id, "started": time.time()}
    threading.Thread(target=_run_task_thread, args=(job_id, task_id, str(script_path), lang), daemon=True).start()
    return jsonify({"job_id": job_id, "task_id": task_id})

@app.route("/api/scripts/stop", methods=["POST"])
def api_scripts_stop():
    data = request.json or {}
    task_id = os.path.basename(data.get("task", ""))
    if not task_id:
        return jsonify({"error": "task required"}), 400
    with _task_pids_lock:
        info = _task_pids.get(task_id)
        if not info:
            return jsonify({"error": "not running"}), 404
        try:
            os.kill(info["pid"], 15)
            _task_pids.pop(task_id, None)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/api/scripts/request", methods=["POST"])
def api_scripts_request():
    """Dispatch to developer profile to build a script task."""
    data = request.json or {}
    name = data.get("name", "").strip()
    desc = data.get("description", "").strip()
    if not name or not desc:
        return jsonify({"error": "name and description required"}), 400
    task_id = name.lower().replace(" ", "-").replace("/", "-")
    task_dir = TASKS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    prompt = (
        f"Cria um script em Python na pasta {task_dir}/ que faça o seguinte:\n\n"
        f"{desc}\n\n"
        f"Requisitos:\n"
        f"- O script principal deve ser o entry point (ficheiro .py)\n"
        f"- Cria um ficheiro task.json com: name, description, entry_point, files (lista de ficheiros com path e desc)\n"
        f"- Testa o script para garantir que funciona antes de terminar\n"
        f"- Se nao for possivel, cria task.json com description a explicar o motivo\n"
        f"- Scripts Python correm com /usr/bin/python3\n"
        f"- ComfyUI API em http://192.168.0.187:8188\n"
        f"- Nao uses bibliotecas que nao estao instaladas (verifica com pip list ou tenta importar)"
    )

    result = _dispatch_task_impl({
        "target_profile": "developer",
        "task": prompt,
        "caller_profile": "orchestrator",
        "timeout": 600,
    })

    if "error" in result:
        return jsonify({"error": result["error"]}), 500

    return jsonify({"agent_id": result.get("agent_id"), "task_id": task_id, "status": "dispatched"})

@app.route("/api/scripts/status/<job_id>")
def api_scripts_status(job_id):
    with _task_jobs_lock:
        job = _task_jobs.get(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job)

# ─── Main ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AgentGUI Server v3.0")
    print(f"  Port: 5020")
    print(f"  Project: {project_root}")
    print(f"  Ollama Local: {OLLAMA_LOCAL_URL}")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5020, debug=False, allow_unsafe_werkzeug=True)

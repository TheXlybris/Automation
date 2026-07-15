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
            # Try to get duration via ffprobe
            duration = None
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(f)],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    duration = float(data.get("format", {}).get("duration", 0))
            except Exception:
                pass
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "duration": duration,
                "duration_human": f"{int(duration//60)}:{int(duration%60):02d}" if duration else None
            })
    return jsonify(files)

@app.route("/api/media/file/<filename>")
def api_media_file(filename):
    f = MEDIA_TEMP_DIR / filename
    if f.exists():
        return send_file(str(f))
    return jsonify({"error": "not found"}), 404

@app.route("/api/media/duration/<filename>")
def api_media_duration(filename):
    f = MEDIA_TEMP_DIR / filename
    if not f.exists():
        return jsonify({"error": "not found"}), 404
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(f)],
            capture_output=True, text=True, timeout=5
        )
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        return jsonify({"duration": duration})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

# ─── Main ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AgentGUI Server v3.0")
    print(f"  Port: 5020")
    print(f"  Project: {project_root}")
    print(f"  Ollama Local: {OLLAMA_LOCAL_URL}")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5020, debug=False, allow_unsafe_werkzeug=True)

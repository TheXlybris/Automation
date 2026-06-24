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

def save_profile_config(profile_id: str, config: dict):
    p = get_profile_config_path(profile_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2), encoding="utf-8")

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
    """Fetch available models from Ollama local + cloud defaults."""
    models = []

    # 1. Local Ollama
    try:
        r = _requests.get(f"{OLLAMA_LOCAL_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("models", []):
                name = m.get("name", "")
                if name.endswith(":latest"):
                    name = name.replace(":latest", "")
                models.append({
                    "id": m.get("name", ""),
                    "name": name,
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                    "source": "local"
                })
    except Exception:
        pass

    # 2. Cloud defaults
    cloud_defaults = [
        {"id": "kimi-k2.6", "name": "kimi-k2.6", "size": None, "source": "cloud"},
        {"id": "glm-5.2", "name": "glm-5.2", "size": None, "source": "cloud"},
        {"id": "deepseek-v4-pro", "name": "deepseek-v4-pro", "size": None, "source": "cloud"},
        {"id": "qwen3-coder:480b", "name": "qwen3-coder 480b", "size": None, "source": "cloud"},
    ]
    for cm in cloud_defaults:
        if cm["id"] not in [m["id"] for m in models]:
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

@app.route("/api/agents/<agent_id>/kill", methods=["POST"])
def api_kill_agent(agent_id):
    try:
        kill_agent(agent_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/delete_finished", methods=["POST"])
def api_delete_finished():
    try:
        count = delete_finished_agents()
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
        save_skills_config(profile_id, config)
        return jsonify({"success": True})

# ── Profile config (model selection — REAL) ──

@app.route("/api/profiles/<profile_id>/config", methods=["GET", "POST"])
def api_profile_config(profile_id):
    if request.method == "GET":
        return jsonify(load_profile_config(profile_id))
    else:
        config = request.json or {}
        save_profile_config(profile_id, config)
        return jsonify({"success": True})

# ── Orchestrator ──

@app.route("/api/orchestrator/inbox")
def api_orch_inbox():
    return jsonify(load_orch_inbox())

@app.route("/api/orchestrator/response", methods=["POST"])
def api_orch_response():
    data = request.json or {}
    text = data.get("text", "")
    profile = data.get("profile")
    socketio.emit("orchestrator_response", {"text": text, "profile": profile})
    return jsonify({"success": True})

@app.route("/api/orchestrator/mark_processed", methods=["POST"])
def api_orch_mark_processed():
    data = request.json or {}
    count = data.get("count", 0)
    state = load_orch_state()
    state["last_processed"] = count
    save_orch_state(state)
    return jsonify({"success": True})

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

@socketio.on("dispatch_task")
def handle_dispatch_task(data):
    """Real dispatch: creates task file, registers agent, launches tmux with model from profile config."""
    target_profile = data.get("target_profile", data.get("profile", "developer"))
    task_text = data.get("task", "")
    
    # Map short IDs to full profile names
    profile_map = {"dev": "developer", "mm": "multimedia", "res": "researcher", "wiki": "wiki", "dreamer": "dreamer"}
    profile = profile_map.get(target_profile, target_profile)
    
    agent_id = f"{profile}_{uuid.uuid4().hex[:8]}"
    
    # Load model from profile config
    config = load_profile_config(profile)
    model = config.get("model")
    
    # Create task file
    task_file = DATA_DIR / f"{agent_id}_task.json"
    task_data = {
        "id": agent_id,
        "profile": profile,
        "goal": task_text,
        "model": model,
        "created_at": datetime.now().isoformat()
    }
    task_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
    
    # Register in state
    register_agent(agent_id, profile, task_text, "")
    
    # Load skills config for the profile
    skills_config = load_skills_config(profile)
    enabled_skills = skills_config.get("enabled", [])
    
    # Launch with model
    result = launch_agent(profile, task_text, "", agent_id=agent_id, model=model)
    
    # Save to history
    save_history_entry({
        "id": agent_id,
        "profile": profile,
        "task": task_text,
        "model": model,
        "timestamp": datetime.now().isoformat(),
        "status": "dispatched"
    })
    
    emit("task_dispatched", {"id": agent_id, "profile": profile, "task": task_text, "model": model}, broadcast=True)

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
    emit("agents_list", list_agents(), broadcast=True)

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
    """Sync agent states every 5 seconds."""
    while True:
        try:
            sync_running_agents()
        except Exception as e:
            print(f"[sync_worker] Error: {e}")
        time.sleep(5)

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

threading.Thread(target=resources_worker, daemon=True).start()
threading.Thread(target=sync_worker, daemon=True).start()
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

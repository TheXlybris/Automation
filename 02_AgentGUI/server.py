#!/usr/bin/env python3
"""
AgentGUI Server v2.0 — Flask + Socket.IO for real-time agent monitoring.
Runs on http://0.0.0.0:5020

CHANGELOG:
- 2026-06-11: Migrated SSE → Socket.IO (bidirectional WebSocket)
- 2026-06-11: React frontend served as static files
- 2026-06-11: Added health check endpoint
- 2026-06-11: Kept all REST API endpoints for backwards compat
"""

import json
import time
import threading
import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

import subprocess

# Import core modules
project_root = Path(__file__).parent
os.chdir(project_root)
import sys
sys.path.insert(0, str(project_root))

from core.state import (
    register_agent, update_agent, get_agent,
    list_agents, cleanup_old_agents, get_last_update_timestamp
)
from core.runner import (
    launch_agent, get_agent_output, kill_agent,
    send_keys_to_agent, sync_running_agents
)
import psutil

# ─── Flask + Socket.IO setup ─────────────────────────
app = Flask(__name__, static_folder='static', static_url_path='/')
app.config['SECRET_KEY'] = 'agentgui-secret-key-change-me'
CORS(app, origins=['http://localhost:5173', 'http://192.168.0.188:5173', 'http://127.0.0.1:5173', 'http://localhost:5020', 'http://192.168.0.188:5020'])

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Shared state for Windows resources ──────────────────
windows_resources = {}

# ─── Orchestrator status cache ─────────────────────
orchestrator_status_cache = {"status": "offline", "mode": "brainstorm"}

# ─── REST API Routes ───────────────────────────────

@app.route("/api/agents")
def api_list_agents():
    profile = request.args.get("profile")
    status = request.args.get("status")
    return jsonify(list_agents(profile_filter=profile, status_filter=status))

@app.route("/api/agents/launch", methods=["POST"])
def api_launch_agent():
    data = request.json or {}
    profile = data.get("profile", "researcher")
    goal = data.get("goal", "No goal specified")
    prompt = data.get("prompt", goal)

    valid_profiles = ["researcher", "developer", "multimedia", "wiki"]
    if profile not in valid_profiles:
        return jsonify({"error": f"Invalid profile. Use: {valid_profiles}"}), 400

    agent_id = f"{profile}_{uuid.uuid4().hex[:8]}"
    task_file = Path(__file__).parent / "data" / f"{agent_id}_task.json"
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_data = {
        "id": agent_id,
        "profile": profile,
        "goal": goal,
        "prompt": prompt,
        "context": data.get("context", ""),
        "timeout_seconds": data.get("timeout_seconds", 1200)
    }
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2)

    register_agent(agent_id, profile, goal, f"python3 profiles/run_{profile}.py {agent_id}")
    agent = launch_agent(profile, goal, prompt, agent_id=agent_id)
    return jsonify(agent)

@app.route("/api/agents/<agent_id>/output")
def api_agent_output(agent_id):
    lines = request.args.get("lines", 100, type=int)
    output = get_agent_output(agent_id, lines=lines)
    return jsonify({"agent_id": agent_id, "output": output})

@app.route("/api/agents/<agent_id>/kill", methods=["POST"])
def api_kill_agent(agent_id):
    success = kill_agent(agent_id)
    if success:
        return jsonify({"success": True, "message": f"Agent {agent_id} terminado"})
    return jsonify({"success": False, "error": "Failed to kill agent"}), 500

@app.route("/api/agents/<agent_id>")
def api_get_agent(agent_id):
    agent = get_agent(agent_id)
    if agent:
        return jsonify(agent)
    return jsonify({"error": "Agent not found"}), 404

# ─── Socket.IO Events ──────────────────────────────

@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'ok', 'agents': list_agents()})

@socketio.on('disconnect')
def handle_disconnect():
    pass

@socketio.on('launch_agent')
def handle_launch(data):
    profile = data.get('profile', 'researcher')
    goal = data.get('goal', 'No goal specified')
    prompt = data.get('prompt', goal)

    valid_profiles = ['researcher', 'developer', 'multimedia', 'wiki']
    if profile not in valid_profiles:
        emit('error', {'message': f'Invalid profile. Use: {valid_profiles}'})
        return

    agent_id = f"{profile}_{uuid.uuid4().hex[:8]}"
    task_file = Path(__file__).parent / "data" / f"{agent_id}_task.json"
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_data = {
        "id": agent_id, "profile": profile, "goal": goal,
        "prompt": prompt, "context": data.get('context', ''),
        "timeout_seconds": data.get('timeout_seconds', 1200)
    }
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2)

    register_agent(agent_id, profile, goal, f"python3 profiles/run_{profile}.py {agent_id}")
    agent = launch_agent(profile, goal, prompt, agent_id=agent_id)
    emit('agent_launched', agent)
    broadcast_agents()

@socketio.on('kill_agent')
def handle_kill(data):
    agent_id = data.get('agent_id')
    success = kill_agent(agent_id)
    emit('agent_killed', {'agent_id': agent_id, 'success': success})
    broadcast_agents()

@socketio.on('get_output')
def handle_get_output(data):
    agent_id = data.get('agent_id')
    lines = data.get('lines', 100)
    output = get_agent_output(agent_id, lines=lines)
    emit('agent_output', {'agent_id': agent_id, 'output': output})

@socketio.on('send_input')
def handle_send_input(data):
    agent_id = data.get('agent_id')
    text = data.get('text', '')
    success = send_keys_to_agent(agent_id, text)
    emit('input_sent', {'agent_id': agent_id, 'success': success})

@socketio.on('refresh_agents')
def handle_refresh():
    emit('agents_list', list_agents())

@socketio.on('dispatch_task')
def handle_dispatch_task(data):
    """Receives task dispatch from AgentPanel and stores it."""
    profile = data.get('target_profile', 'unknown')
    task = data.get('task', '')
    timestamp = datetime.now().isoformat()
    entry = {
        'id': f"{profile}_{uuid.uuid4().hex[:8]}",
        'profile': profile,
        'task': task,
        'status': 'running',
        'time': timestamp
    }
    # Persist to history file
    history_file = Path(__file__).parent / "data" / "history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
    history.insert(0, entry)
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)
    emit('task_dispatched', entry)
    broadcast_agents()

@socketio.on('orchestrator_message')
def handle_orchestrator_message(data):
    """Receives chat message from dashboard, broadcasts typing indicator."""
    text = data.get('text', '')
    if not text:
        return
    # Store in inbox for potential external processing
    inbox_file = Path(__file__).parent / "data" / "orchestrator_inbox.json"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox = []
    if inbox_file.exists():
        try:
            with open(inbox_file, 'r', encoding='utf-8') as f:
                inbox = json.load(f)
        except Exception:
            inbox = []
    inbox.append({'role': 'user', 'text': text, 'time': datetime.now().isoformat()})
    with open(inbox_file, 'w', encoding='utf-8') as f:
        json.dump(inbox, f, indent=2)
    # Broadcast typing indicator to all clients
    socketio.emit('orchestrator_typing', {})
    # Also broadcast the message so agent can pick it up
    socketio.emit('orchestrator_message', {'text': text})
    emit('message_received', {'status': 'ok'})

@socketio.on('orchestrator_mode_change')
def handle_mode_change(data):
    """Receives mode change request from frontend, broadcasts to agent."""
    mode = data.get('mode', 'brainstorm')
    # Persist mode
    mode_file = Path(__file__).parent / "data" / "orchestrator_mode.json"
    mode_file.parent.mkdir(parents=True, exist_ok=True)
    with open(mode_file, 'w', encoding='utf-8') as f:
        json.dump({'mode': mode}, f)
    socketio.emit('orchestrator_mode_change', {'mode': mode})
    emit('mode_changed', {'mode': mode})

@socketio.on('orchestrator_summarize')
def handle_summarize(data):
    """Receives summarize request from frontend, broadcasts to agent."""
    socketio.emit('orchestrator_summarize', data)
    emit('summarize_triggered', {'status': 'ok'})

@socketio.on('orchestrator_ready')
def handle_orchestrator_ready(data):
    """Agent notifies it's ready."""
    global orchestrator_status_cache
    print(f"[INFO] Orchestrator agent ready: {data}")
    orchestrator_status_cache = {"status": "online", "mode": data.get("mode", "brainstorm")}
    socketio.emit('orchestrator_status', orchestrator_status_cache)

@socketio.on('orchestrator_response')
def handle_orchestrator_response_socket(data):
    """Agent emits response via Socket.IO — rebroadcast to all clients."""
    global orchestrator_status_cache
    text = data.get('text', '')
    mode = data.get('mode', '')
    if text:
        orchestrator_status_cache["status"] = "online"
        if mode:
            orchestrator_status_cache["mode"] = mode
        socketio.emit('orchestrator_response', {'text': text, 'mode': mode})

@socketio.on('orchestrator_typing')
def handle_orchestrator_typing_socket(data):
    """Agent emits typing indicator — rebroadcast to all clients."""
    global orchestrator_status_cache
    orchestrator_status_cache["status"] = "online"
    socketio.emit('orchestrator_typing', {})

@socketio.on('orchestrator_status')
def handle_orchestrator_status(data):
    """Handle status from agent."""
    global orchestrator_status_cache
    if data and data.get("status"):
        orchestrator_status_cache = data
        socketio.emit('orchestrator_status', orchestrator_status_cache)

# ─── REST API for orchestrator responses ─────────

@app.route("/api/orchestrator/response", methods=["POST"])
def api_orchestrator_response():
    """External systems (Hermes TUI) can POST responses here."""
    data = request.json or {}
    text = data.get("text", "")
    profile = data.get("profile", None)
    if not text:
        return jsonify({"error": "Missing text"}), 400
    socketio.emit('orchestrator_response', {'text': text, 'profile': profile})
    return jsonify({"success": True})

@app.route("/api/history")
def api_history():
    """Return task history."""
    history_file = Path(__file__).parent / "data" / "history.json"
    history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
    return jsonify(history)

@app.route("/api/orchestrator/inbox")
def api_orchestrator_inbox():
    """Return unread orchestrator messages."""
    inbox_file = Path(__file__).parent / "data" / "orchestrator_inbox.json"
    inbox = []
    if inbox_file.exists():
        try:
            with open(inbox_file, 'r', encoding='utf-8') as f:
                inbox = json.load(f)
        except Exception:
            inbox = []
    return jsonify(inbox)

def broadcast_agents():
    agents = list_agents()
    socketio.emit('agents_updated', {'agents': agents})

# ─── Background sync thread ─────────────────────────
def sync_worker():
    while True:
        time.sleep(5)
        try:
            sync_running_agents()
            cleanup_old_agents(max_age_hours=24)
            broadcast_agents()
        except Exception:
            pass

sync_thread = threading.Thread(target=sync_worker, daemon=True)
sync_thread.start()

# ─── Resource monitoring thread ────────────────────
NVIDIA_SMI_AVAILABLE = shutil.which('nvidia-smi') is not None

def get_gpu_info():
    if not NVIDIA_SMI_AVAILABLE:
        return None
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            if len(parts) == 4:
                return {
                    'name': parts[0],
                    'vram_used_mb': int(parts[1]),
                    'vram_total_mb': int(parts[2]),
                    'gpu_percent': int(parts[3])
                }
    except Exception:
        pass
    return None

def get_system_resources():
    cpu_perc = psutil.cpu_percent(interval=None)
    cpu_freq = psutil.cpu_freq()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    resources = {
        'cpu': {
            'percent': round(cpu_perc, 1),
            'cores': psutil.cpu_count(logical=True),
            'freq_mhz': round(cpu_freq.current, 0) if cpu_freq else 0
        },
        'ram': {
            'used_gb': round(ram.used / (1024**3), 1),
            'total_gb': round(ram.total / (1024**3), 1),
            'percent': ram.percent
        },
        'disk': {
            'used_gb': round(disk.used / (1024**3), 1),
            'total_gb': round(disk.total / (1024**3), 1),
            'percent': round(disk.percent, 1)
        },
        'gpu': get_gpu_info()
    }
    return resources

def resource_worker():
    while True:
        time.sleep(2)
        try:
            vm_resources = get_system_resources()
            combined = {
                'vm': vm_resources,
                'windows': windows_resources if windows_resources else None,
                'timestamp': time.time()
            }
            socketio.emit('resources_update', combined)
        except Exception:
            pass

resource_thread = threading.Thread(target=resource_worker, daemon=True)
resource_thread.start()

# ─── Orchestrator bridge poll thread ───────────────
orchestrator_state = {
    'last_processed': 0,
    'processing': False
}

# ─── Launch Orchestrator Agent subprocess ────────────
_orchestrator_process = None

def start_orchestrator_agent():
    """Inicia o orchestrator_agent.py como subprocesso independente."""
    global _orchestrator_process
    agent_script = Path(__file__).parent / "orchestrator_agent.py"
    if not agent_script.exists():
        print("[WARN] orchestrator_agent.py não encontrado. Orquestrador offline.")
        return
    
    venv_python = Path.home() / "venv_agentgui" / "bin" / "python"
    if not venv_python.exists():
        venv_python = Path("/usr/bin/python3")
    
    try:
        env = os.environ.copy()
        # Carregar API keys do ~/.hermes/.env se não estiverem no ambiente
        hermes_env = Path.home() / ".hermes" / ".env"
        if hermes_env.exists():
            try:
                with open(hermes_env, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, val = line.split('=', 1)
                            if key not in env:
                                env[key] = val
            except Exception:
                pass
        # Log file for orchestrator agent
        log_file = Path("/tmp/orchestrator_agent.log")
        log_file.write_text(f"[{datetime.now().isoformat()}] Orchestrator Agent starting...\n")
        _orchestrator_process = subprocess.Popen(
            [str(venv_python), str(agent_script)],
            stdout=open(str(log_file), 'a'),
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).parent),
            env=env,
            text=True
        )
        print(f"[OK] Orchestrator Agent iniciado (PID {_orchestrator_process.pid})")
        print(f"[INFO] Logs do agente em: {log_file}")
    except Exception as e:
        print(f"[ERROR] Falha a iniciar orchestrator_agent.py: {e}")

def stop_orchestrator_agent():
    global _orchestrator_process
    if _orchestrator_process:
        _orchestrator_process.terminate()
        try:
            _orchestrator_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _orchestrator_process.kill()
        print("[INFO] Orchestrator Agent terminado.")
        _orchestrator_process = None

def bridge_poll_worker():
    """Polls orchestrator inbox and notifies when new messages arrive."""
    inbox_file = Path(__file__).parent / "data" / "orchestrator_inbox.json"
    state_file = Path(__file__).parent / "data" / "orchestrator_state.json"
    while True:
        time.sleep(3)
        try:
            # Load current state
            if state_file.exists():
                try:
                    with open(state_file, 'r', encoding='utf-8') as f:
                        orchestrator_state.update(json.load(f))
                except Exception:
                    pass
            
            # Check inbox
            if not inbox_file.exists():
                continue
            
            with open(inbox_file, 'r', encoding='utf-8') as f:
                inbox = json.load(f)
            
            if not inbox:
                continue
            
            last_idx = orchestrator_state.get('last_processed', 0)
            new_count = len(inbox) - last_idx
            
            if new_count > 0:
                # Process each new message
                for msg in inbox[last_idx:]:
                    text = msg.get('text', '')
                    # Broadcast to all connected clients that a message needs response
                    socketio.emit('orchestrator_needs_response', {
                        'text': text,
                        'time': msg.get('time', '')
                    })
                
                orchestrator_state['last_processed'] = len(inbox)
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(orchestrator_state, f, indent=2)
        except Exception:
            pass

bridge_thread = threading.Thread(target=bridge_poll_worker, daemon=True)
bridge_thread.start()

# ─── REST API to mark inbox processed ──────────────
@app.route("/api/orchestrator/mark_processed", methods=["POST"])
def api_mark_processed():
    """Mark inbox as fully processed (clear unread)."""
    state_file = Path(__file__).parent / "data" / "orchestrator_state.json"
    inbox_file = Path(__file__).parent / "data" / "orchestrator_inbox.json"
    try:
        if inbox_file.exists():
            with open(inbox_file, 'r', encoding='utf-8') as f:
                inbox = json.load(f)
            count = len(inbox)
        else:
            count = 0
        state = {'last_processed': count, 'processing': False}
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        return jsonify({"success": True, "marked_count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/orchestrator/state")
def api_orchestrator_state():
    """Return orchestrator state (last_processed, processing)."""
    state_file = Path(__file__).parent / "data" / "orchestrator_state.json"
    state = {'last_processed': 0, 'processing': False}
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception:
            pass
    return jsonify(state)
@app.route("/api/orchestrator/status")
def api_orchestrator_status():
    """Return orchestrator cached status (online/offline, mode)."""
    return jsonify(orchestrator_status_cache)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    static_path = Path(__file__).parent / 'static'
    if path and (static_path / path).exists():
        return send_from_directory(static_path, path)
    return send_from_directory(static_path, 'index.html')

# ─── Health Check ──────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "socket_io": True, "version": "2.0.0"})

# ─── Windows Resource Receiver ─────────────────────
@app.route("/api/resources/windows", methods=["POST"])
def receive_windows_resources():
    global windows_resources
    data = request.json
    if data:
        windows_resources = data
        return jsonify({"success": True, "message": "Windows resources received"})
    return jsonify({"error": "No data received"}), 400

# ─── Main ─────────────────────────────────────────
if __name__ == "__main__":
    print("╔════════════════════════════════════════╗")
    print("║  AGENTGUI v2.0 — React + Socket.IO     ║")
    print("║  http://192.168.0.188:5020             ║")
    print("╚════════════════════════════════════════╝")
    # Iniciar agente orquestrador
    start_orchestrator_agent()
    socketio.run(app, host='0.0.0.0', port=5020, allow_unsafe_werkzeug=True)

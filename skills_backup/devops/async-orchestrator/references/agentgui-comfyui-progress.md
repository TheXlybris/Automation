# AgentGUI Progress Tracking — Real-Time ComfyUI Progress

## Problem
The AgentGUI dashboard shows progress stuck at 30% ("A invocar hermes chat -q...") for the entire duration of a ComfyUI generation. The progress only updates when the Hermes agent finishes. The user sees a flat progress bar for 5+ minutes.

## Architecture Options for Real Progress

### Option A: WebSocket Watcher in Runner (Complex)
The `run_multimedia.py` opens a WebSocket connection to ComfyUI's `ws://host:8188/ws`, listens for `execution` events (sampler steps), and calls `update_agent()` in real time.
- **Problem:** The runner needs to know the `prompt_id`, which is only known to the script the Hermes agent creates and runs. The runner and the agent are decoupled.

### Option B: Progress File (Recommended — Simple)
The generation script (e.g., `generate_fantasy_isolated.py`) writes progress to a JSON file at a known path. The runner or the Flask server reads this file periodically (every 2-5s) and updates the agent state.

```python
# In the generation script
PROGRESS_FILE = Path(os.environ.get("AGENTUI_DIR", "/mnt/d/AI_Ecosystem/10_Projects/02_AgentGUI")) / "data" / f"{os.environ.get('AGENT_ID', 'unknown')}_progress.json"

def report_progress(step: int, total: int, message: str):
    progress = {
        "step": step,
        "total": total,
        "percent": int(step / total * 100) if total else 0,
        "message": message,
        "timestamp": time.time(),
    }
    PROGRESS_FILE.write_text(json.dumps(progress), encoding="utf-8")

# During generation
report_progress(10, 70, "ComfyUI: sampling step 10/70")
```

The Flask server or runner reads:
```python
progress_path = BASE_DIR / "data" / f"{agent_id}_progress.json"
if progress_path.exists():
    progress = json.loads(progress_path.read_text())
    update_agent(agent_id, progress=30 + int(progress["percent"] * 0.6),
                 message=progress["message"])
```

**Advantage:** Decoupled — generation script doesn't need to import the state module. Just writes a file.

### Option C: Runner Calls ComfyUI Directly (Sacrifices Agent Intelligence)
The runner bypasses Hermes entirely for ComfyUI tasks. It submits the workflow directly and controls the WebSocket. Progress is exact but the runner must hardcode workflow selection, prompt crafting, etc.

**Trade-off:** Loses the Hermes agent's ability to decide workflows, adapt prompts, handle errors creatively.

### Option D: Agent Writes to Shared Memory (Medium)
The Hermes agent has access to the same `core.state` module. It can call `update_agent()` directly during execution.
- **Problem:** The agent runs inside `hermes chat -q` with `--ignore-rules`, which means it doesn't have the same Python environment as the runner. The `core.state` module path may not be in `sys.path`.
- **Workaround:** Add the AgentGUI directory to `sys.path` in the agent's script.

## ComfyUI WebSocket Event Format

ComfyUI emits events on `ws://host:8188/ws`:

```json
{"type": "status", "data": {"status": {"exec_info": {"queue_remaining": 1}}}}
{"type": "execution_start", "data": {"prompt_id": "abc-123"}}
{"type": "executing", "data": {"node": "14", "prompt_id": "abc-123"}}
{"type": "progress", "data": {"value": 10, "max": 70}}
{"type": "executed", "data": {"node": "9", "prompt_id": "abc-123", "output": {"images": [{"filename": "..."}]}}}
{"type": "execution_success", "data": {"prompt_id": "abc-123"}}
```

The `progress` event is emitted by the KSampler node — `value` = current step, `max` = total steps. This maps directly to a percentage.

## Recommended Implementation (Option B + D Hybrid)

For THE RENDER WAVE AgentGUI, the recommended approach:

1. **Hermes agent script** writes `_progress.json` to the AgentGUI data dir
2. **Flask server** polls `_progress.json` files every 3s via background thread
3. **Dashboard** receives progress via SSE from Flask

This gives the agent freedom to use any tool (ComfyUI, ffmpeg, analysis) while the dashboard shows real progress.

## File Locations

| File | Purpose |
|------|---------|
| `data/{agent_id}_progress.json` | Real-time progress from generation script |
| `core/state.py` | `update_agent()` — atomic JSON state update |
| `server.py` | Background thread that polls progress files and pushes SSE |
| `static/app.js` | SSE client that updates progress bars |

## Code Example: Progress-Aware Generation Script

```python
#!/usr/bin/env python3
import json, time, os
from pathlib import Path

AGENT_ID = os.environ.get("AGENT_ID", "unknown")
BASE_DIR = Path(os.environ.get("AGENTUI_DIR", "/mnt/d/AI_Ecosystem/10_Projects/02_AgentGUI"))
PROGRESS_FILE = BASE_DIR / "data" / f"{AGENT_ID}_progress.json"

def report_progress(percent: int, message: str):
    PROGRESS_FILE.write_text(json.dumps({
        "percent": percent, "message": message, "timestamp": time.time()
    }), encoding="utf-8")

# During ComfyUI polling
def poll_with_progress(prompt_id: str, total_steps: int = 70):
    report_progress(5, "ComfyUI: job queued")
    # ... wait for execution_start ...
    report_progress(10, "ComfyUI: execution started")
    # ... during sampling, if WebSocket available ...
    for step in range(1, total_steps + 1):
        # after each progress event
        report_progress(10 + int(step / total_steps * 80),
                       f"ComfyUI: sampling step {step}/{total_steps}")
        time.sleep(0.5)  # placeholder
    report_progress(95, "ComfyUI: decoding VAE")
    # ... after completion ...
    report_progress(100, "ComfyUI: done")
```

## Polling Thread in Flask Server

```python
import threading, time, json
from pathlib import Path
from core.state import update_agent

def progress_poller():
    while True:
        time.sleep(3)
        data_dir = Path(__file__).parent / "data"
        for progress_file in data_dir.glob("*_progress.json"):
            agent_id = progress_file.stem.replace("_progress", "")
            try:
                progress = json.loads(progress_file.read_text())
                # Map 0-100 from ComfyUI to 30-100 in agent state
                # (30 = hermes invocation, 100 = done)
                mapped = 30 + int(progress["percent"] * 0.7)
                update_agent(agent_id, progress=min(99, mapped),
                              message=progress["message"])
            except Exception:
                pass

# Start in server.py
poller_thread = threading.Thread(target=progress_poller, daemon=True)
poller_thread.start()
```

## Notes
- Progress files should be cleaned up when agent finishes (in `sync_running_agents()` or runner cleanup)
- If `_progress.json` is stale (>60s), ignore it — agent may have crashed
- The `percent` field is 0-100 from the generation script; the server maps it to the agent's overall progress range

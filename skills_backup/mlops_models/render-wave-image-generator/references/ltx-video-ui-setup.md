# LTX Video 2B — Web UI Setup for Manual Generation

**Date:** 2026-05-11
**Context:** THE RENDER WAVE — Flask + SSE + WebSocket bridge for real-time ComfyUI progress

## Architecture

```
┌─────────────┐      SSE        ┌──────────────┐      WebSocket     ┌──────────┐
│  Browser    │ ←────────────── │ Flask server │ ←──────────────── │ ComfyUI  │
│  (index.html)│                │  (server.py) │                   │  :8188   │
└─────────────┘   POST /generate └──────────────┘   /prompt, /upload └──────────┘
```

## Files

| File | Path | Purpose |
|------|------|---------|
| `index.html` | `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Video_creation\ui\index.html` | Dark-themed standalone UI — no build step, no frameworks |
| `server.py` | `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Video_creation\ui\server.py` | Flask backend — upload, submit, WebSocket→SSE bridge |
| `.venv/` | `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Video_creation\ui\.venv\` | Python venv with `flask`, `requests`, `websocket-client` |

## Venv Setup

```bash
cd D:/AI_Ecosystem/10_Projects/01_YTAutomation/Video_creation/ui
python3 -m venv .venv
.venv/bin/pip install flask requests websocket-client
```

**Pitfall — PEP 668 (Debian/Ubuntu):** `pip install flask` directly fails with `externally-managed-environment`. Always use a venv. The venv is created inside the UI folder for portability.

## Running the Server

```bash
cd D:/AI_Ecosystem/10_Projects/01_YTAutomation/Video_creation/ui
.venv/bin/python server.py --host 0.0.0.0 --port 5000
```

**Access:**
- WSL browser: `http://localhost:5000`
- Windows browser: `http://<WSL_IP>:5000` (discover IP via `ip addr show eth0` in WSL)

## Frontend (index.html) — Features

| Feature | Implementation |
|---------|---------------|
| Dropzone | `dragover`/`dragleave`/`drop` events + hidden `<input type="file">` |
| Image preview | `URL.createObjectURL(file)` → `<img>` |
| Sliders | `input[type="range"]` with live value display |
| Duration | 1–10 seconds; backend converts to frames = `duration × fps` |
| Progress bar | CSS `width` transition driven by SSE `progress` messages |
| Log | Monospace scroll box with timestamps and color-coded severity |
| Video preview | `<video controls loop muted>` with `src` from `/video/` endpoint |
| Downloads | Links to original MP4, upscaled MP4, and prompts.txt |

## Backend (server.py) — Endpoints

### `POST /generate`
Receives `multipart/form-data`:
- `image` — PNG/JPG file
- `positive`, `negative` — prompts
- `duration`, `strength`, `steps`, `cfg`, `fps` — numeric params
- `seed` — `-1` or fixed integer
- `upscale` — `"true"` or `"false"`

Actions:
1. Saves uploaded image to `temp_uploads/`
2. Loads `Image2Video_LTXV.json` workflow
3. Injects params into nodes `77`, `6`, `7`, `71`, `72`, `80`, `69`
4. Uploads image to ComfyUI `/upload/image`
5. Submits workflow to ComfyUI `/prompt`
6. Spawns daemon thread for `run_pipeline(job_id, ...)`
7. Returns `{"job_id": "job_..."}`

### `GET /progress/<job_id>`
SSE endpoint. Streams JSON lines:
- `{"type": "status", "message": "..."}` — phase messages
- `{"type": "progress", "percent": 42, "step": 21, "total": 50}` — generation progress
- `{"type": "node", "node": "KSampler"}` — current node executing
- `{"type": "done", "video_path": "...", "upscale_path": "...", "txt_path": "..."}` — success
- `{"type": "error", "message": "..."}` — failure

### `GET /video/<filename>`
Serves MP4/TXT files from ComfyUI output folder via `send_from_directory`.

**Pitfall — path mismatch:** `send_from_directory` runs in WSL Python and needs WSL paths (`/mnt/d/...`). A Windows path (`D:\...`) will fail silently or raise `FileNotFoundError`.

## WebSocket Progress Bridge

The `comfyui_ws_listener()` function connects to `ws://192.168.144.1:8188/ws` and parses ComfyUI message types:

| ComfyUI WS Type | Mapped SSE Type | Fields |
|-----------------|-----------------|--------|
| `status` | `queue` | `queue_remaining` |
| `progress` | `progress` | `value`, `max`, `prompt_id` |
| `execution_start` | `status` | prompt_id match check |
| `executing` | `node` | `node` (node ID) |
| `execution_cached` | `status` | prompt_id match check |

**Pitfall — WebSocket missing:** If `websocket-client` is not installed, the listener emits a warning and returns. The pipeline still works (polling loop finds the video), but the progress bar stays at 0% until completion.

## Thread Safety

- `jobs = {}` dictionary guarded by GIL (Python dict operations are thread-safe for simple get/set)
- Each job has its own `queue.Queue()` — no shared queues
- WebSocket listener and polling loop run in separate daemon threads, both feeding the same job queue
- SSE endpoint blocks on `queue.get(timeout=1200)` — terminates when `done` or `error` message arrives

## Extending the UI

To add new parameters:
1. Add slider/input to `index.html` with an ID
2. Append to FormData in the `generateBtn` click handler
3. Read via `request.form.get()` in `generate()` endpoint
4. Inject into the correct workflow node ID in `run_pipeline()`

## File Browser (2026-05-11 addition)

The UI includes a modal file browser to select images from the Windows filesystem (`D:\AI_Ecosystem\`) without relying on the browser's native file picker (which only sees WSL paths when running Chrome inside WSL).

**Why a custom file browser is required:**
When Chrome runs under WSL (via WSLg or `google-chrome` from apt), the GTK file picker spawned by `<input type="file">` only sees the WSL root filesystem. It does NOT mount `/mnt/d/` in the picker dialog. The user sees empty or limited folders. The only way to browse `D:\AI_Ecosystem\` from the browser is to have the backend Python process do the filesystem traversal and return JSON to the frontend.

**UI elements:**
- Button "📂 Procurar em D:" opens modal overlay
- Breadcrumb navigation (click any path segment to jump)
- Folder list (📁) — click to enter
- File list (🖼️ for images, 🎬 for videos) — click to select (highlighted)
- "Selecionar" button loads the image into the dropzone preview

**Backend endpoints:**
- `GET /api/browse?path=/mnt/d/...` — lists directories + media files, with `parent` for "up"
- `GET /api/load-image?path=/mnt/d/...` — serves image as blob (converted to `File` in frontend)

**Roots permitted:**
- `/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output`
- `/mnt/d/AI_Ecosystem/04_Data/Hermes/images/output`
- Any subpath under `/mnt/d/AI_Ecosystem/`

**Security:** `_safe_path()` uses `os.path.realpath()` and prefix checks to prevent directory traversal outside permitted roots.

**Implementation notes:**
- The file browser is pure HTML/JS — no external libraries
- The `browserCrumb()` and `browserNav()` functions reconstruct WSL paths from breadcrumb indices
- Selected image is fetched as blob, wrapped in `File()`, and passed to the same `handleFile()` function used by drag-and-drop

**Critical layout rule:** The modal overlay markup must be a direct child of `<body>`, outside any content wrapper like `<div class="container">`. If nested inside `.container`, CSS `position: fixed` is relative to the container, not the viewport, causing the modal to be clipped or the entire page to appear empty.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Failed to fetch` on `/generate` | Server not running or wrong URL | Check `server.py` is listening on correct host/port; use absolute URLs in fetch |
| Progress bar stuck at 0% | WebSocket not connected | Verify `websocket-client` installed; check ComfyUI WebSocket is enabled (`--listen 0.0.0.0`) |
| Video not found after generation | Wrong `OUTPUT_FOLDER` path | Confirm WSL path `/mnt/d/...` in `server.py` |
| SSE connection drops | Network timeout | SSE auto-reconnects; if not, check `threaded=True` in `app.run()` |
| `externally-managed-environment` | PEP 668 blocked pip | Use venv: `python3 -m venv .venv` |

---
topic: "Vision and Multimodal Tools with Ollama"
description: "Pattern for creating Hermes tools that process video/images via Ollama vision models. Covers ffmpeg frame extraction, base64 encoding, and the Ollama /api/chat images[] array."
scope: hermes-agent, ollama, vision-models, ffmpeg, base64
---

# Vision & Multimodal Tools with Ollama

## Overview

Hermes can analyze video and images via Ollama vision models by:
1. Extracting frames from video with `ffmpeg`
2. Encoding frames as base64
3. Sending them in the `images: []` array of the Ollama `/api/chat` payload

This reference documents the VAO (Video Analysis Ollama) pattern, which is the second major custom tool built with the Ollama toolchain.

## Prerequisites

- `ffmpeg` installed and on PATH
- Ollama vision model pulled (e.g. `ollama pull qwen3-vl:30b-a3b-instruct`)
- Model supports base64 image input (most vision models on Ollama do)

## Pattern: Extract Frames with ffmpeg

```python
import subprocess
import tempfile
import base64
from pathlib import Path

def _extract_frames(video_path: str, fps: float = 1.0, max_frames: int = 30) -> list:
    """
    Extract frames from video using ffmpeg at specified FPS,
    returning list of (filename, base64_string) tuples.
    """
    # Get video duration
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())
    
    # Calculate actual frame count
    total_frames = int(duration * fps)
    actual_frames = min(total_frames, max_frames)
    
    if actual_frames <= 0:
        return []
    
    # Extract evenly-distributed frames
    interval = duration / actual_frames
    frames = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(actual_frames):
            timestamp = i * interval
            frame_path = Path(tmpdir) / f"frame_{i:04d}.jpg"
            cmd = [
                "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
                "-vframes", "1", "-q:v", "2", str(frame_path)
            ]
            subprocess.run(cmd, capture_output=True, check=False)
            if frame_path.exists():
                with open(frame_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                frames.append((frame_path.name, b64))
    
    return frames
```

**Pitfall:** Do NOT use `-vf fps=X` with `-i` input following it. Use `-ss` before `-i` for faster seeking, or `-vf select='...'` for complex frame selection. For evenly-spaced frames, the loop interval approach above is simplest.

**Pitfall:** WSL file paths like `/mnt/d/...` work fine with subprocess/ffmpeg because Python has native access. But if exposing a web UI frontend, the GTK file picker won't see `/mnt/d/` — see SKILL.md for the symlink/WSLg caveats.

## Pattern: Send Images to Ollama Vision Model

```python
def _analyze_with_vision(
    model: str,
    user_prompt: str,
    frames_b64: list,
    endpoint: str = "http://127.0.0.1:11434"
) -> str:
    """
    Send text + images to Ollama vision model.
    Returns the model's analysis text.
    """
    messages = [{
        "role": "user",
        "content": user_prompt,
        "images": frames_b64  # list of base64 strings
    }]
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    
    resp = requests.post(
        f"{endpoint}/api/chat",
        json=payload,
        timeout=300
    )
    
    if resp.status_code == 200:
        return resp.json().get("message", {}).get("content", "")
    else:
        raise RuntimeError(f"Ollama error: HTTP {resp.status_code}")
```

**Key point:** The `images` field goes inside the message dict, at the same level as `content`. This is the Ollama API format for vision.

## Pattern: Environment-Based Configuration

Both MOAO and VAO use the same env-var pattern for dual local/cloud operation:

```python
# Endpoint selection
OLLAMA_LOCAL_URL = "http://127.0.0.1:11434"
OLLAMA_CLOUD_URL = "https://ollama.com/api"

# Mode: "local" | "cloud" | "auto"
MODE = os.getenv("VAO_MODE", "auto")  # or MOAO_MODE

# Model selection
MODEL = os.getenv("VAO_MODEL", "qwen3-vl:30b-a3b-instruct")

# Feature-specific tuning
FPS = float(os.getenv("VAO_FPS", "1.0"))
MAX_FRAMES = int(os.getenv("VAO_MAX_FRAMES", "30"))
```

| Mode | Behavior |
|------|----------|
| `local` | Always uses `OLLAMA_LOCAL_URL`, fails if Ollama not running |
| `cloud` | Always uses `OLLAMA_CLOUD_URL`, requires `OLLAMA_API_KEY` |
| `auto` | Tries local first; falls back to cloud if local unavailable |

**Why this pattern:** It lets the same tool work for both development (local, free, private) and production (cloud, always-on, no local GPU needed) without code changes.

## Full Working Example: Video Analysis Ollama (VAO)

Complete implementation at:
```
~/.hermes/hermes-agent/tools/video_analyze_ollama.py
```

**Key design decisions:**
- Frame rate and max frames are configurable via env vars (default 1 fps, max 30 frames)
- Works with Qwen-VL models locally (qwen3-vl:30b-a3b-instruct, ~18GB VRAM) or cloud (qwen3-vl:235b-cloud)
- Returns structured JSON with `frames_sent`, `model_used`, `processing_time`, `mode`
- Tested with 349KB MP4 clip — extracted 3 frames, analyzed in ~135 seconds on RTX 4060 Ti

## Pitfalls

| Pitfall | Cause | Fix |
|---------|-------|-----|
| Empty image array | ffmpeg failed silently | Check `frame_path.exists()` before encoding |
| OOM during analysis | Vision models are heavy (18-35GB) | Use lower-res frames (`-s 512x512`), or cloud mode |
| 404 from Ollama | Using `/chat` instead of `/api/chat` | Always use `POST /api/chat` |
| WSL path not found | File picker in browser can't see `/mnt/d/` | Use direct paths or custom file browser backend |
| Model not vision-capable | Pulled a text-only model | Check model supports `vision` tag in `/api/tags` |
| Long processing time | Too many frames or high-res images | Reduce `fps` and `max_frames`, use lower `-q:v` |

## Model Selection for Vision Tasks

| Use Case | Model | VRAM | Notes |
|----------|-------|------|-------|
| Local vision analysis | qwen3-vl:30b-a3b-instruct | ~18GB | Best quality for single GPU |
| Cloud vision analysis | qwen3-vl:235b-cloud | N/A | Highest quality, requires cloud plan |
| Lightweight vision | qwen2-vl:7b | ~5GB | Faster, less capable |

## References

- Ollama vision docs: https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion-with-images
- VAO implementation: `~/.hermes/hermes-agent/tools/video_analyze_ollama.py`
- ffmpeg frame extraction: https://trac.ffmpeg.org/wiki/Create%20a%20thumbnail%20image%20every%20X%20seconds%20of%20the%20video

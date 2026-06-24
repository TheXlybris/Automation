#!/usr/bin/env python3
"""
ImageAnimator Windows Service — Mini Flask server for GPU-accelerated video rendering.
Runs on Windows host (port 5021). Imports core/image_animator.py from the project.

Usage: python engines/image_animator_service.py
"""

import json
import os
import sys
import time
import uuid
import threading
import tempfile
from pathlib import Path

# ─── Project root ──────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from core.image_animator import EFFECT_REGISTRY

# ─── App ───────────────────────────────────────────
app = Flask(__name__)
CORS(app)

TEMP_DIR = PROJECT_ROOT / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ─── Path translator (VM path → Windows path) ──────
def vm_path_to_windows(vm_path: str) -> str:
    """Converte paths da VM (/media/sf_AI_Ecosystem/...) para paths do Windows (D:\AI_Ecosystem\...)."""
    if not vm_path:
        return vm_path
    # Strip any leading slashes and replace
    p = vm_path.replace("/", "\\")
    if p.startswith("\\media\\sf_AI_Ecosystem\\"):
        p = "D:\\AI_Ecosystem" + p[len("\\media\\sf_AI_Ecosystem"):]
    elif ":\\" not in p:
        # Assume relative to TEMP_DIR
        p = str(TEMP_DIR / os.path.basename(p))
    return p

# ─── Job state ─────────────────────────────────────
JOBS = {}  # job_id -> {"status": ..., "progress": ..., "filename": ..., "message": ...}

# ─── Endpoints ─────────────────────────────────────

@app.route("/api/video/effects", methods=["GET"])
def api_effects():
    return jsonify({
        "effects": [
            {"name": name, "label": getattr(cls, "label", name.replace("_", " ").title()), "params": cls.default_params()}
            for name, cls in EFFECT_REGISTRY.items()
        ]
    })


# ─── Upload endpoint (para imagens do frontend) ─────
UPLOAD_DIR = PROJECT_ROOT / "temp"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@app.route("/api/media/upload", methods=["POST"])
def api_upload():
    """Recebe upload de imagem PNG/JPEG/WebP, guarda em temp/."""
    from werkzeug.utils import secure_filename
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400
    safe = secure_filename(f.filename)
    path = UPLOAD_DIR / safe
    f.save(path)
    # Devolve path Windows para o frontend
    return jsonify({"success": True, "filename": safe, "path": str(path)})


@app.route("/api/video/animate", methods=["POST"])
def api_animate():
    data = request.get_json(force=True)
    image_path = vm_path_to_windows(data.get("image_path"))
    effects = data.get("effects", [])
    duration = data.get("duration", 10.0)
    fps = data.get("fps", 24)
    size = data.get("size")
    if size:
        size = tuple(size)

    if not image_path or not Path(image_path).exists():
        return jsonify({"error": "image_path missing or not found"}), 400

    job_id = f"win_{uuid.uuid4().hex[:12]}"
    output_file = TEMP_DIR / f"{job_id}.mp4"

    JOBS[job_id] = {
        "status": "running",
        "progress": 0.0,
        "filename": None,
        "message": "A iniciar...",
    }

    def _worker():
        try:
            from moviepy import ImageSequenceClip
            from PIL import Image
            import numpy as np

            base = Image.open(image_path).convert("RGBA")
            if size:
                base = base.resize(size, Image.Resampling.LANCZOS)
            w, h = base.size
            total_frames = int(duration * fps)
            layers = []
            for cfg in effects:
                name = cfg.get("name")
                params = cfg.get("params", {})
                if name not in EFFECT_REGISTRY:
                    raise ValueError(f"Efeito desconhecido: {name!r}")
                layers.append(EFFECT_REGISTRY[name](params))

            frames_np = []
            for i in range(total_frames):
                canvas = base.copy()
                for layer in layers:
                    overlay = layer.render(i, total_frames, base)
                    if overlay.size != (w, h):
                        overlay = overlay.resize((w, h), Image.Resampling.LANCZOS)
                    if overlay.mode == "RGBA":
                        arr = np.array(overlay)
                        mean_alpha = arr[:, :, 3].mean()
                        if mean_alpha > 250:
                            canvas = overlay
                        elif getattr(layer, "blend_mode", None) == "additive":
                            base_arr = np.array(canvas).astype(np.float32)
                            ov_arr = arr.astype(np.float32)
                            r = base_arr[:, :, :3] + ov_arr[:, :, :3] * (ov_arr[:, :, 3:4] / 255.0)
                            blended = np.clip(r, 0, 255).astype(np.uint8)
                            canvas = Image.fromarray(blended, "RGB").convert("RGBA")
                        else:
                            canvas = Image.alpha_composite(canvas, overlay)
                    else:
                        canvas = overlay.convert("RGBA")
                frames_np.append(np.array(canvas.convert("RGB")))
                JOBS[job_id]["progress"] = round((i + 1) / total_frames, 3)
                JOBS[job_id]["message"] = f"Frame {i + 1}/{total_frames}"

            clip = ImageSequenceClip(frames_np, fps=fps)
            clip.write_videofile(str(output_file), codec="libx264", audio=False, logger=None)
            clip.close()

            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["progress"] = 1.0
            JOBS[job_id]["filename"] = output_file.name
            JOBS[job_id]["message"] = "Concluído"

        except Exception as e:
            import traceback
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["message"] = f"{e}\n{traceback.format_exc()}"

    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/video/animate/status/<job_id>")
def api_animate_status(job_id):
    job = JOBS.get(job_id, {"status": "unknown", "message": "Job not found"})
    response = {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "message": job.get("message", ""),
    }
    if job.get("filename"):
        response["filename"] = job["filename"]
    return jsonify(response)


@app.route("/api/video/download/<filename>")
def api_download(filename):
    file_path = TEMP_DIR / filename
    if file_path.exists():
        return send_from_directory(TEMP_DIR, filename, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


@app.route("/api/media/file/<filename>")
def api_media_file(filename):
    """Servir ficheiro gerado para o frontend."""
    file_path = TEMP_DIR / filename
    if file_path.exists():
        return send_from_directory(TEMP_DIR, filename)
    return jsonify({"error": "File not found"}), 404


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "image_animator"})


# ─── Main ──────────────────────────────────────────
if __name__ == "__main__":
    print("╔════════════════════════════════════════╗")
    print("║  ImageAnimator Service — Windows GPU   ║")
    print("║  http://0.0.0.0:5021                   ║")
    print("╚════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5021, threaded=True)

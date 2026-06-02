#!/usr/bin/env python3
"""
THE RENDER WAVE — LTX Video img2vid UI Server
Flask backend com SSE progresso em tempo real via WebSocket ComfyUI.
"""

import argparse
import json
import os
import sys
import time
import subprocess
import requests
import threading
import queue
from pathlib import Path

from flask import Flask, request, jsonify, Response, send_from_directory

# ============ CONFIGURAÇÃO ============
COMFYUI_HOST = "http://192.168.144.1:8188"
COMFYUI_WS = "ws://192.168.144.1:8188/ws"
WORKFLOW_PATH = "/mnt/d/AI_Ecosystem/03_Workflows/Image2Video_LTXV.json"
OUTPUT_FOLDER = "/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output"
VIDEO_OUTPUT_DIR = os.path.join(OUTPUT_FOLDER, "video")
UPSCALE_DIR = os.path.join(OUTPUT_FOLDER, "video_upscaled")

DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 576
DEFAULT_STRENGTH = 0.10
DEFAULT_STEPS = 50
DEFAULT_CFG = 3.0
DEFAULT_FPS = 24
DEFAULT_SAMPLER = "euler"
POLL_INTERVAL = 2
MAX_WAIT = 1200  # 20 min

app = Flask(__name__)
jobs = {}  # job_id -> {"queue": Queue(), "done": False, "result": None}


def load_workflow():
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def upload_image_to_comfy(image_path):
    basename = os.path.basename(image_path)
    url = f"{COMFYUI_HOST}/upload/image"
    with open(image_path, "rb") as f:
        files = {"image": (basename, f, "image/png")}
        data = {"type": "input", "overwrite": "true"}
        resp = requests.post(url, files=files, data=data)
    resp.raise_for_status()
    result = resp.json()
    return result["name"]


def submit_prompt(workflow_dict):
    url = f"{COMFYUI_HOST}/prompt"
    payload = {"prompt": workflow_dict}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data.get("prompt_id")


def poll_for_video(prompt_id, job_queue):
    url = f"{COMFYUI_HOST}/history/{prompt_id}"
    start = time.time()
    while True:
        if time.time() - start > MAX_WAIT:
            return None
        resp = requests.get(url)
        if resp.status_code != 200:
            time.sleep(POLL_INTERVAL)
            continue
        data = resp.json()
        if not data or prompt_id not in data:
            time.sleep(POLL_INTERVAL)
            continue
        entry = data[prompt_id]
        outputs = entry.get("outputs", {})
        for node_id, node_out in outputs.items():
            if "gifs" in node_out:
                item = node_out["gifs"][0]
                return item["filename"], item.get("subfolder", ""), item.get("type", "output")
            if "videos" in node_out:
                item = node_out["videos"][0]
                return item["filename"], item.get("subfolder", ""), item.get("type", "output")
            if "images" in node_out:
                for item in node_out["images"]:
                    fname = item["filename"]
                    if fname.endswith(".mp4"):
                        return fname, item.get("subfolder", ""), item.get("type", "output")
        time.sleep(POLL_INTERVAL)


def resolve_video_path(filename, subfolder, out_type):
    if out_type == "output":
        base = OUTPUT_FOLDER
    elif out_type == "temp":
        base = os.path.join(os.path.dirname(OUTPUT_FOLDER), "temp")
    else:
        base = OUTPUT_FOLDER
    if subfolder:
        return os.path.join(base, subfolder, filename)
    return os.path.join(base, filename)


def upscale_video(input_mp4, output_mp4, target_w=2560, target_h=1440, crf=18):
    cmd = [
        "ffmpeg", "-y", "-i", input_mp4,
        "-vf", f"scale={target_w}:{target_h}:flags=lanczos",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        output_mp4
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def write_prompt_txt(video_path, positive, negative, params):
    txt_path = video_path.replace(".mp4", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Positive: {positive}\n")
        f.write(f"Negative: {negative}\n")
        f.write(f"Parameters: {params}\n")
    return txt_path


def comfyui_ws_listener(prompt_id, job_queue):
    """Conecta ao WebSocket do ComfyUI e envia progresso para a job_queue."""
    try:
        import websocket
    except ImportError:
        job_queue.put({"type": "error", "message": "websocket-client não instalado. Progresso não disponível em tempo real."})
        return

    def on_message(ws, message):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        msg_type = data.get("type")
        if msg_type == "status":
            status = data.get("data", {}).get("status", {})
            exec_info = status.get("exec_info", {})
            queue_remaining = exec_info.get("queue_remaining", 0)
            job_queue.put({"type": "queue", "remaining": queue_remaining})
        elif msg_type == "progress":
            progress = data.get("data", {})
            value = progress.get("value", 0)
            max_val = progress.get("max", 100)
            prompt_id_ws = progress.get("prompt_id")
            if prompt_id_ws == prompt_id:
                pct = int((value / max_val) * 100) if max_val else 0
                job_queue.put({"type": "progress", "percent": pct, "step": value, "total": max_val})
        elif msg_type == "execution_start":
            pid = data.get("data", {}).get("prompt_id")
            if pid == prompt_id:
                job_queue.put({"type": "status", "message": "A gerar vídeo..."})
        elif msg_type == "execution_cached":
            pid = data.get("data", {}).get("prompt_id")
            if pid == prompt_id:
                job_queue.put({"type": "status", "message": "Cache hit — a processar..."})
        elif msg_type == "executing":
            node = data.get("data", {}).get("node")
            job_queue.put({"type": "node", "node": node})

    def on_open(ws):
        job_queue.put({"type": "status", "message": "Ligado ao ComfyUI — a aguardar..."})

    def on_error(ws, error):
        job_queue.put({"type": "error", "message": str(error)})

    ws_app = websocket.WebSocketApp(
        COMFYUI_WS,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
    )
    ws_app.run_forever()


def run_pipeline(job_id, image_path, positive, negative, duration, strength, steps, cfg, fps, seed, do_upscale, upscale_w, upscale_h):
    """Pipeline completo numa thread separada."""
    q = jobs[job_id]["queue"]
    try:
        q.put({"type": "status", "message": "A carregar workflow..."})
        wf = load_workflow()

        length = int(duration * fps)
        q.put({"type": "status", "message": f"Config: {DEFAULT_WIDTH}x{DEFAULT_HEIGHT} | {duration}s ({length} frames) | strength={strength}"})

        # Extrair prompts do workflow se não fornecidos
        node_6_text = wf.get("6", {}).get("inputs", {}).get("text", "")
        node_7_text = wf.get("7", {}).get("inputs", {}).get("text", "")
        positive_prompt = positive if positive else node_6_text
        negative_prompt = negative if negative else node_7_text

        # Injetar parâmetros
        wf["77"]["inputs"]["width"] = DEFAULT_WIDTH
        wf["77"]["inputs"]["height"] = DEFAULT_HEIGHT
        wf["77"]["inputs"]["length"] = length
        wf["77"]["inputs"]["strength"] = strength
        wf["6"]["inputs"]["text"] = positive_prompt
        wf["7"]["inputs"]["text"] = negative_prompt
        wf["71"]["inputs"]["steps"] = steps
        if seed >= 0:
            wf["72"]["inputs"]["noise_seed"] = seed
        wf["72"]["inputs"]["cfg"] = cfg
        wf["80"]["inputs"]["fps"] = fps
        wf["69"]["inputs"]["frame_rate"] = fps

        q.put({"type": "status", "message": "A fazer upload da imagem..."})
        uploaded_name = upload_image_to_comfy(image_path)
        wf["78"]["inputs"]["image"] = uploaded_name

        q.put({"type": "status", "message": "A submeter para o ComfyUI..."})
        prompt_id = submit_prompt(wf)
        q.put({"type": "status", "message": f"Job submetido (ID: {prompt_id[:8]}...)"})

        # Iniciar WebSocket listener em thread separada
        ws_thread = threading.Thread(target=comfyui_ws_listener, args=(prompt_id, q), daemon=True)
        ws_thread.start()

        q.put({"type": "status", "message": "A aguardar geração..."})
        result = poll_for_video(prompt_id, q)
        if not result:
            q.put({"type": "error", "message": "Timeout ou falha na geração do vídeo."})
            jobs[job_id]["done"] = True
            return

        filename, subfolder, out_type = result
        video_path = resolve_video_path(filename, subfolder, out_type)

        if not os.path.exists(video_path):
            q.put({"type": "error", "message": f"Vídeo não encontrado em: {video_path}"})
            jobs[job_id]["done"] = True
            return

        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        q.put({"type": "status", "message": f"Vídeo gerado: {size_mb:.1f} MB"})

        # Guardar prompts
        params_str = f"width={DEFAULT_WIDTH}, height={DEFAULT_HEIGHT}, length={length}, strength={strength}, steps={steps}, seed={seed}, cfg={cfg}, fps={fps}"
        txt_path = write_prompt_txt(video_path, positive_prompt, negative_prompt, params_str)

        # Upscale
        if do_upscale:
            q.put({"type": "status", "message": "A fazer upscale com ffmpeg..."})
            os.makedirs(UPSCALE_DIR, exist_ok=True)
            base = os.path.splitext(filename)[0]
            upscale_name = f"{base}_upscaled.mp4"
            upscale_path = os.path.join(UPSCALE_DIR, upscale_name)
            ok = upscale_video(video_path, upscale_path, upscale_w, upscale_h)
            if ok:
                q.put({"type": "done", "video_path": video_path, "upscale_path": upscale_path, "txt_path": txt_path, "size_mb": size_mb})
            else:
                q.put({"type": "done", "video_path": video_path, "upscale_path": None, "txt_path": txt_path, "size_mb": size_mb, "warning": "Upscale falhou"})
        else:
            q.put({"type": "done", "video_path": video_path, "upscale_path": None, "txt_path": txt_path, "size_mb": size_mb})

    except Exception as e:
        q.put({"type": "error", "message": str(e)})
    finally:
        jobs[job_id]["done"] = True


@app.route("/")
def index():
    return send_from_directory(os.path.dirname(__file__), "index.html")


@app.route("/generate", methods=["POST"])
def generate():
    if "image" not in request.files:
        return jsonify({"error": "Imagem em falta"}), 400

    image = request.files["image"]
    positive = request.form.get("positive", "")
    negative = request.form.get("negative", "")
    duration = float(request.form.get("duration", 6))
    strength = float(request.form.get("strength", DEFAULT_STRENGTH))
    steps = int(request.form.get("steps", DEFAULT_STEPS))
    cfg = float(request.form.get("cfg", DEFAULT_CFG))
    fps = int(request.form.get("fps", DEFAULT_FPS))
    seed = int(request.form.get("seed", -1))
    do_upscale = request.form.get("upscale", "true").lower() == "true"
    upscale_w = int(request.form.get("upscale_w", 2560))
    upscale_h = int(request.form.get("upscale_h", 1440))

    # Guardar imagem temporariamente
    temp_dir = os.path.join(os.path.dirname(__file__), "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    image_path = os.path.join(temp_dir, image.filename)
    image.save(image_path)

    job_id = f"job_{int(time.time() * 1000)}"
    jobs[job_id] = {"queue": queue.Queue(), "done": False, "result": None}

    thread = threading.Thread(
        target=run_pipeline,
        args=(job_id, image_path, positive, negative, duration, strength, steps, cfg, fps, seed, do_upscale, upscale_w, upscale_h),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/progress/<job_id>")
def progress(job_id):
    def event_stream():
        if job_id not in jobs:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job não encontrado'})}\n\n"
            return
        q = jobs[job_id]["queue"]
        while True:
            try:
                msg = q.get(timeout=1200)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout a aguardar progresso'})}\n\n"
                break
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/video/<path:filename>")
def serve_video(filename):
    # Serve vídeos do output do ComfyUI
    return send_from_directory(OUTPUT_FOLDER, filename)


# ============ FILE BROWSER PARA WINDOWS FS ============
BROWSER_ROOTS = [
    "/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output",
    "/mnt/d/AI_Ecosystem/04_Data/Hermes/images/output",
]
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi"}


def _safe_path(requested):
    """Garante que o caminho pedido está dentro de uma root permitida."""
    rp = os.path.realpath(requested)
    for root in BROWSER_ROOTS:
        if rp.startswith(os.path.realpath(root)) or rp.startswith(os.path.realpath(root) + os.sep):
            return rp
    # Fallback: permitir /mnt/d/AI_Ecosystem/
    if rp.startswith("/mnt/d/AI_Ecosystem/"):
        return rp
    return None


@app.route("/api/browse")
def api_browse():
    path = request.args.get("path", BROWSER_ROOTS[0])
    safe = _safe_path(path)
    if safe is None:
        return jsonify({"error": "Caminho não permitido"}), 403
    if not os.path.isdir(safe):
        return jsonify({"error": "Não é diretório"}), 400

    dirs = []
    files = []
    try:
        for entry in os.scandir(safe):
            if entry.is_dir(follow_symlinks=False):
                dirs.append({"name": entry.name, "path": entry.path})
            else:
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in IMG_EXTS or ext in VIDEO_EXTS:
                    files.append({
                        "name": entry.name,
                        "path": entry.path,
                        "type": "image" if ext in IMG_EXTS else "video",
                        "size": entry.stat().st_size,
                    })
    except PermissionError:
        return jsonify({"error": "Sem permissões"}), 403

    dirs.sort(key=lambda x: x["name"].lower())
    files.sort(key=lambda x: x["name"].lower())
    parent = os.path.dirname(safe) if safe != os.path.dirname(safe) else None

    return jsonify({
        "current": safe,
        "parent": parent,
        "dirs": dirs,
        "files": files,
    })


@app.route("/api/load-image")
def api_load_image():
    path = request.args.get("path")
    if not path:
        return jsonify({"error": "Caminho em falta"}), 400
    safe = _safe_path(path)
    if safe is None or not os.path.isfile(safe):
        return jsonify({"error": "Ficheiro não encontrado"}), 404
    ext = os.path.splitext(safe)[1].lower()
    if ext not in IMG_EXTS:
        return jsonify({"error": "Não é imagem"}), 400
    return send_from_directory(os.path.dirname(safe), os.path.basename(safe))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    # Criar pastas necessárias
    os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
    os.makedirs(UPSCALE_DIR, exist_ok=True)

    print(f"[SERVER] THE RENDER WAVE UI — http://{args.host}:{args.port}")
    print(f"[SERVER] ComfyUI: {COMFYUI_HOST}")
    print(f"[SERVER] Press Ctrl+C para parar")
    app.run(host=args.host, port=args.port, threaded=True)

#!/usr/bin/env python3
"""
Servidor web para o RENDER WAVE Video Generator.
Serve a pagina HTML, aceita pedidos de geracao, e mostra os videos gerados.
"""

import json
import os
import subprocess
import sys
import re

from flask import Flask, send_from_directory, request, jsonify

# ========= CONFIGURACAO =========
APP_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(APP_DIR, "video_generator.html")
SCRIPT_PATH = os.path.join(APP_DIR, "generate_video.py")
IMAGES_DIR = "/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output"
METADATA_DIR = "/mnt/d/AI_Ecosystem/04_Data/Hermes/videos/metadata"

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(APP_DIR, "video_generator.html")


@app.route("/video/<path:filename>")
def serve_video(filename):
    safe = os.path.basename(filename)
    # Procurar na subpasta video/ ou raiz
    for subdir in ["video", ""]:
        path = os.path.join(IMAGES_DIR, subdir, safe)
        if os.path.exists(path):
            return send_from_directory(os.path.join(IMAGES_DIR, subdir), safe)
    return "Ficheiro nao encontrado", 404


@app.route("/images")
def list_images():
    """Lista imagens disponiveis no output do ComfyUI para usar como input."""
    import glob
    patterns = [
        os.path.join(IMAGES_DIR, "*.png"),
        os.path.join(IMAGES_DIR, "*.jpg"),
        os.path.join(IMAGES_DIR, "*.jpeg"),
        os.path.join(IMAGES_DIR, "*.webp"),
    ]
    images = []
    for pattern in patterns:
        for path in sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True):
            images.append({
                "filename": os.path.basename(path),
                "path": path,
                "mtime": os.path.getmtime(path)
            })
    return jsonify(images[:50])


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json() or {}

    image_path = data.get("image", "").strip()
    prompt = data.get("prompt", "").strip()

    if not image_path:
        return jsonify({"status": "error", "message": "Caminho da imagem vazio"}), 400
    if not prompt:
        return jsonify({"status": "error", "message": "Prompt vazio"}), 400

    # Construir argumentos
    venv_python = os.path.join(APP_DIR, "..", "Image_creation", "venv", "bin", "python3")
    # Fallback se venv nao existir em Image_creation
    if not os.path.exists(venv_python):
        venv_python = os.path.join(APP_DIR, "venv", "bin", "python3")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    args = [venv_python, "-u", SCRIPT_PATH,
            "--image", image_path,
            "--prompt", prompt,
            "--negative", str(data.get("negative", "low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, artifacts, fused fingers, bad anatomy, weird hand, ugly")),
            "--strength", str(data.get("strength", 0.15)),
            "--length", str(data.get("length", 153)),
            "--seed", str(data.get("seed", -1)),
            "--steps", str(data.get("steps", 50)),
            "--cfg", str(data.get("cfg", 3.0))]

    # Se o user passou video_prompt manual, usar --video-prompt
    if data.get("video_prompt"):
        args.extend(["--video-prompt", data.get("video_prompt")])
    elif data.get("no_translate"):
        args.append("--no-translate")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=900
        )

        output_text = result.stdout.strip()

        # Extrair ultimo JSON da saida
        json_str = None
        for i in range(len(output_text) - 1, -1, -1):
            if output_text[i] == '}':
                depth = 0
                for j in range(i, -1, -1):
                    c = output_text[j]
                    if c == '}':
                        depth += 1
                    elif c == '{':
                        depth -= 1
                        if depth == 0:
                            json_str = output_text[j:i+1]
                            break
                if json_str:
                    break

        if not json_str:
            return jsonify({"status": "error", "message": "Nenhum JSON encontrado na resposta", "stdout": output_text[-500:]}), 500

        output = json.loads(json_str)
        return jsonify(output), 200

    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Timeout - o ComfyUI demorou demasiado"}), 504
    except json.JSONDecodeError as e:
        return jsonify({"status": "error", "message": "Resposta invalida do script", "raw": output_text[-500:]}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("=" * 50)
    print("RENDER WAVE - Video Generator Server")
    print("=" * 50)
    print(f"Pasta de videos: {os.path.join(IMAGES_DIR, 'video')}")
    print(f"Metadados: {METADATA_DIR}")
    print("")
    print("Abre no navegador: http://127.0.0.1:5001")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=False)

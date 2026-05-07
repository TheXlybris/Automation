#!/usr/bin/env python3
"""
Servidor web para o RENDER WAVE Image Generator.
Serve a pagina HTML, aceita pedidos de geracao, e mostra as imagens geradas.
"""

import json
import os
import subprocess
import sys
import re

from flask import Flask, send_from_directory, request, jsonify

# ========= CONFIGURACAO =========
APP_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(APP_DIR, "image_generator.html")
SCRIPT_PATH = os.path.join(APP_DIR, "generate_image.py")
IMAGES_DIR = "/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output"

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(APP_DIR, "image_generator.html")


@app.route("/image/<path:filename>")
def serve_image(filename):
    # Seguranca: nao permite sair do directorio
    safe = os.path.basename(filename)
    return send_from_directory(IMAGES_DIR, safe)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json() or {}

    # Validacao minima
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"status": "error", "message": "Prompt vazio"}), 400

    # Construir argumentos para o script (usando o Python do venv)
    venv_python = os.path.join(APP_DIR, "venv", "bin", "python3")
    args = [venv_python, "-u", SCRIPT_PATH,
            "--prompt", prompt,
            "--negative", str(data.get("negative", "text, watermark, ugly, blurry, low quality")),
            "--width", str(data.get("width", 1024)),
            "--height", str(data.get("height", 576)),
            "--batch", str(data.get("batch", 1)),
            "--seed", str(data.get("seed", -1)),
            "--steps", str(data.get("steps", 70)),
            "--cfg", str(data.get("cfg", 8.0))]

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=360
        )

        # Procurar o JSON na saida (pode ser indentado com multiplas linhas)
        output_text = result.stdout.strip()
        
        # Estrategia: procurar o ultimo bloco JSON valido usando contador de chavetas
        json_str = None
        # Procurar de tras para frente o inicio do JSON mais profundo
        for i in range(len(output_text) - 1, -1, -1):
            if output_text[i] == '}':
                # Tentar encontrar o '{' correspondente
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
            return jsonify({"status": "error", "message": "Nenhum JSON encontrado na resposta", "stdout": output_text[:500]}), 500

        output = json.loads(json_str)
        return jsonify(output), 200

    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Timeout - o ComfyUI demorou demasiado"}), 504
    except json.JSONDecodeError as e:
        return jsonify({"status": "error", "message": "Resposta invalida do script", "raw": json_line if 'json_line' in dir() else str(e)}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("=" * 50)
    print("RENDER WAVE - Image Generator Server")
    print("=" * 50)
    print(f"Pasta de imagens: {IMAGES_DIR}")
    print(f"Workflow: /mnt/c/Users/Fil_B/Downloads/Text2Image_API.json")
    print("")
    print("Abre no navegador: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)

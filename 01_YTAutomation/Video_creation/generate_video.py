#!/usr/bin/env python3
"""
Gera videos via API do ComfyUI para o projeto THE RENDER WAVE.
Workflow: Image2Video_LTXV.json (LTX Video 2B img2vid)
Traduz automaticamente prompts de imagem -> video.
Guarda metadados (prompts + parametros) em ficheiro TXT.
"""

import json
import os
import time
import argparse
import requests
import re
import glob

# ========= CONFIGURACAO =========
COMFYUI_HOST = "http://192.168.144.1:8188"
WORKFLOW_PATH = "/mnt/d/AI_Ecosystem/03_Workflows/API/Image2Video_LTXV.json"
IMAGES_DIR = "/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output"
METADATA_DIR = "/mnt/d/AI_Ecosystem/04_Data/Hermes/videos/metadata"

# ========= TRADUCAO PROMPT =========

# Termos de fotografia estatica a remover
STATIC_PHOTO_TERMS = [
    r"\d+mm lens",
    r"medium shot",
    r"close[\s-]?up",
    r"wide shot",
    r"full shot",
    r"extreme close[\s-]?up",
    r"shallow depth of field",
    r"depth of field",
    r"sharp focus on",
    r"focus on",
    r"National Geographic",
    r"nature photography",
    r"photography",
    r"natural colors",
    r"detailed textures",
    r"textures of",
    r"raw photo",
    r"8k",
]

# Frases de movimento/loop a adicionar no final
MOTION_SUFFIX = (
    ", consistent scene, stable composition, camera slowly pans to the right, "
    "subtle ambient motion only, fixed viewpoint, seamless cyclic motion, "
    "smooth continuous movement, infinite loop feel, ambient perpetual motion, "
    "natural repeating rhythm, hypnotic gentle flow, meditative calm motion"
)


def translate_image_to_video_prompt(image_prompt: str) -> str:
    """Traduz prompt de imagem estatica para prompt de video animado."""
    video_prompt = image_prompt

    # 1. Remover termos de fotografia estatica
    for pattern in STATIC_PHOTO_TERMS:
        video_prompt = re.sub(pattern, "", video_prompt, flags=re.IGNORECASE)

    # 2. Limpar duplicacoes de virgulas e espacos
    video_prompt = re.sub(r",\s*,", ",", video_prompt)
    video_prompt = re.sub(r"\s+", " ", video_prompt)
    video_prompt = video_prompt.strip(", ")

    # 3. Adicionar frases de movimento e loop no final
    video_prompt = video_prompt + MOTION_SUFFIX

    return video_prompt


def upload_image_to_comfyui(image_path: str, host: str) -> str:
    """Upload image para ComfyUI input/ e retorna o nome usado no workflow."""
    url = f"{host}/api/upload/image"
    filename = os.path.basename(image_path)

    with open(image_path, "rb") as f:
        files = {"image": (filename, f, "image/png")}
        data = {"type": "input", "overwrite": "true"}
        resp = requests.post(url, files=files, data=data, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(f"Upload falhou: {resp.status_code} {resp.text}")

    result = resp.json()
    # ComfyUI retorna: {"name": "filename.png", "subfolder": "", "type": "input"}
    return result.get("name", filename)


def build_payload(wflow_json, image_name, prompt, negative, strength, length, seed, steps, cfg):
    """Injeta os parametros dinamicos no workflow JSON."""
    w = json.loads(json.dumps(wflow_json))  # deep copy

    # Prompt positivo e negativo (nodes 6 e 7)
    w["6"]["inputs"]["text"] = prompt
    w["7"]["inputs"]["text"] = negative

    # Imagem de input (node 78)
    w["78"]["inputs"]["image"] = image_name

    # Parametros LTXV (node 77)
    w["77"]["inputs"]["strength"] = strength
    w["77"]["inputs"]["length"] = length

    # Parametros do sampler (node 72)
    w["72"]["inputs"]["noise_seed"] = seed
    w["72"]["inputs"]["cfg"] = cfg

    # Scheduler steps (node 71)
    w["71"]["inputs"]["steps"] = steps

    # Prefixo do ficheiro output (node 81)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    w["81"]["inputs"]["filename_prefix"] = f"video/RENDERWAVE_{timestamp}"

    return w


def submit_and_wait(host, payload, timeout=600):
    """Envia o workflow para /api/prompt e espera pelo resultado."""
    url = f"{host}/prompt"
    resp = requests.post(url, json={"prompt": payload}, timeout=30)
    if resp.status_code != 200:
        return {"status": "error", "message": resp.text}

    data = resp.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        return {"status": "error", "message": "Sem prompt_id na resposta"}

    print(f"[OK] Prompt enviado. ID: {prompt_id}")

    start = time.time()
    while time.time() - start < timeout:
        hist_resp = requests.get(f"{host}/history/{prompt_id}", timeout=10)
        if hist_resp.status_code != 200:
            time.sleep(1)
            continue

        hist = hist_resp.json()
        entry = hist.get(prompt_id)
        if not entry:
            time.sleep(1)
            continue

        outputs = entry.get("outputs", {})

        # Procurar videos em outputs
        videos = []
        for node_id, node_out in outputs.items():
            vids = node_out.get("videos", [])
            for v in vids:
                if v.get("type") == "output":
                    videos.append({
                        "node_id": node_id,
                        "filename": v["filename"],
                        "subfolder": v.get("subfolder", ""),
                    })

            # Fallback: procurar images (alguns nodes de video retornam como images)
            imgs = node_out.get("images", [])
            for img in imgs:
                fn = img.get("filename", "")
                if img.get("type") == "output" and fn.endswith((".mp4", ".webm", ".mov", ".avi")):
                    videos.append({
                        "node_id": node_id,
                        "filename": fn,
                        "subfolder": img.get("subfolder", ""),
                    })

        if videos:
            return {"status": "success", "prompt_id": prompt_id, "videos": videos}

        status = entry.get("status", {}).get("status_str", "running")
        if status == "error":
            return {"status": "error", "message": "Erro na execucao do workflow."}
        if status == "success" and not videos:
            # Workflow completou mas sem videos retornados - retornar vazio para fallback no disco
            return {"status": "success", "prompt_id": prompt_id, "videos": []}

        time.sleep(1)

    return {"status": "error", "message": f"Timeout apos {timeout}s. Verifique na fila do ComfyUI."}


def find_latest_video_on_disk():
    """Procura ficheiros de video mais recentes no output do ComfyUI."""
    patterns = [
        os.path.join(IMAGES_DIR, "video", "*.mp4"),
        os.path.join(IMAGES_DIR, "video", "*.webm"),
        os.path.join(IMAGES_DIR, "*.mp4"),
        os.path.join(IMAGES_DIR, "*.webm"),
    ]
    all_videos = []
    for pattern in patterns:
        all_videos.extend(glob.glob(pattern))

    if not all_videos:
        return None

    # Mais recente
    latest = max(all_videos, key=os.path.getmtime)
    return latest


def save_metadata(video_filename, image_prompt, video_prompt, negative,
                  output_dir, strength, length, seed, steps, cfg):
    """Guarda metadados da geracao num ficheiro TXT."""
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(video_filename)[0]
    meta_path = os.path.join(output_dir, f"{base_name}_metadata.txt")

    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("=== THE RENDER WAVE - Video Generation Metadata ===\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Video File: {video_filename}\n\n")
        f.write(f"--- Image Prompt (original) ---\n{image_prompt}\n\n")
        f.write(f"--- Video Prompt (translated) ---\n{video_prompt}\n\n")
        f.write(f"--- Negative Prompt ---\n{negative}\n\n")
        f.write(f"--- Parameters ---\n")
        f.write(f"Strength: {strength}\n")
        f.write(f"Length (frames): {length}\n")
        f.write(f"Seed: {seed}\n")
        f.write(f"Steps: {steps}\n")
        f.write(f"CFG: {cfg}\n")

    return meta_path


def main():
    parser = argparse.ArgumentParser(description="GERA VIDEO - THE RENDER WAVE")
    parser.add_argument("--image", required=True, help="Caminho para a imagem de input")
    parser.add_argument("--prompt", required=True, help="Prompt positivo (formato imagem)")
    parser.add_argument("--negative", default="low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, artifacts, fused fingers, bad anatomy, weird hand, ugly", help="Prompt negativo")
    parser.add_argument("--strength", type=float, default=0.15, help="Strength img2vid (0.0-1.0, padrao: 0.15)")
    parser.add_argument("--length", type=int, default=153, help="Numero de frames (padrao: 153)")
    parser.add_argument("--seed", type=int, default=-1, help="Seed (-1 = aleatorio)")
    parser.add_argument("--steps", type=int, default=50, help="Steps (padrao: 50)")
    parser.add_argument("--cfg", type=float, default=3.0, help="CFG scale (padrao: 3)")
    parser.add_argument("--no-translate", action="store_true", help="Usar prompt de imagem diretamente (sem traducao)")
    parser.add_argument("--video-prompt", help="Prompt de video manual (ignora traducao e prompt de imagem)")
    args = parser.parse_args()

    # Validar workflow
    if not os.path.exists(WORKFLOW_PATH):
        print(f"[ERRO] Workflow nao encontrado: {WORKFLOW_PATH}")
        return

    with open(WORKFLOW_PATH, "r") as f:
        wflow = json.load(f)

    # Validar imagem
    if not os.path.exists(args.image):
        print(f"[ERRO] Imagem nao encontrada: {args.image}")
        return

    # Determinar prompt de video
    image_prompt = args.prompt
    if args.video_prompt:
        video_prompt = args.video_prompt
        print("[INFO] Usando prompt de video manual")
    elif args.no_translate:
        video_prompt = image_prompt
        print("[INFO] Usando prompt de imagem diretamente (sem traducao)")
    else:
        video_prompt = translate_image_to_video_prompt(image_prompt)
        print("[INFO] Prompt traduzido de imagem -> video")

    print(f"[INFO] Prompt Imagem: {image_prompt[:100]}...")
    print(f"[INFO] Prompt Video:  {video_prompt[:100]}...")

    seed = args.seed if args.seed != -1 else int(time.time() * 1000) % (2**32)

    print(f"[INFO] Imagem: {args.image}")
    print(f"[INFO] Strength: {args.strength} | Length: {args.length} | Seed: {seed}")

    # 1. Upload da imagem para ComfyUI
    print("[INFO] A fazer upload da imagem para o ComfyUI...")
    try:
        image_name = upload_image_to_comfyui(args.image, COMFYUI_HOST)
        print(f"[OK] Imagem uploaded: {image_name}")
    except Exception as e:
        print(f"[ERRO] Upload falhou: {e}")
        return

    # 2. Construir payload
    payload = build_payload(wflow, image_name, video_prompt, args.negative,
                            args.strength, args.length, seed, args.steps, args.cfg)

    # 3. Enviar e esperar
    result = submit_and_wait(COMFYUI_HOST, payload)

    # 4. Guardar metadados e mostrar resultado
    if result["status"] == "success":
        videos = result.get("videos", [])

        # Se nao retornou videos no historico, procurar no disco
        if not videos:
            print("[INFO] A procurar ficheiro de video no output...")
            latest = find_latest_video_on_disk()
            if latest:
                filename = os.path.basename(latest)
                subfolder = "video" if "/video/" in latest.replace("\\", "/") else ""
                videos = [{"filename": filename, "subfolder": subfolder, "node_id": "81"}]
                print(f"[OK] Video encontrado: {filename}")
            else:
                print("[AVISO] Nenhum ficheiro de video encontrado no output")

        # Guardar metadados
        for v in videos:
            meta_path = save_metadata(
                v["filename"], image_prompt, video_prompt, args.negative,
                METADATA_DIR, args.strength, args.length, seed, args.steps, args.cfg
            )
            print(f"[OK] Metadados guardados: {meta_path}")

        result["videos"] = videos
    else:
        print(f"[ERRO] {result.get('message', 'Erro desconhecido')}")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

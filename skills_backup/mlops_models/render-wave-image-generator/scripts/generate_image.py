#!/usr/bin/env python3
"""
Gera imagens via API do ComfyUI para o projeto THE RENDER WAVE.
Workflow: Text2Image_API.json (exportado do ComfyUI)
"""

import json
import os
import time
import argparse
import requests

# ========= CONFIGURACAO =========
# Host Windows visto pelo WSL (descobrir via: ip route | grep default)
COMFYUI_HOST = "http://192.168.144.1:8188"
WORKFLOW_PATH = "/mnt/c/Users/Fil_B/Downloads/Text2Image_API.json"

# Node IDs confirmados no workflow JSON:
# 3 = KSampler      (seed, steps, cfg, sampler_name, scheduler, denoise)
# 4 = CheckpointLoaderSimple (ckpt_name)
# 5 = EmptyLatentImage (width, height, batch_size)
# 6 = CLIPTextEncode POSITIVO (text, clip)
# 7 = CLIPTextEncode NEGATIVO (text, clip)
# 8 = VAEDecode
# 9 = SaveImage (filename_prefix, images)


def build_payload(wflow_json, prompt, negative, width, height, batch_size, seed, steps, cfg):
    """Injeta os parametros dinamicos no workflow JSON (deep copy)."""
    w = json.loads(json.dumps(wflow_json))

    # Prompts
    w["6"]["inputs"]["text"] = prompt
    w["7"]["inputs"]["text"] = negative
    # Resolucao e batch
    w["5"]["inputs"]["width"] = width
    w["5"]["inputs"]["height"] = height
    w["5"]["inputs"]["batch_size"] = batch_size
    # Sampler settings
    w["3"]["inputs"]["seed"] = seed
    w["3"]["inputs"]["steps"] = steps
    w["3"]["inputs"]["cfg"] = cfg
    # Nome do ficheiro output
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    w["9"]["inputs"]["filename_prefix"] = f"RENDERWAVE_{timestamp}"

    return w


def submit_and_wait(host, payload, timeout=300):
    """Envia o workflow para /api/prompt e faz polling em /history/{prompt_id}."""
    # 1. Enviar prompt
    url = f"{host}/prompt"
    resp = requests.post(url, json={"prompt": payload}, timeout=30)
    if resp.status_code != 200:
        return {"status": "error", "message": resp.text}

    data = resp.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        return {"status": "error", "message": "Sem prompt_id na resposta"}

    print(f"[OK] Prompt enviado. ID: {prompt_id}")

    # 2. Poll /history/{prompt_id} ate completar
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
        images = []
        # outputs = { "9": { "images": [ { "filename": "...", "subfolder": "", "type": "output" } ] } }
        for node_id, node_out in outputs.items():
            imgs = node_out.get("images", [])
            for img in imgs:
                if img.get("type") == "output":
                    images.append({
                        "node_id": node_id,
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                    })

        if images:
            return {"status": "success", "prompt_id": prompt_id, "images": images}

        # Se chegou aqui sem imagens, verifica se houve erro
        status = entry.get("status", {}).get("status_str", "running")
        if status == "error":
            return {"status": "error", "message": "Erro na execucao do workflow."}
        if status == "success" and not images:
            return {"status": "error", "message": "Workflow completou mas nao retornou imagens."}

        time.sleep(1)

    return {"status": "error", "message": f"Timeout apos {timeout}s."}


def main():
    parser = argparse.ArgumentParser(description="GERA IMAGEM - THE RENDER WAVE")
    parser.add_argument("--prompt", required=True, help="Descricao positiva da imagem")
    parser.add_argument("--negative", default="text, watermark, ugly, blurry, low quality", help="Descricao negativa")
    parser.add_argument("--width", type=int, default=1024, help="Largura (padrao: 1024)")
    parser.add_argument("--height", type=int, default=576, help="Altura (padrao: 576)")
    parser.add_argument("--batch", type=int, default=1, help="Numero de imagens (1-8)")
    parser.add_argument("--seed", type=int, default=-1, help="Seed (-1 = aleatorio)")
    parser.add_argument("--steps", type=int, default=70, help="Steps (padrao: 70)")
    parser.add_argument("--cfg", type=float, default=8.0, help="CFG scale (padrao: 8)")
    args = parser.parse_args()

    if not os.path.exists(WORKFLOW_PATH):
        print(f"[ERRO] Workflow nao encontrado: {WORKFLOW_PATH}")
        return

    with open(WORKFLOW_PATH, "r") as f:
        wflow = json.load(f)

    seed = args.seed if args.seed != -1 else int(time.time() * 1000) % (2**32)

    print(f"[INFO] Prompt: {args.prompt}")
    print(f"[INFO] Resolucao: {args.width}x{args.height} | Batch: {args.batch} | Seed: {seed}")

    payload = build_payload(wflow, args.prompt, args.negative, args.width, args.height, args.batch, seed, args.steps, args.cfg)
    result = submit_and_wait(COMFYUI_HOST, payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Gera imagens via API do ComfyUI — template canónico para THE RENDER WAVE.
Copiar para o projecto e modificar WORKFLOW_PATH, COMFYUI_HOST conforme necessário.
"""

import json
import os
import time
import argparse
import sys
import requests

# ============ CONFIGURACAO (modificar conforme o ambiente) ============
# IP do host Windows visto pelo WSL. Descobrir via: ip route | grep default
COMFYUI_HOST = "http://192.168.144.1:8188"
WORKFLOW_PATH = "/mnt/c/Users/Fil_B/Downloads/Text2Image_API.json"
# ================================================================

# Node IDs do workflow Text2Image_API.json (validar antes de usar):
# 3 = KSampler           (seed, steps, cfg, sampler_name, scheduler, denoise)
# 4 = CheckpointLoaderSimple  (ckpt_name)
# 5 = EmptyLatentImage   (width, height, batch_size)
# 6 = CLIPTextEncode     (text — prompt POSITIVO)
# 7 = CLIPTextEncode     (text — prompt NEGATIVO)
# 8 = VAEDecode         (sem injecao)
# 9 = SaveImage          (filename_prefix — OBRIGATORIO)


def validate_workflow(wf):
    """Verifica se o workflow tem os node IDs esperados. Levanta AssertionError em falha."""
    expected = {
        "3": "KSampler",
        "4": "CheckpointLoaderSimple",
        "5": "EmptyLatentImage",
        "6": "CLIPTextEncode",
        "7": "CLIPTextEncode",
        "8": "VAEDecode",
        "9": "SaveImage",
    }
    missing = []
    wrong_type = []
    for nid, expected_class in expected.items():
        if nid not in wf:
            missing.append(nid)
        elif wf[nid].get("class_type") != expected_class:
            wrong_type.append(f"{nid}: esperado {expected_class}, encontrado {wf[nid].get('class_type')}")
    if missing or wrong_type:
        msg = "Validacao do workflow falhou:\n"
        if missing:
            msg += f"  Node IDs em falta: {missing}\n"
        if wrong_type:
            msg += f"  Tipos errados: {wrong_type}\n"
        msg += "Possive causas:\n"
        msg += "  - Workflow nao esta em formato API (exportar via ComfyUI: Save API)\n"
        msg += "  - Workflow foi modificado e node IDs mudaram\n"
        msg += f"  - Verificar: {WORKFLOW_PATH}"
        raise AssertionError(msg)


def build_payload(wflow_json, prompt, negative, width, height, batch_size, seed, steps, cfg):
    """Injeta parametros no workflow via deep copy. Nunca muta o original."""
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
    # filename_prefix OBRIGATORIO no SaveImage
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    w["9"]["inputs"]["filename_prefix"] = f"RENDERWAVE_{timestamp}"

    return w


def submit_and_wait(host, payload, timeout=300):
    """Envia para /api/prompt e faz polling em /history/{prompt_id}."""
    # 1. Enviar prompt
    url = f"{host}/prompt"
    try:
        resp = requests.post(url, json={"prompt": payload}, timeout=30)
    except requests.exceptions.ConnectionError as e:
        print(f"[ERRO] Nao foi possivel ligar a {host}")
        print(f"  Certifique-se de que o ComfyUI esta a rodar com --listen 0.0.0.0")
        print(f"  Erro: {e}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"[ERRO] API retornou {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)

    data = resp.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        print(f"[ERRO] Sem prompt_id na resposta. Retorno: {data}")
        sys.exit(1)

    print(f"[OK] Prompt enviado. ID: {prompt_id}")

    # 2. Polling de /history/{prompt_id}
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
        # CRITICAL: outputs e um DICT {node_id: node_output}, nao uma lista
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

        # Verifica se job falhou
        status = entry.get("status", {}).get("status_str", "running")
        if status == "error":
            return {"status": "error", "message": "Erro na execucao do workflow. Ver logs do ComfyUI."}
        if status == "success" and not images:
            return {"status": "error", "message": "Workflow completou mas nao retornou imagens."}

        print("[...] Aguardando execucao...")
        time.sleep(1)

    return {"status": "error", "message": f"Timeout apos {timeout}s. Verifique se o ComfyUI esta processando."}


def main():
    parser = argparse.ArgumentParser(
        description="GERA IMAGEM - THE RENDER WAVE v3",
        epilog="Exemplo: python generate_image.py --prompt 'Paisagem serena' --width 1024 --height 576"
    )
    parser.add_argument("--prompt", required=True, help="Descricao positiva da cena (obrigatorio)")
    parser.add_argument("--negative", default="text, watermark, ugly, blurry, low quality", help="Prompt negativo")
    parser.add_argument("--width", type=int, default=1024, help="Largura em px (padrao: 1024)")
    parser.add_argument("--height", type=int, default=576, help="Altura em px (padrao: 576)")
    parser.add_argument("--batch", type=int, default=1, help="Numero de imagens (1-8)")
    parser.add_argument("--seed", type=int, default=-1, help="Seed (-1 = aleatorio)")
    parser.add_argument("--steps", type=int, default=70, help="Steps do sampler (padrao: 70)")
    parser.add_argument("--cfg", type=float, default=8.0, help="CFG scale (padrao: 8)")
    parser.add_argument("--host", default=COMFYUI_HOST, help=f"URL do ComfyUI (padrao: {COMFYUI_HOST})")
    parser.add_argument("--workflow", default=WORKFLOW_PATH, help=f"Path do workflow JSON (padrao: {WORKFLOW_PATH})")
    args = parser.parse_args()

    # Validar ficheiro workflow
    if not os.path.exists(args.workflow):
        print(f"[ERRO] Workflow nao encontrado: {args.workflow}")
        sys.exit(1)

    with open(args.workflow, "r", encoding="utf-8") as f:
        wflow = json.load(f)

    # Validar estrutura do workflow (opcional mas recomendado)
    try:
        validate_workflow(wflow)
        print("[OK] Workflow validado com sucesso.")
    except AssertionError as e:
        print(str(e))
        sys.exit(1)

    # Converter seed -1 para aleatorio
    if args.seed == -1:
        seed = int(time.time() * 1000) % (2**32)
    else:
        seed = args.seed

    print(f"[INFO] Prompt:  {args.prompt}")
    print(f"[INFO] Negative: {args.negative}")
    print(f"[INFO] Resolucao: {args.width}x{args.height} | Batch: {args.batch} | Seed: {seed}")

    payload = build_payload(wflow, args.prompt, args.negative, args.width, args.height, args.batch, seed, args.steps, args.cfg)
    result = submit_and_wait(args.host, payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit code = 0 em sucesso, 1 em erro
    sys.exit(0 if result.get("status") == "success" else 1)


if __name__ == "__main__":
    main()

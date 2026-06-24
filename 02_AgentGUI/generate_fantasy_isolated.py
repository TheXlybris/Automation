#!/usr/bin/env python3
"""
generate_fantasy_isolated.py - Geracao de imagem fantasy animation isolada
para storyboard. Sem IP-Adapter. Workflow base: Text2Image_IPAdapter_Coherent_API.json
Resolucao: 2400x1350. RTX 4060 Ti 16GB.
"""
import json
import time
import urllib.request
import urllib.error
import os
import random

COMFYUI_URL = "http://192.168.144.1:8188"
WORKFLOW_PATH = "/mnt/d/AI_Ecosystem/03_Workflows/API/Text2Image_IPAdapter_Coherent_API.json"
OUTPUT_SYMLINK = "/mnt/d/AI_Ecosystem/04_Data/Hermes/images/output"

PROMPT_POSITIVE = (
    "masterpiece, best quality, highly detailed, fantasy animation landscape, "
    "ethereal floating crystal islands above a vast ocean at twilight, "
    "glowing bioluminescent coral growing on levitating rock platforms, "
    "luminescent jellyfish swimming through misty air, "
    "waterfalls flowing upward into a sky filled with aurora borealis in shades of pink and teal, "
    "ethereal atmosphere, soft volumetric magical light, concept art style, "
    "cartoon shading, whimsical, 8k, trending on ArtStation"
)

PROMPT_NEGATIVE = (
    "(worst quality, low quality, bad quality:1.4), "
    "(blurry, blurred, out of focus:1.2), ugly, deformed, disfigured, "
    "extra limbs, bad anatomy, watermark, signature, text, jpeg artifacts, "
    "oversaturated, overexposed, photorealistic, realistic, raw photo, "
    "3d render, plastic, artificial, human, person, face, portrait"
)


def load_workflow(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_isolated_workflow(wf: dict) -> dict:
    """Cria versao do workflow SEM IP-Adapter (imagem isolada).
    O KSampler usa o modelo diretamente do CheckpointLoaderSimple (node 4)
    em vez do IPAdapterAdvanced (node 13).
    """
    wf = json.loads(json.dumps(wf))  # deep copy

    # Node 14 (KSampler): ligar model ao node 4 (CheckpointLoaderSimple) em vez de 13
    wf["14"]["inputs"]["model"] = ["4", 0]

    # Node 6: prompt positivo
    wf["6"]["inputs"]["text"] = PROMPT_POSITIVE

    # Node 7: prompt negativo
    wf["7"]["inputs"]["text"] = PROMPT_NEGATIVE

    # Node 1: resolucao ja esta 2400x1350 no workflow original
    # Node 14: parametros de sampler
    wf["14"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
    wf["14"]["inputs"]["steps"] = 70
    wf["14"]["inputs"]["cfg"] = 8.0
    wf["14"]["inputs"]["sampler_name"] = "euler"
    wf["14"]["inputs"]["scheduler"] = "normal"
    wf["14"]["inputs"]["denoise"] = 1.0

    # Node 9: prefixo do ficheiro
    wf["9"]["inputs"]["filename_prefix"] = "STORYBOARD_fantasy"

    return wf


def queue_prompt(prompt: dict) -> str:
    data = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"Resposta sem prompt_id: {result}")
        return prompt_id


def poll_history(prompt_id: str, timeout: int = 300) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(
                f"{COMFYUI_URL}/history/{prompt_id}",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                history = json.loads(resp.read().decode("utf-8"))
                if prompt_id in history:
                    return history[prompt_id]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                pass  # ainda nao esta pronto
            else:
                raise
        time.sleep(2)
    raise TimeoutError(f"Timeout apos {timeout}s a aguardar prompt_id={prompt_id}")


def extract_images(outputs: dict) -> list:
    images = []
    for node_id, node_out in outputs.items():
        for img in node_out.get("images", []):
            if img.get("type") == "output":
                images.append({
                    "node_id": node_id,
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                })
    return images


def main():
    print("=" * 60)
    print("THE RENDER WAVE - Geracao Imagem Isolada (Storyboard)")
    print("=" * 60)
    print(f"ComfyUI URL: {COMFYUI_URL}")
    print(f"Workflow: {WORKFLOW_PATH}")
    print(f"Resolucao: 2400x1350")
    print(f"IP-Adapter: DESLIGADO (imagem isolada)")
    print("-" * 60)

    if not os.path.exists(WORKFLOW_PATH):
        print(f"[ERRO] Workflow nao encontrado: {WORKFLOW_PATH}")
        return 1

    print("[1/5] A carregar workflow base...")
    wf = load_workflow(WORKFLOW_PATH)

    print("[2/5] A construir workflow isolado (sem IP-Adapter)...")
    wf_isolated = build_isolated_workflow(wf)

    # Guardar workflow usado para debug
    debug_path = "/mnt/d/AI_Ecosystem/04_Data/Hermes/images/output/_last_workflow.json"
    os.makedirs(os.path.dirname(debug_path), exist_ok=True)
    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(wf_isolated, f, indent=2)
    print(f"       Workflow debug: {debug_path}")

    print("[3/5] A enviar para ComfyUI...")
    try:
        prompt_id = queue_prompt(wf_isolated)
    except Exception as e:
        print(f"[ERRO] Falha ao enviar: {e}")
        return 1
    print(f"       prompt_id: {prompt_id}")

    print("[4/5] A aguardar conclusao (timeout 300s)...")
    try:
        history = poll_history(prompt_id)
    except TimeoutError as e:
        print(f"[ERRO] {e}")
        return 1

    outputs = history.get("outputs", {})
    images = extract_images(outputs)

    print("[5/5] Resultado:")
    if not images:
        print("       [AVISO] Nenhuma imagem encontrada nos outputs!")
        print(f"       Outputs: {json.dumps(outputs, indent=2)}")
        return 1

    for img in images:
        print(f"       - Node {img['node_id']}: {img['filename']}")
        full_path = os.path.join(OUTPUT_SYMLINK, img["subfolder"], img["filename"])
        print(f"         Path: {full_path}")

    # Sumario
    seed = wf_isolated["14"]["inputs"]["seed"]
    print("-" * 60)
    print("SUMARIO:")
    print(f"  Seed: {seed}")
    print(f"  Steps: {wf_isolated['14']['inputs']['steps']}")
    print(f"  CFG: {wf_isolated['14']['inputs']['cfg']}")
    print(f"  Sampler: {wf_isolated['14']['inputs']['sampler_name']}")
    print(f"  Modelo: {wf_isolated['4']['inputs']['ckpt_name']}")
    print(f"  Resolucao: {wf_isolated['1']['inputs']['width']}x{wf_isolated['1']['inputs']['height']}")
    print(f"  Ficheiros: {len(images)}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())

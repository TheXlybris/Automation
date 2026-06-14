#!/usr/bin/env python3
"""
generate_with_progress.py — Geração de imagem via ComfyUI com progresso real.

Usa WebSocket para progresso do sampler em tempo real + HTTP polling
para deteção fiável de conclusão (ComfyUI não envia execution_success via WS).
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
import urllib.error
import websocket
import threading


def load_workflow(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_progress_file(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def build_workflow(
    wf: dict,
    positive_prompt: str,
    negative_prompt: str,
    checkpoint: str,
    width: int,
    height: int,
    steps: int,
    seed: int,
    filename_prefix: str,
) -> dict:
    wf = json.loads(json.dumps(wf))  # deep copy

    for nid, node in wf.items():
        inputs = node.get("inputs", {})

        if node.get("class_type") == "CheckpointLoaderSimple":
            inputs["ckpt_name"] = checkpoint

        elif node.get("class_type") == "EmptyLatentImage":
            inputs["width"] = width
            inputs["height"] = height

        elif node.get("class_type") == "KSampler":
            inputs["seed"] = seed if seed >= 0 else random.randint(0, 2**32 - 1)
            inputs["steps"] = steps

        elif node.get("class_type") == "CLIPTextEncode":
            if nid == "6":
                inputs["text"] = positive_prompt
            elif nid == "7":
                inputs["text"] = negative_prompt

        elif node.get("class_type") == "SaveImage":
            inputs["filename_prefix"] = filename_prefix

    return wf


def queue_prompt(comfyui_url: str, workflow: dict) -> str:
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{comfyui_url}/prompt",
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


def poll_history(comfyui_url: str, prompt_id: str) -> dict:
    """Poll HTTP /history/{prompt_id} para estado completo do job."""
    try:
        req = urllib.request.Request(f"{comfyui_url}/history/{prompt_id}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            history = json.loads(resp.read().decode("utf-8"))
        return history.get(prompt_id, {})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}  # ainda não existe
        raise


def run_generation(args):
    progress = {
        "status": "initializing",
        "progress": 0,
        "current_node": None,
        "step": 0,
        "max_steps": args.steps,
        "message": "A inicializar...",
        "images": [],
        "error": None,
        "started_at": time.time(),
        "finished_at": None,
        "prompt_id": None,
    }
    update_progress_file(args.progress_file, progress)

    # 1. Carregar workflow
    progress["status"] = "loading_workflow"
    progress["message"] = f"A carregar workflow: {args.workflow}"
    update_progress_file(args.progress_file, progress)

    wf = load_workflow(args.workflow)
    seed = args.seed if args.seed >= 0 else random.randint(0, 2**32 - 1)
    wf = build_workflow(
        wf, args.prompt, args.negative, args.checkpoint,
        args.width, args.height, args.steps, seed,
        args.filename_prefix,
    )

    # 2. Enviar para ComfyUI
    progress["status"] = "queuing"
    progress["message"] = "A enviar para ComfyUI..."
    update_progress_file(args.progress_file, progress)

    try:
        prompt_id = queue_prompt(args.comfyui_url, wf)
    except Exception as e:
        progress["status"] = "error"
        progress["error"] = f"Falha ao enfileirar: {e}"
        progress["message"] = f"Erro ao enviar: {e}"
        progress["finished_at"] = time.time()
        update_progress_file(args.progress_file, progress)
        return 1

    progress["prompt_id"] = prompt_id
    progress["status"] = "queued"
    progress["message"] = f"Prompt enfileirado: {prompt_id[:8]}"
    update_progress_file(args.progress_file, progress)

    # 3. WebSocket listener (para progresso em tempo real)
    ws_url = args.comfyui_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    ws_connected = threading.Event()
    ws_last_progress = {"step": 0, "max": args.steps, "node": None}

    def on_ws_message(ws, message):
        if not isinstance(message, str):
            return
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type", "")
        data = msg.get("data", {})

        if msg_type == "progress":
            step = data.get("value", 0)
            max_steps = data.get("max", args.steps)
            node_id = data.get("node")
            ws_last_progress["step"] = step
            ws_last_progress["max"] = max_steps
            ws_last_progress["node"] = node_id

        elif msg_type == "execution_start":
            ws_last_progress["status"] = "running"

    def on_ws_error(ws, err):
        pass  # Silenciar erros WS (usamos HTTP fallback)

    def on_ws_close(ws, code, msg):
        pass

    def run_ws():
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_ws_message,
            on_error=on_ws_error,
            on_close=on_ws_close,
        )
        ws_connected.set()
        ws.run_forever(ping_interval=10, ping_timeout=5)

    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()

    # 4. Loop principal: HTTP polling + sincronização de progresso WS
    max_wait = 600  # 10 minutos
    start_wait = time.time()
    last_http_check = 0
    completed = False
    images = []

    while time.time() - start_wait < max_wait:
        time.sleep(1)
        now = time.time()

        # Atualizar progress file com dados do WebSocket (a cada 1-2 segundos)
        step = ws_last_progress.get("step", 0)
        max_steps = ws_last_progress.get("max", args.steps)
        node_id = ws_last_progress.get("node")
        if max_steps > 0:
            sampler_pct = (step / max_steps) * 80
        else:
            sampler_pct = 0
        progress["step"] = step
        progress["max_steps"] = max_steps
        progress["progress"] = int(10 + sampler_pct)
        progress["current_node"] = node_id
        progress["message"] = f"Sampler: step {step}/{max_steps}" if step > 0 else "A inicializar..."
        if ws_last_progress.get("status") == "running":
            progress["status"] = "running"

        # HTTP polling: verificar /history a cada 5 segundos
        if now - last_http_check >= 5:
            last_http_check = now
            try:
                history = poll_history(args.comfyui_url, prompt_id)
                if history:
                    status_info = history.get("status", {})
                    if status_info.get("completed"):
                        # Concluído! Extrair imagens
                        for node_id, out in history.get("outputs", {}).items():
                            for img in out.get("images", []):
                                if img.get("type") == "output":
                                    images.append({
                                        "node_id": node_id,
                                        "filename": img["filename"],
                                        "subfolder": img.get("subfolder", ""),
                                    })
                        progress["status"] = "completed"
                        progress["progress"] = 100
                        progress["images"] = images
                        progress["message"] = f"Concluído! {len(images)} imagem(ns) gerada(s)"
                        progress["finished_at"] = time.time()
                        completed = True
                        update_progress_file(args.progress_file, progress)
                        break

                    elif status_info.get("status_str") == "error":
                        progress["status"] = "error"
                        progress["error"] = "Erro reportado pelo ComfyUI"
                        progress["message"] = "Erro no ComfyUI"
                        progress["finished_at"] = time.time()
                        completed = True
                        update_progress_file(args.progress_file, progress)
                        break
            except Exception:
                pass  # Ignorar falhas temporárias de HTTP

        update_progress_file(args.progress_file, progress)

    # Se saiu por timeout
    if not completed:
        progress["status"] = "error"
        progress["error"] = "Timeout após 10 minutos"
        progress["message"] = "Timeout — ComfyUI não reportou conclusão"
        progress["finished_at"] = time.time()
        update_progress_file(args.progress_file, progress)

    # 5. Resultado
    if progress["status"] == "completed":
        for img in images:
            sub = img["subfolder"]
            fname = img["filename"]
            full = os.path.join(args.output_dir, sub, fname) if sub else os.path.join(args.output_dir, fname)
            print(f"OUTPUT_IMAGE: {full}")
        print(f"SEED: {seed}")
        return 0
    else:
        print(f"ERROR: {progress.get('error', 'Desconhecido')}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="Gerar imagem via ComfyUI com progresso real")
    parser.add_argument("--workflow", required=True, help="Path ao workflow JSON (API format)")
    parser.add_argument("--prompt", required=True, help="Prompt positivo")
    parser.add_argument("--negative", default="", help="Prompt negativo")
    parser.add_argument("--checkpoint", default="DreamShaperXL_Turbo_v2_1.safetensors", help="Checkpoint a usar")
    parser.add_argument("--width", type=int, default=2400, help="Largura")
    parser.add_argument("--height", type=int, default=1350, help="Altura")
    parser.add_argument("--steps", type=int, default=70, help="Steps do sampler")
    parser.add_argument("--seed", type=int, default=-1, help="Seed (-1 = aleatório)")
    parser.add_argument("--cfg", type=float, default=7.0, help="CFG scale")
    parser.add_argument("--filename-prefix", default="AGENTGUI", help="Prefixo do ficheiro")
    parser.add_argument("--output-dir", default="/mnt/d/AI_Ecosystem/04_Data/Hermes/images/output", help="Pasta de output")
    parser.add_argument("--progress-file", required=True, help="Path ao file JSON de progresso")
    parser.add_argument("--comfyui-url", default="http://192.168.144.1:8188", help="URL do ComfyUI")
    args = parser.parse_args()

    return run_generation(args)


if __name__ == "__main__":
    sys.exit(main())

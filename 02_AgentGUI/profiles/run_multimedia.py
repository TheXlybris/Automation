#!/usr/bin/env python3
"""
Runner para o perfil Multimedia.
Recebe AGENT_ID como argumento.

Se a tarefa tem 'prompt' (geracao de imagem), invoca generate_with_progress.py
para progresso real via WebSocket do ComfyUI.
Senao, delega ao Hermes chat generico.
"""

import sys
import json
import subprocess
import os
import time
from pathlib import Path

AGENT_ID = sys.argv[1]
BASE_DIR = Path(os.environ.get("AGENTUI_DIR", "/mnt/d/AI_Ecosystem/10_Projects/02_AgentGUI"))
TASK_FILE = BASE_DIR / "data" / f"{AGENT_ID}_task.json"
LOG_FILE = BASE_DIR / "data" / f"{AGENT_ID}.log"
PROGRESS_FILE = Path(f"/tmp/progress_{AGENT_ID}.json")

sys.path.insert(0, str(BASE_DIR))
from core.state import update_agent


def run_with_progress(task: dict):
    """Executa geracao de imagem com progresso real via ComfyUI WebSocket."""
    update_agent(AGENT_ID, status="running", progress=5,
                 message="A inicializar geracao de imagem...")

    prompt = task.get("prompt", "")
    negative = task.get("negative_prompt", "")
    context = task.get("context", "")

    # Defaults do projeto
    checkpoint = task.get("checkpoint", "DreamShaperXL_Turbo_v2_1.safetensors")
    width = task.get("width", 2400)
    height = task.get("height", 1350)
    steps = task.get("steps", 70)
    seed = task.get("seed", -1)
    prefix = task.get("filename_prefix", "AGENTGUI")

    workflow_path = task.get("workflow_path", "/mnt/d/AI_Ecosystem/03_Workflows/API/Text2Image.json")
    comfyui_url = task.get("comfyui_url", "http://192.168.144.1:8188")
    output_dir = task.get("output_dir", "/mnt/d/AI_Ecosystem/04_Data/Hermes/images/output")

    cmd = [
        sys.executable,
        str(BASE_DIR / "generate_with_progress.py"),
        "--workflow", workflow_path,
        "--prompt", prompt,
        "--negative", negative,
        "--checkpoint", checkpoint,
        "--width", str(width),
        "--height", str(height),
        "--steps", str(steps),
        "--seed", str(seed),
        "--filename-prefix", prefix,
        "--output-dir", output_dir,
        "--progress-file", str(PROGRESS_FILE),
        "--comfyui-url", comfyui_url,
    ]

    # Limpar progress file anterior
    PROGRESS_FILE.unlink(missing_ok=True)

    update_agent(AGENT_ID, progress=10, message="A lancar gerador com progresso real...")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=str(BASE_DIR),
    )

    last_progress = 0
    last_message = ""
    max_wait = task.get("timeout_seconds", 1200)
    start = time.time()

    # Polling: ler progress file + verificar se processo terminou
    while proc.poll() is None and time.time() - start < max_wait:
        time.sleep(2)

        if PROGRESS_FILE.exists():
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    pdata = json.load(f)

                progress = pdata.get("progress", 0)
                status = pdata.get("status", "running")
                message = pdata.get("message", "A gerar...")

                # Evitar spam de updates iguais
                if progress != last_progress or message != last_message:
                    update_agent(
                        AGENT_ID,
                        status="running",
                        progress=progress,
                        message=message,
                    )
                    last_progress = progress
                    last_message = message

            except (json.JSONDecodeError, IOError):
                pass

    # Processo terminou (ou timeout)
    try:
        stdout, stderr = proc.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    rc = proc.returncode

    # Ler estado final do progress file
    final_progress = {"status": "unknown", "images": [], "error": None}
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                final_progress = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Compilar log
    log_content = f"""=== STDOUT ===
{stdout}
=== STDERR ===
{stderr}
=== PROGRESS FINAL ===
{json.dumps(final_progress, indent=2)}
=== RC: {rc} ==="""

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(log_content)

    images = final_progress.get("images", [])
    error = final_progress.get("error")

    if rc == 0 and final_progress.get("status") == "completed" and images:
        img_paths = []
        for img in images:
            sub = img.get("subfolder", "")
            fname = img["filename"]
            p = os.path.join(output_dir, sub, fname) if sub else os.path.join(output_dir, fname)
            img_paths.append(p)

        update_agent(
            AGENT_ID,
            status="completed",
            progress=100,
            message=f"Concluido: {len(images)} imagem(ns) gerada(s)",
            output_append=f"Imagens geradas:\n" + "\n".join(img_paths) + f"\n\nSeed: {final_progress.get('step', 'N/A')}",
        )
    else:
        err_msg = error or stderr[:300] or f"RC {rc}"
        update_agent(
            AGENT_ID,
            status="error",
            progress=last_progress,
            message=f"Erro: {err_msg[:80]}",
            error=err_msg,
            output_append=stdout[:4000],
        )


def run_with_hermes(task: dict, soul: str):
    """Delega ao agente Hermes generico (analise, audio, etc.)."""
    update_agent(AGENT_ID, status="running", progress=10, message="A ler tarefa e SOUL.md...")

    prompt = f"""{soul}

## TAREFA
{task['goal']}

## PROMPT DA IMAGEM
{task.get('prompt', '')}

## CONTEXTO DO PROJETO
{task.get('context', '')}

## INSTRUCOES
1. Executa a tarefa de acordo com as regras do perfil Multimedia.
2. Usa ferramentas de geracao (ComfyUI) ou analise (vision) conforme necessario.
3. Respeita limites de VRAM: RTX 4060 Ti 16GB (modelos ate 2B para img2vid).
4. Devolve a resposta em Portugues (PT-PT).

Comeca agora."""

    update_agent(AGENT_ID, progress=30, message="A invocar hermes chat -q...")

    cmd = ["hermes", "chat", "-q", prompt, "-Q", "--ignore-rules", "--source", "tool"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=task.get("timeout_seconds", 1200), cwd=str(BASE_DIR)
        )
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"=== STDOUT ===\n{result.stdout}\n=== STDERR ===\n{result.stderr}\n=== RC: {result.returncode} ===")

        if result.returncode == 0:
            update_agent(AGENT_ID, status="completed", progress=100,
                         message="Tarefa concluida", output_append=result.stdout[:9000])
        else:
            update_agent(AGENT_ID, status="error", message="Erro durante execucao",
                         error=f"RC {result.returncode}: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        update_agent(AGENT_ID, status="error", error="Timeout")
    except Exception as e:
        update_agent(AGENT_ID, status="error", error=f"Excecao: {str(e)}")


def main():
    if not TASK_FILE.exists():
        update_agent(AGENT_ID, status="error", error=f"Task file nao encontrado: {TASK_FILE}")
        return

    with open(TASK_FILE, "r", encoding="utf-8") as f:
        task = json.load(f)

    # Carregar SOUL.md do perfil multimedia
    soul_path = Path.home() / ".hermes" / "profiles" / "multimedia" / "SOUL.md"
    soul = ""
    if soul_path.exists():
        with open(soul_path, "r", encoding="utf-8") as f:
            soul = f.read()

    # Decidir: geracao de imagem (tem prompt longo) ou delegar ao Hermes
    has_prompt = bool(task.get("prompt", "").strip())
    is_image_gen = has_prompt and len(task.get("prompt", "")) > 20

    if is_image_gen:
        run_with_progress(task)
    else:
        run_with_hermes(task, soul)


if __name__ == "__main__":
    main()

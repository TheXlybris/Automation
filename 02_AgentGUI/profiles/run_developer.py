#!/usr/bin/env python3
"""
Runner para o perfil Developer.
Recebe AGENT_ID como argumento.
"""

import sys
import json
import subprocess
import os
from pathlib import Path

AGENT_ID = sys.argv[1]
BASE_DIR = Path(os.environ.get("AGENTUI_DIR", "/mnt/d/AI_Ecosystem/10_Projects/02_AgentGUI"))
TASK_FILE = BASE_DIR / "data" / f"{AGENT_ID}_task.json"
LOG_FILE = BASE_DIR / "data" / f"{AGENT_ID}.log"

sys.path.insert(0, str(BASE_DIR))
from core.state import update_agent

def main():
    update_agent(AGENT_ID, status="running", progress=10, message="A ler tarefa e SOUL.md...")

    if not TASK_FILE.exists():
        update_agent(AGENT_ID, status="error", error=f"Task file nao encontrado: {TASK_FILE}")
        return

    with open(TASK_FILE, 'r', encoding='utf-8') as f:
        task = json.load(f)

    soul_path = Path.home() / ".hermes" / "profiles" / "developer" / "SOUL.md"
    if soul_path.exists():
        with open(soul_path, 'r', encoding='utf-8') as f:
            soul = f.read()
    else:
        soul = "# Developer Agent\n\nCode, debug, optimize."

    update_agent(AGENT_ID, progress=20, message="A construir prompt...")

    prompt = f"""{soul}

## TAREFA
{task['goal']}

## CONTEXTO DO PROJETO
{task.get('context', '')}

## INSTRUCOES
1. Executa a tarefa de acordo com as regras do perfil Developer.
2. Escreve codigo em Python, Bash, JavaScript ou outra linguagem conforme necessario.
3. VERIFICA antes de afirmar — corre o codigo, testa, confirma que funciona.
4. Devolve a resposta em Portugues (PT-PT).

Comeca agora."""

    update_agent(AGENT_ID, progress=30, message="A invocar hermes chat -q...")

    cmd = ["hermes", "chat", "-q", prompt, "-Q", "--ignore-rules", "--source", "tool"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=task.get("timeout_seconds", 1200), cwd=str(BASE_DIR)
        )
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
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

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Runner para o perfil Researcher.
Recebe AGENT_ID como argumento.
Escreve progresso para stdout (visivel no tmux) e resultado para log file.
"""

import sys
import json
import subprocess
import os
from pathlib import Path

AGENT_ID = sys.argv[1]
BASE_DIR = Path(os.environ.get("AGENTUI_DIR", "/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI"))
TASK_FILE = BASE_DIR / "data" / f"{AGENT_ID}_task.json"
LOG_FILE = BASE_DIR / "data" / f"{AGENT_ID}.log"

def report(msg: str, progress: int = None):
    """Print to tmux AND update state."""
    print(f"[{AGENT_ID}] {msg}", flush=True)
    try:
        sys.path.insert(0, str(BASE_DIR))
        from core.state import update_agent
        if progress is not None:
            update_agent(AGENT_ID, message=msg, progress=progress)
        else:
            update_agent(AGENT_ID, message=msg)
    except Exception:
        pass

def main():
    report("A ler tarefa e SOUL.md...", 10)

    if not TASK_FILE.exists():
        report(f"ERRO: Task file nao encontrado: {TASK_FILE}", 0)
        return

    with open(TASK_FILE, 'r', encoding='utf-8') as f:
        task = json.load(f)

    soul_path = Path.home() / ".hermes" / "profiles" / "researcher" / "SOUL.md"
    soul = ""
    if soul_path.exists():
        with open(soul_path, 'r', encoding='utf-8') as f:
            soul = f.read()

    report("A construir prompt...", 20)

    prompt = f"""{soul}

## TAREFA
{task['goal']}

## CONTEXTO DO PROJETO
{task.get('context', '')}

## INSTRUCOES
1. Executa a tarefa de acordo com as regras do perfil Researcher.
2. Pesquisa web (web_search) e le ficheiros (read_file) conforme necessario.
3. SINTETIZA os resultados -- nao copies resultados crus.
4. Devolve a resposta final em Portugues (PT-PT).
5. Inclui tabelas para comparacoes e links diretos para fontes.

Comeca agora."""

    report("A invocar hermes chat -q...", 30)

    cmd = ["hermes", "chat", "-q", prompt, "-Q", "--ignore-rules", "--source", "tool"]
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as logf:
            logf.write(f"=== AGENT: {AGENT_ID} ===\n")
            logf.write(f"=== TASK: {task['goal']} ===\n\n")
            
            result = subprocess.run(
                cmd,
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                timeout=task.get("timeout_seconds", 1200),
                cwd=str(BASE_DIR)
            )
            
            logf.write(f"\n=== RETURN CODE: {result.returncode} ===\n")

        if result.returncode == 0:
            report("Tarefa concluida", 100)
            # Read log and store in state
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                sys.path.insert(0, str(BASE_DIR))
                from core.state import update_agent
                update_agent(AGENT_ID, status="completed", output_append=content[-9000:])
            except Exception:
                pass
        else:
            report(f"Erro: return code {result.returncode}", 0)
            sys.path.insert(0, str(BASE_DIR))
            from core.state import update_agent
            update_agent(AGENT_ID, status="error", error=f"RC {result.returncode}")

    except subprocess.TimeoutExpired:
        report("ERRO: Timeout", 0)
        sys.path.insert(0, str(BASE_DIR))
        from core.state import update_agent
        update_agent(AGENT_ID, status="error", error="Timeout")
    except Exception as e:
        report(f"ERRO: {e}", 0)
        sys.path.insert(0, str(BASE_DIR))
        from core.state import update_agent
        update_agent(AGENT_ID, status="error", error=str(e))

if __name__ == "__main__":
    main()

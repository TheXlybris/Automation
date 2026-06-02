# AgentGUI Runner Fixes -- Bugs Encontrados e Resolucoes (Maio 2026)

## Contexto
Session de debugging do AgentGUI: o agente multimedia era lancado com sucesso pelo dashboard mas nunca gerava a imagem. Root cause foi uma cadeia de 3 bugs nos runners (`run_multimedia.py`, `run_developer.py`, `run_researcher.py`).

---

## Bug 1: Prompt nao passado ao agente (TODOS os runners)

**Sintoma:** Agente multimedia diz "qual e o prompt que queres usar?" mesmo quando o task.json tem o prompt completo.

**Root cause:** O runner construia o prompt com `task['goal']` mas omitia o campo `task['prompt']` que o dashboard enviava.

**Fix** (em todos os 3 runners: multimedia, developer, researcher):
```python
prompt = f"""{soul}

## TAREFA
{task['goal']}

## PROMPT DA IMAGEM
{task.get('prompt', '')}

## CONTEXTO DO PROJETO
{task.get('context', '')}
...
"""
```

**Nota:** Para developer, o campo equivalente e `task.get('prompt', '')` ou `task.get('spec', '')`.

---

## Bug 2: Hermes CLI em modo interativo (TODOS os runners)

**Sintoma:** Runner chama `hermes chat -q` com `capture_output=True`, mas o processo hermes inicia uma sessao interativa completa e fica bloqueado a esperar input do stdin.

**Root cause:** `hermes chat -q` (single query) nao e equivalente a "executa uma vez e sai imediatamente" -- e preciso adicionar flags para modo programatico.

**Fix:** Usar a combinacao CORRETA de flags do hermes CLI:
```python
cmd = ['hermes', 'chat', '-q', prompt, '-Q', '--ignore-rules', '--source', 'tool']
result = subprocess.run(
    cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    timeout=..., cwd=...
)
```

| Flag | Funcao |
|------|--------|
| `-q QUERY` | Single query (nao-interativo) |
| `-Q, --quiet` | Suprime banner, spinner, tool previews. So emite resposta final + info. **CRITICO para subprocess.** |
| `--ignore-rules` | Nao injecta AGENTS.md, SOUL.md, .cursorrules, memory. Runner ja injecta regras via prompt. |
| `--source tool` | Session source tag -- distingue agentes programaticos dos interativos. |
| `stdin=subprocess.DEVNULL` | Garante que processo nao fica bloqueado esperando stdin. |

**Teste validador:**
```bash
# Deve retornar em <10s com output curto
time timeout 15 hermes chat -q "Diz ola em 1 palavra" -Q --ignore-rules --source tool
# Output exemplo:
# session_id: 20260517_212121_65f80e
# Ola
```

---

## Bug 3: Log file nao escrito durante execucao (runner multimedia/developer)

**Sintoma:** Log file fica 0 bytes enquanto a tarefa corre.

**Root cause:** So escreve no log no final. Se processo crasha ou é terminado, log fica vazio.

**Fix:** Redireccionar stdout/stderr directamente para o file descriptor do log:
```python
with open(LOG_FILE, 'w', encoding='utf-8') as logf:
    logf.write(f"=== AGENT: {AGENT_ID} ===\n")
    result = subprocess.run(
        cmd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        timeout=..., cwd=...
    )
    logf.write(f"\n=== RETURN CODE: {result.returncode} ===\n")
```

`run_researcher.py` ja usava este pattern -- foi copiado para os outros.

---

## Arquitectura corrigida do runner (template completo)

```python
#!/usr/bin/env python3
import sys, json, subprocess, os
from pathlib import Path

AGENT_ID = sys.argv[1]
BASE_DIR = Path(os.environ.get("AGENTUI_DIR", "/mnt/d/AI_Ecosystem/10_Projects/02_AgentGUI"))
TASK_FILE = BASE_DIR / "data" / f"{AGENT_ID}_task.json"
LOG_FILE = BASE_DIR / "data" / f"{AGENT_ID}.log"
sys.path.insert(0, str(BASE_DIR))
from core.state import update_agent

def main():
    update_agent(AGENT_ID, status="running", progress=10,
                  message="A ler tarefa e SOUL.md...")

    with open(TASK_FILE, 'r', encoding='utf-8') as f:
        task = json.load(f)

    soul_path = Path.home() / ".hermes" / "profiles" / task['profile'] / "SOUL.md"
    soul = soul_path.read_text(encoding='utf-8') if soul_path.exists() else ""

    update_agent(AGENT_ID, progress=20, message="A construir prompt...")

    prompt = f"""{soul}

## TAREFA
{task['goal']}

## PROMPT
{task.get('prompt', '')}

## CONTEXTO DO PROJETO
{task.get('context', '')}

## INSTRUCOES
1. Executa a tarefa de acordo com as regras do perfil.
2. Devolve a resposta em Portugues (PT-PT).

Comeca agora."""

    update_agent(AGENT_ID, progress=30, message="A invocar hermes chat -q...")

    cmd = ['hermes', 'chat', '-q', prompt, '-Q', '--ignore-rules', '--source', 'tool']

    with open(LOG_FILE, 'w', encoding='utf-8') as logf:
        logf.write(f"=== AGENT: {AGENT_ID} ===\n=== TASK: {task['goal']} ===\n\n")
        result = subprocess.run(
            cmd, stdout=logf, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=task.get("timeout_seconds", 1200),
            cwd=str(BASE_DIR)
        )
        logf.write(f"\n=== RETURN CODE: {result.returncode} ===\n")

    if result.returncode == 0:
        update_agent(AGENT_ID, status="completed", progress=100,
                     message="Tarefa concluida")
    else:
        update_agent(AGENT_ID, status="error",
                     message="Erro durante execucao",
                     error=f"RC: {result.returncode}")

if __name__ == "__main__":
    main()
```

---

## Resumo das alteracoes aplicadas
| Ficheiro | Alteracoes |
|---|---|
| run_multimedia.py | +prompt field, -Q --ignore-rules --source tool, stdin=DEVNULL, stdout live logging |
| run_developer.py | +prompt field, -Q --ignore-rules --source tool, stdin=DEVNULL, stdout live logging |
| run_researcher.py | +prompt field, -Q --ignore-rules --source tool, stdin=DEVNULL |

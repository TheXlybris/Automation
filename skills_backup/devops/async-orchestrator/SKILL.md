---
name: async-orchestrator
description: "Orchestrate background tasks by dispatching to specialized profiles via cron jobs. True async parallelism for THE RENDER WAVE team."
version: 1.0.0
author: Hermes Agent
---

## References
- `references/img2vid-fantasy-rtx4060ti-2026-05-17.md` — Research results: which img2vid models fit 16GB VRAM
- `references/agentgui-runner-fixes-2026-05.md` — Debugging session: 3 bugs in AgentGUI runners with reproduction recipes and corrected runner template

---

# Async Orchestrator

## Team Members

| Member | Domain | Trigger | SOUL Path |
|--------|--------|---------|-----------|
| `developer` | Code, debugging, scripts | coding tasks | `~/.hermes/profiles/developer/SOUL.md` |
| `researcher` | Web research, comparisons | research tasks | `~/.hermes/profiles/researcher/SOUL.md` |
| `multimedia` | Image/video/audio creation & analysis | media tasks | `~/.hermes/profiles/multimedia/SOUL.md` |

## Dispatch Protocol

### Step 1: Identify task type
Read user request → match keywords to team member.

### Step 2: Load profile rules
Read the target profile's `SOUL.md` to inject rules into the job prompt.

### Step 3: Create one-shot cron job
Use the `cronjob` tool (NOT Python pseudocode — make a real tool call):
```json
{
  "action": "create",
  "name": "task-{member}-{uuid}",
  "prompt": "[CRITICAL: You are a scheduled cron job. DELIVERY: Your final response will be automatically delivered — do NOT use send_message. Just produce your report as your final response and the system handles delivery. SILENT: If nothing new to report, respond with exactly \"[SILENT]\".]\n\n[PROFILE RULES from SOUL.md]\n\n## Task\n{user_request}\n\n## Context\n{project_context}\n\nExecute according to profile rules.",
  "schedule": "1m",
  "deliver": "origin",
  "enabled_toolsets": ["web", "terminal", "file", "vision", "video"]
}
```

### Step 4: Notify user
Tell user: "✅ Deleguei ao {member}. Corre em background. Vou avisar quando acabar."

### Step 5: Receive result OR check fallback
The scheduler may fail to deliver back to the CLI session. If no result arrives within 5-10 minutes:
- Look for the output in the cron output directory: `~/.hermes/cron/output/{job_id}/`
- Read the `.md` file there — that's the full result
- Present the result manually to the user

```bash
ls ~/.hermes/cron/output/  # list completed job IDs
cat ~/.hermes/cron/output/{job_id}/YYYY-MM-DD_HH-MM-SS.md
```

### Step 6: Default behavior rule
**Async delegation to specialized profiles is the DEFAULT behavior** for research, analysis, and media generation tasks. Do NOT perform these tasks inline yourself.

## Known Pitfalls & Platform Limitations

### AgentGUI Runner Bugs (May 2026)
When spawning Hermes agents as subprocesses from the AgentGUI dashboard, three bugs were found and fixed:

1. **Prompt not passed:** `run_multimedia.py` only included `task['goal']` in the prompt, omitting `task['prompt']` which the dashboard sent. Fix: add `## PROMPT DA IMAGEM\n{task.get('prompt', '')}` to the f-string.

2. **Hermes CLI interactive hang:** `hermes chat -q` without `-Q` starts a full interactive session and blocks on stdin. Fix: use the programmatic flag set: `-q <prompt> -Q --ignore-rules --source tool`, plus `stdin=subprocess.DEVNULL` in `subprocess.run()`.

3. **Log file stays at 0 bytes:** Using `capture_output=True` and writing the log only at the end means crashes leave empty log files. Fix: redirect stdout/stderr directly to the log file handle during `subprocess.run(stdout=logf, stderr=subprocess.STDOUT)`.

Full reproduction and fix details: `references/agentgui-runner-fixes-2026-05.md`.

### Cron `deliver='origin'` in CLI sessions
Cron jobs with `deliver='origin'` **do NOT reliably deliver back to an interactive CLI session**. The scheduler daemon runs (PID 386) and jobs execute, but delivery back to the original chat thread often fails silently.

**Symptom:** Job stays in status `scheduled` indefinitely, or runs but no result appears in chat.

**Workaround (immediate):** After creating a cron job, manually check the output directory if no delivery arrives within 2-3 minutes:
```bash
ls ~/.hermes/cron/output/{job_id}/
cat ~/.hermes/cron/output/{job_id}/*.md
```

**Workaround (robust):** Run `delegate_task` with `role='leaf'` instead of cron -- it blocks the orchestrator but runs the subagent in a separate isolated context. The orchestrator can then continue with a manual results-check loop, or the user builds a separate dashboard (see AgentGUI below) to monitor agents.

### Cron jobs not appearing in `list`
Sometimes `cronjob(action='create')` reports success but the job is not persisted in `~/.hermes/cron/jobs.json`. The scheduler daemon shows no active jobs even though creation succeeded.

**Symptom:** `hermes cron list` shows 0 active jobs immediately after creation.

**Workaround:** Use `delegate_task` for interactive async work, or build a persistent dashboard (see AgentGUI below).

## Alternative: AgentGUI Dashboard (Recommended for CLI)

For true parallelism where the orchestrator stays free and results are viewable on demand, use the **AgentGUI** dashboard instead of cron:

| Feature | Cron + `deliver='origin'` | AgentGUI |
|---------|---------------------------|----------|
| Orchestrator stays free | Sometimes | Yes |
| Result delivery | Unreliable in CLI | Manual check (always works) |
| Visual progress | No | Web UI with bar, status, output |
| Kill/cancel agent | No | Yes |
| Reusable across projects | No | Yes |

**How to use AgentGUI:**
1. Build Flask server + frontend in `D:/AI_Ecosystem/10_Projects/02_AgentGUI/`
2. Agents launch via `tmux` (independent system processes)
3. Each agent writes progress to central JSON state file
4. Dashboard polls/SSE-shows progress in real time
5. User checks dashboard anytime for results, no delivery needed

**Default behavior rule (updated):**
- **Gateway platforms (Telegram, Discord, etc.):** Use `cronjob` with `deliver='origin'` -- delivery works there.
- **Interactive CLI sessions:** Prefer `delegate_task` for synchronous subagents, or **AgentGUI** for true background parallelism.
- **Research/media/analysis tasks:** Delegate -- don't do inline.

### AgentGUI Architecture
A working implementation exists at `D:/AI_Ecosystem/10_Projects/02_AgentGUI/`:
- `server.py` — Flask API + SSE, port 5020
- `core/state.py` — JSON state manager (thread-safe)
- `core/runner.py` — tmux session launcher, output capture, kill
- `profiles/run_{profile}.py` — wrappers that invoke `hermes chat -q` with SOUL.md
- `templates/index.html` — dashboard UI with launch form, table, modal
- `static/style.css` — dark theme, progress bars
- `static/app.js` — SSE, filters, buttons, modal

Key design: agents are independent tmux processes. The dashboard checks `tmux list-sessions` to detect if an agent finished. Use `./start_server.sh` to launch.

## Rules for the Orchestrator

1. **Never do the task myself** if a team member exists for it.
2. **Always announce delegation** before creating the cron job.
3. **Never block** -- create job, move on.
4. **Handle result delivery** when it arrives -- present to user with minimal delay.
5. **If result is incomplete**, create follow-up job or ask user if retry is needed.
6. **One-shot only** -- use `schedule='1m'` for immediate async execution. Recurring schedules are for future needs only.

## Project Context Template (inject into every job)

```
THE RENDER WAVE project:
- RTX 4060 Ti 16GB hardware constraint
- LTX Video 2B v0.9.5 for img2vid (~4s clips)
- SDXL + IP-Adapter PLUS for coherent images
- Fantasy/animation style ONLY (no photorealism)
- 2400x1350 resolution for storyboard images
- Workflows immutable in D:/AI_Ecosystem/03_Workflows/API/
- ComfyUI on Windows localhost (127.0.0.1), WSL accesses via 192.168.144.1
- Scripts live in D:/AI_Ecosystem/10_Projects/01_YTAutomation/Script_creation/
- Outputs via symlinks only — never move/copy ComfyUI files
```

## Example: Video Analysis

User: "Analisa este vídeo"
→ Identify: `multimedia`
→ Load: `~/.hermes/profiles/multimedia/SOUL.md`
→ Create cron job with:
   - prompt = multimedia rules + "Analiza o vídeo X. Reporta modelo, parâmetros, artefactos, qualidade."
   - toolsets = terminal, vision, video
   - deliver = 'origin'
→ Tell user: "A equipa multimedia está a analisar. Volto já com os resultados."
→ When result arrives: "Aqui está a análise do vídeo: [summary]"

## Example: Bug Fix

User: "o script dá erro na linha 45"
→ Identify: `developer`
→ Load: `~/.hermes/profiles/developer/SOUL.md`
→ Create cron job with:
   - prompt = developer rules + "Debug script X, linha 45. Verifica e propõe fix mínimo."
   - toolsets = terminal, file, code_execution
   - deliver = 'origin'
→ Tell user: "O developer está em cima do bug. Já volto."
→ When result arrives: "Fix identificado: [change]"

## Example: Research

User: "quais modelos img2vid novos para 16GB?"
→ Identify: `researcher`
→ Load: `~/.hermes/profiles/researcher/SOUL.md`
→ Create cron job with:
   - prompt = researcher rules + "Research img2vid models ≤16GB VRAM. Pros/cons/links."
   - toolsets = web, search
   - deliver = 'origin'
→ Tell user: "O researcher está a pesquisar. Volto já com o relatório."
→ When result arrives: "Encontrei N modelos: [summary with links]"

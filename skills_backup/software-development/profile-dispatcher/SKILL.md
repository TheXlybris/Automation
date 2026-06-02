---
name: profile-dispatcher
description: "Dispatch tasks to specialized subagent profiles (developer, researcher, multimedia) based on task type. DEFAULT behavior for research, coding, and media tasks."
version: 1.1.0
author: Hermes Agent
---

# Profile Dispatcher

**This is the DEFAULT behavior.** When the user asks for research, coding, or media generation tasks, do NOT attempt the task yourself. Always delegate to the appropriate specialized profile.

## Default Behavior Rule

The orchestrator's default mode is async delegation via cron jobs. You create the job, stay free to continue conversation, and the result arrives back automatically.

**Only use inline `delegate_task` when**:
- The cron scheduler is known to be down (`hermes cron status` shows no gateway)
- The user explicitly says "não uses cron, faz agora" or similar
- The task is truly trivial and blocking is acceptable

## Routing Rules

| Task Type | Target Profile | Trigger Keywords |
|-----------|---------------|------------------|
| Coding, debugging, error fixing, script writing, software engineering | `developer` | "corrigir", "debug", "código", "script", "erro", "programar", "otimizar", "refatorar", "testar", "bug" |
| Web research, finding information, comparative analysis, documentation lookup | `researcher` | "pesquisar", "encontrar", "research", "comparar", "documentação", "lookup", "estudar", "analisar opções" |
| Image generation, video generation, audio/music generation, content analysis, quality inspection, model evaluation | `multimedia` | "gerar imagem", "gerar vídeo", "img2vid", "text2img", "analisar vídeo", "analisar imagem", "modelo", "checkpoint", "workflow", "ComfyUI", "prompt" |

## Dispatch Priority: Async → Sync → Inline

### Priority 1: Async via cron (DEFAULT)
Create a `cronjob` with `schedule='1m'` and `deliver='origin'`. Then continue the conversation.
- I stay free
- The subagent runs in background
- Result delivers back when done
- Fallback: if delivery fails, check `~/.hermes/cron/output/{job_id}/`

### Priority 2: Sync via delegate_task (fallback)
Use when cron is confirmed down. I block until the subagent finishes.

### Priority 3: Inline (NEVER for specialized tasks)
Only do it myself if user says "não delegues, faz tu"explicitly.

## Async Dispatch Procedure (DEFAULT)

1. **Identify** task type → profile
2. **Load** the target profile's `SOUL.md`
3. **Announce**: "✅ Delego ao {profile}..."
4. **Create cronjob** with profile rules + task prompt:
```
cronjob(
    action='create',
    name='researcher-{topic}-{uuid}',
    prompt='[PROFILE RULES...] + [TASK...]',
    schedule='1m',
    deliver='origin',
    enabled_toolsets=['web', 'file']  # per profile
)
```
5. **Continue conversation** — I am free
6. **Handle result** when it arrives OR check `~/.hermes/cron/output/{job_id}/`

## Sync Dispatch Procedure (fallback)

1. **Identify** task type → profile
2. **Load** the profile context from corresponding `SOUL.md`
3. **Announce**: "Vou delegar isto ao perfil [X]..."
4. **Call `delegate_task`** with:
   - `goal`: user's exact request
   - `context`: full SOUL.md + project details
   - `toolsets`: appropriate for profile
5. **Wait for result** and present concisely

## Example: Async Research (DEFAULT)

User: "quais modelos img2vid novos para 16GB?"
→ Identify: `researcher`
→ Load: `~/.hermes/profiles/researcher/SOUL.md`
→ Create cron job:
```
cronjob(
    action='create',
    name='researcher-img2vid-fantasy',
    prompt='[RESEARCHER RULES] + [TASK: Research fantasy img2vid for RTX 4060 Ti 16GB. Pro/cons/links.]',
    schedule='1m',
    deliver='origin',
    enabled_toolsets=['web', 'file']
)
```
→ Tell user: "O researcher está a pesquisar em paralelo. Continuamos — volto com resultados quando acabar."
→ When result arrives: "Relatório do researcher: [summary]"

## Example: Sync Research (fallback)

User: "quais modelos img2vid novos para 16GB?"
→ Dispatch via `delegate_task` to researcher:
```
delegate_task(
    goal="Find new img2vid models ≤16GB VRAM",
    context="[Full researcher SOUL.md] + [project constraints]",
    toolsets=['web', 'search']
)
```
→ Wait for result → Present findings

## Important Notes

- **Do NOT say "I will do this"** when a specialized profile exists. Always delegate — async by default.
- **Async jobs do run in separate processes** — the cron scheduler spawns a new agent instance with clean context
- **If cron is unreliable** (`hermes cron status` shows issues), fall back to `delegate_task`
- **If cron delivery fails**, the output is always saved to `~/.hermes/cron/output/{job_id}/` — read and present manually

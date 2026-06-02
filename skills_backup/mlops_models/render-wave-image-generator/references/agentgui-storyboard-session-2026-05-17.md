# AgentGUI Storyboard Pipeline — Session Status (2026-05-17)

## What Was Tested
End-to-end test of the AgentGUI dashboard (localhost:5020) launching a `multimedia` agent to generate a fantasy animation image via ComfyUI.

## Bugs Found and Fixed

### Bug 1: Prompt not passed to agent
`run_multimedia.py` only included `task['goal']` but omitted `task['prompt']`. The agent asked "what prompt do you want?" instead of using the provided prompt.

**Fix:** Added `## PROMPT DA IMAGEM\n{task.get('prompt', '')}` to the prompt construction in all three runners.

### Bug 2: Hermes CLI hangs in interactive mode
`hermes chat -q` without `-Q` starts a full interactive REPL and blocks on stdin forever.

**Fix:** Use the programmatic flag set:
```bash
hermes chat -q "$PROMPT" -Q --ignore-rules --source tool
```
- `-Q` = quiet mode (suppress banner, spinner, tool previews)
- `--ignore-rules` = don't inject AGENTS.md/SOUL.md/memory (runner already injects rules)
- `--source tool` = marks session as programmatic
- `stdin=subprocess.DEVNULL` = prevents stdin block

### Bug 3: Log file empty during execution
Runner used `capture_output=True` and wrote log only at the end. If process crashed, log was 0 bytes.

**Fix:** Redirect stdout/stderr directly to the log file handle:
```python
with open(LOG_FILE, 'w', encoding='utf-8') as logf:
    result = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT, ...)
```

## Test Result: SUCCESS

The multimedia agent successfully:
1. Loaded `Text2Image_IPAdapter_Coherent_API.json` workflow
2. Created a bypass version without IP-Adapter (relinked KSampler to CheckpointLoaderSimple)
3. Submitted to ComfyUI API at `192.168.144.1:8188`
4. Generated `STORYBOARD_fantasy_00001_.png` at 2400×1350
5. Saved to `04_Data/Hermes/images/output/`
6. Produced a full technical report (parameters, prompt analysis, next steps)

## Remaining Issue: No Real-Time Progress

The dashboard shows progress stuck at 30% for the entire generation. The progress bar only jumps to 100% when the agent finishes.

**Root cause:** The runner only updates state at start (30%) and end (100%). The Hermes agent's ComfyUI generation happens inside a subprocess with no feedback channel to the dashboard.

**Solution options:** See `references/agentgui-comfyui-progress.md` in the `async-orchestrator` skill.

## File Locations (AgentGUI)

| File | Purpose |
|------|---------|
| `server.py` | Flask API + SSE on port 5020 |
| `core/state.py` | JSON state manager |
| `core/runner.py` | tmux session launcher |
| `profiles/run_multimedia.py` | Hermes multimedia agent wrapper |
| `profiles/run_developer.py` | Hermes developer agent wrapper |
| `profiles/run_researcher.py` | Hermes researcher agent wrapper |
| `templates/index.html` | Dashboard UI |
| `start_server.sh` | Launch script |

## ComfyUI Workflow Used

`Text2Image_IPAdapter_Coherent_API.json` — the IP-Adapter workflow for coherent storyboard images. For isolated images (no reference), the agent created a script that bypasses IP-Adapter by relinking the KSampler input from node 13 (IPAdapterAdvanced) to node 4 (CheckpointLoaderSimple).

This pattern is useful when you want ONE coherent workflow file that handles both:
- With IP-Adapter: use as-is (LoadImage reference → PrepImageForClipVision → IPAdapterUnifiedLoader → IPAdapterAdvanced → KSampler)
- Without IP-Adapter: script re-links KSampler.model to CheckpointLoaderSimple directly

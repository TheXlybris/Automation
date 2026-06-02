# OpenCode Usage Patterns — Session Learnings

## Output Delivery

### Problem: Code generated in TUI mode may not be written to disk
**Observed:** User instructed opencode to write `run_img2vid.py` to a specific path. The TUI responded in 16 seconds with generated code in the chat, but the file was never created on disk.

**Root cause:** In TUI/interactive mode, opencode treats the conversation as the primary output. It may show generated code in the chat panel without persisting it unless explicitly instructed with "write this file to disk at <path>" or confirmed by the user.

**Fix / best practice:**
- When using `opencode run` (non-interactive mode), use explicit file-write language: "Create and save the file at /path/to/file.py"
- When using interactive TUI mode, after seeing generated code, explicitly say "write this to <path>" or use the edit tool (Ctrl+X E) to save
- Verify with `ls -la <path>` after the session
- Prefer `opencode run` over TUI for file generation tasks — it's deterministic and exits cleanly

## Model Selection for Coding

| Use case | Recommended model | Why |
|----------|-------------------|-----|
| Complex architecture, debugging, reasoning | `ollama-cloud/kimi-k2.6:cloud` | Deep reasoning, large context |
| Code generation, quick scripts | `ollama-cloud/qwen3-coder-next` | Optimized for code, fast output |
| Default / small fixes | `rnj-1:8b` (default) | Fast, cheap, sufficient for simple tasks |

**Switch command:**
```
opencode run "..." --model ollama-cloud/qwen3-coder-next
```

## Parallel Execution Reality Check

**Claim:** "Run 3 models simultaneously with Ollama Cloud Pro"
**Reality:** Ollama Cloud Pro gives 60 RPM globally. Concurrent requests share that pool. When the Hermes agent is already making long-running requests, a background opencode process may timeout or hang.

**Better approach:**
- Use one provider for Hermes (Ollama Cloud) and a different provider for opencode (OpenRouter, OpenCode Zen) to avoid rate-limit contention
- Or: accept sequential execution — opencode for tasks, wait, then return results to Hermes
- Background `opencode run` on cloud models often produces no output (hanging). Interactive terminal usage is more reliable.

## Prompt Engineering for Code Agents

When delegating code generation to opencode, include:
1. Exact file path for output
2. Shebang and imports
3. All function signatures and CLI args
4. The complete workflow/data structure the code must operate on
5. Specific error handling requirements
6. Explicit "Do NOT run the script" if you only want generation

The more precise the prompt, the better the output. Vague prompts ("write a script for ComfyUI") produce vague, incomplete code.

## Credential File Auto-Reject

OpenCode will **always** auto-reject read/write requests on:
- `.env` files
- `auth.json` / tokens
- Any file matching common secret patterns

Plan around this: do credential checks yourself via `terminal`, or use dummy/sample configs for opencode tasks.

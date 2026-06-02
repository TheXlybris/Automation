---
name: opencode
description: "Delegate coding to OpenCode CLI (features, PR review)."
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Coding-Agent, OpenCode, Autonomous, Refactoring, Code-Review]
    related_skills: [claude-code, codex, hermes-agent]
---

# OpenCode CLI

Use [OpenCode](https://opencode.ai) as an autonomous coding worker orchestrated by Hermes terminal/process tools. OpenCode is a provider-agnostic, open-source AI coding agent with a TUI and CLI.

## When to Use

- User explicitly asks to use OpenCode
- You want an external coding agent to implement/refactor/review code
- You need long-running coding sessions with progress checks
- You want parallel task execution in isolated workdirs/worktrees

## Prerequisites

- OpenCode installed: `npm i -g opencode-ai@latest` or `brew install anomalyco/tap/opencode`
- Auth configured: `opencode auth login` or set provider env vars (OPENROUTER_API_KEY, etc.)
- Verify: `opencode auth list` should show at least one provider
- Git repository for code tasks (recommended)
- `pty=true` for interactive TUI sessions

## Binary Resolution (Important)

Shell environments may resolve different OpenCode binaries. If behavior differs between your terminal and Hermes, check:

```
terminal(command="which -a opencode")
terminal(command="opencode --version")
```

If needed, pin an explicit binary path:

```
terminal(command="$HOME/.opencode/bin/opencode run '...'", workdir="~/project", pty=true)
```

### WSL-specific: Windows PATH shadows WSL binary

**Symptom:** `opencode --version` fails with "It seems that your package manager failed to install the right version ..." even though `npm i -g opencode-ai` succeeded inside WSL.

**Root cause:** The user's Windows `%APPDATA%\npm` directory (mounted at `/mnt/c/Users/.../AppData/Roaming/npm`) appears **before** the WSL npm global bin in `$PATH`. The Windows `opencode` wrapper is a `.cmd`/`.ps1` script that cannot run under WSL Linux.

**Actual WSL install location (Hermes bundled Node):** `~/.hermes/node/lib/node_modules/opencode-ai/bin/opencode`.

**Fix:** Create a symlink in a WSL-native PATH directory:
```bash
ln -sf ~/.hermes/node/lib/node_modules/opencode-ai/bin/opencode ~/.local/bin/opencode
```

**Verification:** `opencode --version` should return a version number (e.g., `1.14.46`).

## One-Shot Tasks

Use `opencode run` for bounded, non-interactive tasks:

```
terminal(command="opencode run 'Add retry logic to API calls and update tests'", workdir="~/project")
```

Attach context files with `-f`:

```
terminal(command="opencode run 'Review this config for security issues' -f config.yaml -f .env.example", workdir="~/project")
```

Show model thinking with `--thinking`:

```
terminal(command="opencode run 'Debug why tests fail in CI' --thinking", workdir="~/project")
```

Force a specific model:

```
terminal(command="opencode run 'Refactor auth module' --model openrouter/anthropic/claude-sonnet-4", workdir="~/project")
```

## Model Selection

Default model is often a small 8B parameter model (`rnj-1:8b`). For better results on complex tasks, override with a stronger model.

List available models by provider:
```
terminal(command="opencode models <provider>")
```

Common model flags:
| Flag | Example |
|------|---------|
| `--model ollama-cloud/kimi-k2.6:cloud` | Current Hermes model via Ollama Cloud |
| `--model ollama-cloud/deepseek-v3.2` | DeepSeek v3.2 via Ollama Cloud |
| `--model ollama-cloud/glm-4.7` | GLM-4.7 via Ollama Cloud |

**When to switch models:**
- Simple refactoring or small fixes — default 8B is fine
- Complex architecture review or multi-file refactoring — use kimi-k2.6, deepseek-v3.2, or similar 30B+ model
- Background sessions with API models — expect 30s+ latency per step; use direct terminal work for speed

### WSL with Ollama Cloud provider

When the user has Ollama Cloud configured as provider in `~/.local/share/opencode/auth.json`, all models are cloud-hosted (no local inference).
- The default model is small and fast but weak on reasoning
- Cloud models have network latency — interactive TUI sessions feel sluggish
- Background `opencode run` commands on cloud models may hang or time out due to step-by-step latency
- Prefer local terminal commands when you need speed; use opencode only when you need the agent's autonomy

## Interactive Sessions (Background)

For iterative work requiring multiple exchanges, start the TUI in background:

```
terminal(command="opencode", workdir="~/project", background=true, pty=true)
# Returns session_id

# Send a prompt
process(action="submit", session_id="<id>", data="Implement OAuth refresh flow and add tests")

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send follow-up input
process(action="submit", session_id="<id>", data="Now add error handling for token expiry")

# Exit cleanly — Ctrl+C
process(action="write", session_id="<id>", data="\x03")
# Or just kill the process
process(action="kill", session_id="<id>")
```

**Important:** Do NOT use `/exit` — it is not a valid OpenCode command and will open an agent selector dialog instead. Use Ctrl+C (`\x03`) or `process(action="kill")` to exit.

### TUI Keybindings

| Key | Action |
|-----|--------|
| `Enter` | Submit message (press twice if needed) |
| `Tab` | Switch between agents (build/plan) |
| `Ctrl+P` | Open command palette |
| `Ctrl+X L` | Switch session |
| `Ctrl+X M` | Switch model |
| `Ctrl+X N` | New session |
| `Ctrl+X E` | Open editor |
| `Ctrl+C` | Exit OpenCode |

### Resuming Sessions

After exiting, OpenCode prints a session ID. Resume with:

```
terminal(command="opencode -c", workdir="~/project", background=true, pty=true)  # Continue last session
terminal(command="opencode -s ses_abc123", workdir="~/project", background=true, pty=true)  # Specific session
```

## Common Flags

| Flag | Use |
|------|-----|
| `run 'prompt'` | One-shot execution and exit |
| `--continue` / `-c` | Continue the last OpenCode session |
| `--session <id>` / `-s` | Continue a specific session |
| `--agent <name>` | Choose OpenCode agent (build or plan) |
| `--model provider/model` | Force specific model |
| `--format json` | Machine-readable output/events |
| `--file <path>` / `-f` | Attach file(s) to the message |
| `--thinking` | Show model thinking blocks |
| `--variant <level>` | Reasoning effort (high, max, minimal) |
| `--title <name>` | Name the session |
| `--attach <url>` | Connect to a running opencode server |

## Procedure

1. Verify tool readiness:
   - `terminal(command="opencode --version")`
   - `terminal(command="opencode auth list")`
2. For bounded tasks, use `opencode run '...'` (no pty needed).
3. For iterative tasks, start `opencode` with `background=true, pty=true`.
4. Monitor long tasks with `process(action="poll"|"log")`.
5. If OpenCode asks for input, respond via `process(action="submit", ...)`.
6. Exit with `process(action="write", data="\x03")` or `process(action="kill")`.
7. Summarize file changes, test results, and next steps back to user.

## PR Review Workflow

OpenCode has a built-in PR command:

```
terminal(command="opencode pr 42", workdir="~/project", pty=true)
```

Or review in a temporary clone for isolation:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && opencode run 'Review this PR vs main. Report bugs, security risks, test gaps, and style issues.' -f $(git diff origin/main --name-only | head -20 | tr '\n' ' ')", pty=true)
```

## Parallel Work Pattern

Use separate workdirs/worktrees to avoid collisions:

```
terminal(command="opencode run 'Fix issue #101 and commit'", workdir="/tmp/issue-101", background=true, pty=true)
terminal(command="opencode run 'Add parser regression tests and commit'", workdir="/tmp/issue-102", background=true, pty=true)
process(action="list")
```

## Session & Cost Management

List past sessions:

```
terminal(command="opencode session list")
```

Check token usage and costs:

```
terminal(command="opencode stats")
terminal(command="opencode stats --days 7 --models anthropic/claude-sonnet-4")
```

## Pitfalls

- Interactive `opencode` (TUI) sessions require `pty=true`. The `opencode run` command does NOT need pty.
- `/exit` is NOT a valid command — it opens an agent selector. Use Ctrl+C to exit the TUI.
- PATH mismatch can select the wrong OpenCode binary/model config.
- If OpenCode appears stuck, inspect logs before killing:
  - `process(action="log", session_id="<id>")`
- Avoid sharing one working directory across parallel OpenCode sessions.
- Enter may need to be pressed twice to submit in the TUI (once to finalize text, once to send).

### File Access Limitations (Auto-Reject)

OpenCode auto-rejects permission requests for `.env` files and other credential files (`auth.json`, tokens, keys). Even with explicit `-f` flags, it will refuse to read them. **Never** delegate tasks that must inspect `.env`, config keys, or secrets to opencode — do them yourself or use `terminal` commands directly.

**External directories:** When launched with a `workdir`, opencode auto-rejects glob/read on absolute paths outside that directory. If you need to scan multiple project roots, either:
  - Launch from a common parent directory, or
  - Run multiple `opencode run` instances scoped to each directory, or
  - Use `terminal` commands directly instead.

### Project Scanning / Review Tasks

OpenCode is **NOT reliable** for broad "scan this entire project and report everything" tasks. It tends to:
  - Miss most files (e.g., found 1 of 9 workflows, ignored entire folder trees)
  - Return generic, hallucinated summaries that skip concrete details
  - Stop early when hitting the first auto-reject

**Better approach for project audits:**
  1. Use `terminal` with `find`, `grep`, `wc`, and small Python scripts to inspect the codebase yourself.
  2. Use `opencode run` only for **targeted, bounded tasks** on known files (e.g., "review this specific function for bugs" or "refactor this file").
  3. If you need a multi-file review, enumerate the exact files in the prompt with `-f` flags instead of asking opencode to discover them.

### Background Sessions with Cloud Models — UNRELIABLE

**Problem:** Launching `opencode` via `terminal(background=true)` with cloud models (Ollama Cloud, OpenRouter, etc.) frequently hangs, produces no output, or times out.

**Root cause:** Each step in opencode's agent loop requires a full LLM API call. With cloud models, each call takes 5-30s. In background mode, the process monitor (`process(action="poll")`) may timeout or miss output. The model also may not complete within Hermes' background process timeout (default 120s). Additionally, if Hermes is also using the same Ollama Cloud account, both agents compete for the same rate limit (60 RPM global).

**Session evidence (2026-05-11):**
- `opencode run "Explore ..." --model ollama-cloud/kimi-k2.6:cloud` in background: hung for 30s+, no output, eventually killed
- Same command in foreground terminal: completed in 57s with full results
- `opencode run ...` with default 8B model in background: completed in seconds (local inference is fast)

**Rule:** Never launch opencode with cloud models in `background=true` mode. Instead:
- **For cloud models:** Run opencode in a separate terminal window (WSL or Windows) where the user can monitor it directly
- **For local models:** Background mode works fine because inference is fast (<1s per step)
- **Alternative:** Use `delegate_task` from Hermes with a direct tool call instead of opencode for parallel work

### Code Generation in TUI — File May Not Be Written

**Problem:** When opencode generates code in TUI mode, it often displays the code in the chat but does NOT write it to disk. The user must manually save the file.

**Session evidence (2026-05-11):**
- User asked opencode to generate `run_img2vid.py`; opencode produced code in 16s
- File did not exist on disk — user had to copy-paste and save manually
- When asked to "write it to disk", opencode may fail silently

**Workaround:** Always verify the file exists after opencode claims to have created it. If missing, write it yourself or ask the user to copy-paste from opencode's output.

## Verification

Smoke test:

```
terminal(command="opencode run 'Respond with exactly: OPENCODE_SMOKE_OK'")
```

Success criteria:
- Output includes `OPENCODE_SMOKE_OK`
- Command exits without provider/model errors
- For code tasks: expected files changed and tests pass

## Rules

1. Prefer `opencode run` for one-shot automation — it's simpler and doesn't need pty.
2. Use interactive background mode only when iteration is needed.
3. Always scope OpenCode sessions to a single repo/workdir.
4. For long tasks, provide progress updates from `process` logs.
5. Report concrete outcomes (files changed, tests, remaining risks).
6. Exit interactive sessions with Ctrl+C or kill, never `/exit`.

---
slug: hermes-config
description: Configure, launch, and troubleshoot Hermes Agent — backends, providers, toolsets, web dashboard, web tools, and environment variables.
version: 1.0.2
created: 2026-05-25
updated: 2026-06-01
name: hermes-config
---

# Hermes Agent Configuration

Skill for diagnosing and setting up Hermes Agent tool backends, search providers, and environment variables.

## Config File Location

Primary config: `~/.hermes/config.yaml`
A backup location may exist: `~/hermes_backup/config.yaml`

Always read this file first before making changes to understand current state.

## Web Search & Extract Backends

### Supported Backends
- `firecrawl` — default web backend
- `tavily` — search and extract
- `exa` — search and extract
- `parallel` — extract only

### Key Config Keys
```yaml
web:
  backend: firecrawl          # general web backend
  search_backend: ''           # '' means unset; use 'tavily', 'exa', etc.
  extract_backend: ''         # '' means unset; use 'tavily', 'exa', 'parallel', etc.
```

### Environment Variables by Backend
| Backend | Required Env Var | Fallback / Notes |
|---------|------------------|----------------|
| Tavily  | `TAVILY_API_KEY` | Used for both search and extract |
| Firecrawl | `FIRECRAWL_API_KEY` | Default if search_backend is '' |
| Exa     | `EXA_API_KEY`   | Search + extract |

### Setup Steps for a New Backend (e.g. Tavily)
1. Read current `~/.hermes/config.yaml` to baseline.
2. Ensure env var is exported in the shell (`export TAVILY_API_KEY=tvly-...`).
3. Edit `config.yaml`:
   ```yaml
   web:
     search_backend: tavily
     extract_backend: tavily
   ```
4. Restart Hermes session or run `hermes tools list` to verify `web` toolset status.
5. Test with a `web_search` call to confirm provider is responsive.

### Diagnostics
- `hermes tools list` shows enabled/disabled toolsets and backends.
- Check `~/.hermes/config.yaml` for `providers: {}` and empty `search_backend` / `extract_backend`.
- No `TAVILY*`, `EXA*`, or `FIRECRAWL*` references in config mean env vars are missing.
- Check `~/.hermes/logs/errors.log` for backend plugin load errors (e.g., `register_web_search_provider` missing).

## Web Dashboard

Launching and troubleshooting the Hermes Agent Web Dashboard for managing config, API keys, sessions, cron jobs, skills, and profiles.

### Prerequisites

The dashboard requires `fastapi` and `uvicorn` in the **Hermes pipx venv** (not system Python). The dashboard runs under `~/.local/share/pipx/venvs/hermes-agent/bin/python`, so the packages must exist there.

**Check which Python has the deps:**
```bash
# System Python (may have them, but the dashboard does NOT use this)
python3 -c "import fastapi; import uvicorn; print('system OK')"

# Pipx venv Python (this is what `hermes dashboard` actually uses)
~/.local/share/pipx/venvs/hermes-agent/bin/python -c "import fastapi; import uvicorn; print('venv OK')"
```
Only the venv result matters. If it fails, install directly into the venv.

**Install via pip inside the pipx venv:**
```bash
python3 -c "
import subprocess, os
venv_python = os.path.expanduser('~/.local/share/pipx/venvs/hermes-agent/bin/python')
subprocess.run([venv_python, '-m', 'pip', 'install', 'fastapi', 'uvicorn'], timeout=120)
"
```

### Starting the Dashboard

**Quick start (localhost only):**
```bash
hermes dashboard
```
Opens default browser to http://127.0.0.1:9119 automatically.

**Non-interactive (background):**
```bash
hermes dashboard --no-open --skip-build
```
Recommended for background/in-service usage. If you use `background=true` in a terminal tool, the dashboard will start as a background process. Use `--tui` flag to expose the in-browser Chat tab (embedded hermes TUI via PTY/WebSocket).

**Verify it's running:**
```bash
ss -tlnp | grep 9119   # Linux: check listening port
lsof -i :9119
```

**Access:**
Once running, point browser to **http://127.0.0.1:9119** (or set `--host 0.0.0.0 --insecure` for remote access — DANGEROUS, exposes API keys on network).

**Stop:**
```bash
hermes dashboard --stop
```

### Dashboard Sections

| Section | Purpose |
|---------|---------|
| **SESSIONS** | View and manage conversation sessions |
| **MODELS** | Configure providers and models |
| **LOGS** | Browser Hermes runtime logs |
| **CRON** | Manage scheduled cron jobs |
| **SKILLS** | Browse installed skills |
| **PLUGINS** | Manage plugins |
| **PROFILES** | Switch between config profiles |
| **CONFIG** | Edit config.yaml via web UI |
| **KEYS** | Manage API keys |
| **DOCUMENTATION** | Quick links to docs |

### Troubleshooting

**"Web UI dependencies not installed (need fastapi + uvicorn)"**
1. Confirm the venv python:
   ```
   ~/.local/share/pipx/venvs/hermes-agent/bin/python -c "import fastapi; import uvicorn; print('OK')"
   ```
2. If it fails, install:
   ```
   ~/.local/share/pipx/venvs/hermes-agent/bin/python -m pip install fastapi uvicorn
   ```
3. If already installed but dashboard still errors, the pipx wrapper may need a rebuild:
   ```
   pipx reinstall hermes-agent
   ```

**Dashboard starts but page is blank / 404**
The `web_dist` directory may be missing from the package (rare). Reinstall hermes-agent or check:
```
ls ~/.local/share/pipx/venvs/hermes-agent/lib/python*/site-packages/hermes_cli/web_dist/
```

**Port already in use**
Change port:
```bash
hermes dashboard --port 9120
```

**Process hangs without starting**
Use background mode with proper health check:
```bash
hermes dashboard --no-open --skip-build &
sleep 2
curl -s http://127.0.0.1:9119 | head -5
```

### Dashboard Pitfalls
1. **Pipx venv deps ≠ system deps**: `fastapi` may import in system Python but be missing from the pipx venv. Always install into the venv Python.
2. **Long-lived process detection in terminal tool**: Running `hermes dashboard` via the `terminal()` tool in non-interactive mode may return an error about "long-lived server process". Use `pty=true` with a regular shell, or run from an actual terminal outside Hermes.
3. **Frontend assets**: The dashboard uses prebuilt assets at `~/.local/share/pipx/venvs/hermes-agent/lib/python3.12/site-packages/hermes_cli/web_dist/`. If this folder is missing, use `--skip-build` (the full build requires npm and a `web/` source folder that may not be present in the pipx package).
4. **Pipx inject blocked**: Tools like `pipx inject`, `pipx runpip`, and direct `pip install` in the `terminal()` tool may be blocked by the "long-lived server/watch process" heuristic (exit code -1). Use `execute_code` with `subprocess.run([venv_python, '-m', 'pip', ...])` instead.

## Web Search Fallback via Browser
A known bug (hermes-agent #31918) can cause `web_search` and `web_extract` to report "No provider configured" even when `search_backend` is set correctly and env vars are exported. Affects tavily, exa, firecrawl, searxng, brave-free, ddgs.

### Detection
- `hermes tools list` shows `web: enabled`
- `web_search` returns "No web search provider configured"
- `hermes status` shows the API key as present
- Direct API call to the provider (e.g., Tavily) succeeds
- Browser-based navigation (`browser_navigate`) works fine

### Workaround
Use `browser_navigate` to search engines (Google, DuckDuckGo, Bing) and extract results from the rendered page. This bypasses the plugin registration layer entirely. The user explicitly confirmed this workaround: when they say "pesquisa online", use `browser_navigate`.

### Fix (when available)
The bug is caused by `PluginContext.register_web_search_provider` being unavailable during plugin load, preventing web backend plugins from registering. Monitor [GitHub issue #31918](https://github.com/NousResearch/hermes-agent/issues/31918) for patch status.

## Web Tools Troubleshooting

### Core Principle: Verify Before Asserting

When a user says "bug X is supposedly fixed" or asks about tool status, **always verify live** (GitHub issues/PRs, local tool test) rather than relying on memory or assumptions. Bug status changes; merged PRs often fix *different* bugs than the one the user cares about.

### Verification Workflow

1. **Check the Issue directly** — Navigate to `https://github.com/nousresearch/hermes-agent/issues/<number>` and confirm status (Open / Closed).
2. **Search PRs by issue number** — Use `https://github.com/nousresearch/hermes-agent/pulls?q=is:pr+<number>` to find PRs that claim to fix it.
3. **Read merged PR descriptions carefully** — A merged PR may fix a *related* bug with a different root cause. Check which issue numbers it explicitly says "Fixes".
4. **Distinguish root causes** — Two bugs can have the same symptom ("web_search doesn't work") but different causes (plugin discovery timing vs missing API on PluginContext).

### Known Bugs & Workarounds

#### Bug #31918 — `PluginContext` missing `register_web_search_provider`

- **Status:** Still OPEN (verify on GitHub before assuming change).
- **Symptom:** All web-search plugins (`web-tavily`, `web-exa`, `web-firecrawl`, `web-parallel`, `web-searxng`, `web-brave-free`, `web-ddgs`) fail to load with:
  ```
  Failed to load plugin 'web-tavily': 'PluginContext' object has no attribute 'register_web_search_provider'
  ```
- **Impact:** `web_search` tool returns:
  ```
  "No web search provider configured. Run `hermes tools` to set one up."
  ```
- **Workaround:** Use `browser_navigate` to a search engine (Google, Bing, DuckDuckGo) as a fallback for web queries. This has been confirmed working.
- **Important:** Do NOT tell the user `web_search` is permanently broken or that browser tools are the "only" way — frame it as a temporary workaround pending the fix.

#### Bug #27580 / #27584 — Plugin Discovery Timing (FIXED by PR #34563)

- **Status:** Resolved (merged ~2 days before 31 May 2026).
- **Symptom:** `web_search` / `web_extract` return "No provider configured" even with correct config and API keys, specifically in cold contexts (subprocess agents, delegate children, standalone scripts).
- **Root cause:** Registry only populated as side effect of importing `model_tools.py`. From a cold context the registry was empty.
- **Fix:** PR #34563 added `_ensure_web_plugins_loaded()` in `tools/web_tools.py` before registry lookups.
- **Lesson:** If the user says "it works sometimes but not from subagents/delegate," this was likely #27580 (fixed). If it *never* works even in the main agent process, it's likely #31918 (still open).

### Tool Fallback Hierarchy

When web tooling is impaired, prefer in this order:

1. `web_search` / `web_extract` — fastest when working.
2. `browser_navigate` to a search engine + `browser_snapshot` / `browser_vision` — reliable fallback.
3. `web_extract` with direct URLs — for content extraction when search is broken.

## Browser / Vision Backends
- `browser.engine`: `auto`, `playwright`
- `browser.cloud_provider`: `local` or remote CDP URL
- `browser.camofox.*` — managed stealth session settings

## General Provider Model
- `providers: {}` — custom OpenAI-compatible endpoints go here with `base_url` and `key_env`.
- `fallback_providers: []` — automatic failover list for rate limits and outages.

## Pitfalls
1. **Interactive-only commands**: `hermes tools` (no subcommand) requires an interactive TTY and fails in non-interactive subprocesses. Use `hermes tools list` instead.
2. **Empty backends vs default**: `search_backend: ''` does NOT fall back to `backend`; it means disabled. You must explicitly set a value.
3. **Env vars not persisted**: `export` in a terminal tool lasts only that subprocess. Add to shell rc (`.bashrc`, `.zshrc`) for permanence.
4. **Web extract also needs backend**: `web_extract` fails with "No web extract provider configured" if `extract_backend` is empty.
5. **Silent backend initialization failure**: If `search_backend` is set correctly, the env var is exported, `hermes tools list` shows `web` as enabled, but `web_search` still returns "No web search provider configured" during a session, the web module likely failed to initialize at startup but is still shown as enabled. Workaround: use `browser_navigate` to a search engine and extract results directly. Fix: restart the Hermes session (fresh process) to force re-initialization of web backends.
6. **No provider directories under `~/.hermes/`**: Backend credentials live purely in env vars and `config.yaml`; there is no per-provider config directory.

## References
- `references/web-backends.md` — detailed notes on each supported backend, rate limits, and known quirks.
- `references/bug-31918-web-tavily-registration.md` — reproduction recipe, diagnosis steps, and browser-based workaround for the web plugin registration bug.
- `references/bug-31918-web-search-provider.md` — session research on the open bug, related PRs, and distinction between #31918 and #27580.
- `references/pipx-venv-deps.md` — pitfall: system Python deps ≠ pipx venv deps, and how to fix it (general).
- `references/pipx-venv-deps-dashboard.md` — dashboard-specific application of the pipx venv dependency pitfall.

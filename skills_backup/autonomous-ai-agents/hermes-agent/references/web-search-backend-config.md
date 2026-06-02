# Hermes Agent Web Search Backend Configuration

## Overview

Hermes Agent supports multiple web search/extraction backends: **Tavily**, **Firecrawl**, **Exa**, **Parallel**, and local/self-hosted variants. The backend choice is stored in `~/.hermes/config.yaml` under the `web:` section.

## Configuration Keys

| Key | Purpose | Valid Values |
|-----|---------|-------------|
| `web.backend` | Primary web backend for search + extract | `tavily`, `firecrawl`, `exa`, `parallel` |
| `web.search_backend` | Explicit search provider (overrides `backend` for search) | `tavily`, `firecrawl`, `exa`, `parallel` |
| `web.extract_backend` | Explicit extraction provider (overrides `backend` for extract) | `tavily`, `firecrawl`, `exa`, `parallel` |
| `web.use_gateway` | Route web calls through the gateway instead of direct | `true`, `false` |

## Environment Variables

Each backend requires its corresponding API key in `~/.hermes/.env`:

| Backend | Env Var | Source |
|---------|---------|--------|
| Tavily | `TAVILY_API_KEY` | https://app.tavily.com/home |
| Firecrawl | `FIRECRAWL_API_KEY` | https://firecrawl.dev/ |
| Exa | `EXA_API_KEY` | https://exa.ai |
| Parallel | `PARALLEL_API_KEY` | https://parallel.ai |

For self-hosted Firecrawl, also set `FIRECRAWL_API_URL`.

## Common Workflow

### Switching to Tavily (recommended for most users)

```bash
# CLI commands
hermes config set web.backend tavily
hermes config set web.search_backend tavily
hermes config set web.extract_backend tavily
```

Or edit `~/.hermes/config.yaml` directly:
```yaml
web:
  backend: tavily
  search_backend: tavily
  extract_backend: tavily
  use_gateway: false
```

Then add to `~/.hermes/.env`:
```
TAVILY_API_KEY=tvly-your-key-here
```

### Important: Full Process Restart Required

After modifying `config.yaml` or `.env` for web backends, a **full process restart** is required. Config is snapshotted at session startup, and **environment variables from `.env` are loaded once when the process starts** — mid-session changes to `config.yaml` or `.env` are NOT picked up by `/reset`.

| Action | What it does | Environment vars reloaded? |
|--------|-------------|---------------------------|
| `/reset` in chat | Clears conversation history, keeps model/tools config | ❌ No |
| `/exit` then `hermes chat` | Exits TUI completely, starts new process | ✅ Yes (only if the new `hermes chat` process was started from a shell that had the `.env` vars exported) |
| `source ~/.hermes/.env` + new shell | Loads .env into the shell, then launches `hermes chat` | ✅ Yes, reliable |
| `systemctl --user restart hermes-gateway` | Restarts the gateway service with new env vars (for Telegram/Discord) | ✅ Yes |

**Pitfall:** Even after doing `/exit` and `hermes chat`, if the new shell session (e.g. a new SSH window or a new `tmux` pane) did not export the `.env` variables, the TUI process never sees them. The safest fix is to add `source ~/.hermes/.env` to `~/.bashrc`, or to prepend `source ~/.hermes/.env && ` before every `hermes chat` invocation.

If `web_search` returns:
> `No web search provider configured. Run 'hermes tools' to set one up.`

...even after configuration, the cause is usually one of:
1. **Only did `/reset` without exiting** — environment variables (API keys) are still from the old `.env`
2. `backend` points to a provider whose API key is missing (e.g., `backend: firecrawl` but only `TAVILY_API_KEY` is set)
3. `hermes tools` was run and silently reset `backend` to `firecrawl` (it only shows Firecrawl in the UI if Tavily is not the active provider)

### The `hermes tools` UI Trap

Running `hermes tools` (interactive tool configuration) often shows only **Firecrawl Self-Hosted** as the web backend option. This is because the UI presents the currently selected backend as the only option. If Tavily is not currently selected, it won't appear.

**Fix:** Set the backend via CLI instead:
```bash
hermes config set web.backend tavily
hermes config set web.search_backend tavily
```

## Debugging

Enable debug logging in `~/.hermes/.env`:
```
WEB_TOOLS_DEBUG=true
```

This surfaces HTTP bodies, response codes, and provider selection decisions in the logs.

## Backend Comparison

| Backend | Free Tier | Speed | Coverage | Notes |
|---------|-----------|-------|----------|-------|
| Tavily | Yes (1,000 calls/month) | Fast | Broad | Recommended default |
| Firecrawl | Self-hosted | Depends | Good | Requires self-hosted instance |
| Exa | Limited | Fast | AI-native | Semantic search focus |
| Parallel | Limited | Fast | Good | Unified API for multiple sources |

## Pitfalls

1. **Config/backend mismatch:** If `backend: firecrawl` but only `TAVILY_API_KEY` is present in `.env`, web search silently fails with "No provider configured."
2. **`hermes tools` reposts backend:** Running the interactive tool configurator can silently revert `backend` to `firecrawl` if that was the last selected option.
3. **Session not reset:** Always `/reset` after changing web backend settings.
4. **Node.js not related:** Browser automation requires Node.js, but web search (Tavily/Firecrawl/Exa) works via HTTP API — Node.js is irrelevant for search functionality.
5. **Gateway systemd service without `EnvironmentFile`:** If the gateway runs as `systemctl --user`, add `EnvironmentFile=%h/.hermes/.env` to the `[Service]` section. Without it, `.env` variables (including `TAVILY_API_KEY`) are NOT loaded, and web_search returns "No provider configured" even though the key exists.

## Verification

After configuration and `/reset`:
```python
# test web_search
web_search(query="test connection", limit=1)
```

Expected: results with titles/URLs, not an error about missing provider.

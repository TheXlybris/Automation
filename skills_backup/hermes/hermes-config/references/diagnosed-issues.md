# Diagnosed Configuration Issues

## Issue: Silent Web Backend Initialization Failure

**Symptom:**
- `web_search` and `web_extract` return "No web search provider configured" despite:
  - `~/.hermes/config.yaml` having `search_backend: tavily` and `extract_backend: tavily`
  - `TAVILY_API_KEY` correctly exported in the environment
  - `hermes tools list` shows `web` as ✓ enabled
- Meanwhile, `browser_navigate` works normally.

**Diagnosis:**
The web backend module fails to initialize during Hermes startup but the toolset is still marked as enabled in the registry. This is a runtime initialization bug where the backend is registered but not instantiated.

**Workaround:**
Use the browser tool to perform web searches directly:
1. `browser_navigate` to a search engine URL (e.g., `https://duckduckgo.com/html/?q=...`)
2. Use `browser_snapshot` or `browser_vision` to extract search results.

**Fix:**
Restart the Hermes session with a fresh process (`hermes restart` or kill/restart the CLI) so the web backend module is re-initialized from scratch.

**Verification after fix:**
Run `web_search` with a test query — success means the backend was properly instantiated.

# Bug #31918 — Session Research (31 May 2026)

## Issue
- **GitHub:** https://github.com/nousresearch/hermes-agent/issues/31918
- **Status:** OPEN (verified live on 2026-05-31).
- **Title:** `[BUG] web-tavily plugin fails to register: PluginContext missing register_web_search_provider`
- **Opened by:** Gawainexiaoxiang ~1 week ago.

## Error
```
Failed to load plugin 'web-tavily': 'PluginContext' object has no attribute 'register_web_search_provider'
```

All web-search plugins affected:
- `web-tavily`, `web-exa`, `web-firecrawl`, `web-parallel`, `web-searxng`, `web-brave-free`, `web-ddgs`.

## User Impact
`web_search` tool returns:
```
"No web search provider configured. Run `hermes tools` to set one up."
```

## No PR Directly Fixing #31918
Search `is:pr 31918` on the repo returns **0 results** (Open or Closed).

## Related But Distinct Fix
- **PR #34563** — `fix(web): ensure plugin discovery before web_*_tool registry lookups`
  - Merged 2 days ago by teknium1.
  - Fixes issues **#27580** and **#27584**.
  - NOT the same as #31918.
  - Fixes a *timing/discovery* problem: registry empty in cold contexts because plugin discovery only happened as a side effect of importing `model_tools.py`.
  - Solution: `_ensure_web_plugins_loaded()` called before registry lookups.

## Distinction Table

| Bug | Root Cause | Symptom | Status |
|-----|-----------|---------|--------|
| #31918 | `PluginContext` API mismatch — method `register_web_search_provider` missing at runtime | All web plugins fail to load, even in main process | **OPEN** |
| #27580/#27584 | Plugin discovery timing — registry not populated in cold contexts (subprocess, delegate) | "No provider configured" only from subagents/standalone scripts | **FIXED** by #34563 |

## Workaround
Use `browser_navigate` to a search engine as fallback. Verified working.

## Next Verification Trigger
If user says "bug 31918 is supposedly fixed," repeat the live check:
1. GitHub issue status.
2. PR search for `is:pr 31918`.
3. Confirm merged PRs don't conflate with different issue numbers.

# Bug #31918: web-tavily Plugin Registration Failure

**Date**: 2026-05-25
**Status**: Open (hermes-agent #31918)
**Affected backends**: tavily, exa, firecrawl, searxng, brave-free, ddgs

## Symptoms
- `hermes tools list` shows `web: enabled`
- `web_search` returns: "No web search provider configured"
- `web_extract` returns: "No web extract provider configured"
- `hermes status` shows API key present
- Direct provider API call succeeds (e.g., Tavily returns HTTP 200)
- `browser_navigate` works perfectly
- Browser tool also works
- Backend tool non-functional

## Root Cause
`PluginContext.register_web_search_provider` missing during plugin load:
```
Failed to load plugin 'web-tavily': 'PluginContext' object has no attribute 'register_web_search_provider'
```

## Diagnosis Steps
1. Check env var: `echo $TAVILY_API_KEY`
2. Check config: `cat ~/.hermes/config.yaml | grep search_backend`
3. Test API directly: `python3 -c "import requests; requests.post('https://api.tavily.com/search', json={'query':'test','api_key':'...','search_depth':'basic'})"`
4. Check logs: `tail ~/.hermes/logs/errors.log | grep web-tavily`

## Workaround (Confirmed by User)
When user says "pesquisa online" or any web search request, use `browser_navigate` to a search engine (Google, DuckDuckGo, Bing) and extract results from the rendered page. Bypasses the plugin layer entirely.

## Fix
Monitor [GitHub issue #31918](https://github.com/NousResearch/hermes-agent/issues/31918) for patch.

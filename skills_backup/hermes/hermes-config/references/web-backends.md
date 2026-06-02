# Web Backends Reference

Quick lookup for supported web search/extract backends in Hermes.

## Tavily (tavily)
- **Env var:** `TAVILY_API_KEY=tvly-...`
- **Supports:** search, extract
- **Rate limits:** varies by plan; free tier exists
- **Config:**
  ```yaml
  web:
    search_backend: tavily
    extract_backend: tavily
  ```
- **Notes:** Good NLP search. Use for general knowledge queries. Does not support `answer` param in all regions.

## Firecrawl (firecrawl)
- **Env var:** `FIRECRAWL_API_KEY`
- **Supports:** extract (default `web.backend`)
- **Notes:** Scrapes and returns clean markdown. Default for `web_extract` if no backend is set.

## Exa (exa)
- **Env var:** `EXA_API_KEY`
- **Supports:** search, extract
- **Notes:** Semantic search over web. Good for technical/research queries.

## Parallel (parallel)
- **Supports:** extract only
- **Notes:** Aggregates multiple extractors in parallel.

## Diagnostics
- `hermes tools list` shows if `web` is enabled.
- If search returns "No web search provider configured", read `config.yaml` — `search_backend` is empty.
- `web_extract` returning "No web extract provider configured" means `extract_backend` is empty.

## Quick Fix Recipe (Tavily)
1. `export TAVILY_API_KEY=<key>`
2. Patch `~/.hermes/config.yaml`:
   ```yaml
   web:
     search_backend: tavily
     extract_backend: tavily
   ```
3. Run `hermes tools list` to confirm `web` is enabled.
4. Test with `web_search`.

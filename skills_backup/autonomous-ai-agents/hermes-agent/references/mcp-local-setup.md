# mem0-open-mcp: Local Setup with Ollama + Qdrant

> TL;DR: Configure mem0-open-mcp to run 100% local using Ollama for LLM/embeddings and self-hosted Qdrant.

## Known-good config (YAML)

```yaml
server:
  host: 0.0.0.0
  port: 8765
  user_id: default
  reload: false
  log_level: info
  performance_logging: false

llm:
  provider: ollama
  config:
    model: qwen2.5-coder:7b
    temperature: 0.1
    max_tokens: 2000

embedder:
  provider: ollama
  config:
    model: nomic-embed-text:latest
    embedding_dims: 768

vector_store:
  provider: qdrant
  config:
    collection_name: mem0_memories
    host: localhost
    port: 6333
    embedding_model_dims: 768
    extra: {}

openmemory: {}
custom_prompts: {}
```

Save to `~/.mem0-open-mcp/mem0-open-mcp.yaml`.

## Best models for this setup

| Role | Model | Why |
|------|-------|-----|
| LLM | `qwen2.5-coder:7b` | Capable, small enough for 16GB VRAM, good instruction following |
| Embedder | `nomic-embed-text:latest` | 768-dim embeddings, purpose-built for text search, 274MB |
| Avoid | `mxbai-embed-large` | Larger (669MB), no significant benefit for this use case |

## Hermes MCP registration

```bash
hermes mcp add mem0 --command mem0-open-mcp --args stdio
```

Then in a Hermes session: `/reload-mcp`

## Critical bug (2026-05-10): mem0ai v2 broke mem0-open-mcp

**Symptom:** All mem0 tools return `Error: Memory system is currently unavailable. Please try again later.`
**Root cause:** `mem0ai` v2.0.2 changed `AsyncMemory.from_config()` from async to sync. `mem0-open-mcp` v0.2.12 still does `await AsyncMemory.from_config(config)`, which raises `TypeError: object AsyncMemory can't be used in 'await' expression`.

**Detection:**
```bash
mem0-open-mcp test
# LLM + Embedder + Vector Store all pass, but "Memory test failed: ... AsyncMemory can't be used in 'await'"
```

**Workarounds (in order of preference):**

1. **Patch server.py locally** (fastest, 2-line change):
   Edit `mem0_server/server.py` inside the pipx venv. Replace:
   ```python
   self._memory_client = await AsyncMemory.from_config(mem0_config)
   ```
   with:
   ```python
   self._memory_client = AsyncMemory.from_config(mem0_config)
   ```
   (there are 2 occurrences). Then restart Hermes session.

2. **Downgrade mem0ai** inside the pipx venv to last v1.x known-compatible.

3. **Wait for upstream fix** in mem0-open-mcp.

## Pitfalls

- Config file must be named `mem0-open-mcp.yaml` and placed in `~/.mem0-open-mcp/`. `~/.local/config.yaml` or `~/.mem0/` are NOT read by the loader.
- If switching from OpenAI to Ollama, **delete the Qdrant collection first** (it stores vectors with wrong dimensions otherwise).
- `embedding_model_dims` must match the embedder output dimension exactly: `768` for nomic-embed-text, `1536` for OpenAI.
- `mem0-open-mcp configure` writes its output to a **different filename** than the loader searches; use the exact path `/home/xlybris/.mem0-open-mcp/mem0-open-mcp.yaml`.

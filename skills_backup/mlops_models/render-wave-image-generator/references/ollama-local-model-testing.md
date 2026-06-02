# Ollama Local Model Quick-Test via curl

Use `/api/chat` (not `/api/generate`) for chat-completion models with templates.

```bash
# Test if a model loads and responds
curl -s -X POST http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:8b", "messages": [{"role":"user","content":"Count 1 to 3."}], "stream": false, "options": {"num_predict": 20}}'
```

## Key Response Fields
- `load_duration` — time to load weights into RAM/VRAM (dominates first call)
- `eval_duration` — actual generation time per token
- `done_reason`:
  - `"stop"` — normal completion
  - `"length"` — hit token limit; may indicate empty/broken output

## Common Failures
- `model requires more system memory (X GiB) than is available (Y GiB)` — model won't fit in system RAM at all
- `done_reason: length` with empty `content` — wrong template/chat format for that model; test with `/api/chat` instead of `/api/generate`

## Memory Benchmarks (observed)
- qwen3.5:35b-a3b → needs ~18GB system RAM → fails on 16GB
- gemma4:26b → loads after ~39s, uses ~10–12GB VRAM after load
- qwen3:8b → loads after ~17s, fits in 16GB VRAM

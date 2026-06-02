# Custom Tools Migration: Tools Repo → Plugins Directory

Data: 2026-05-18

Contexto: THE RENDER WAVE criou duas tools personalizadas (MOAO e VAO) que originalmente foram colocadas em `~/.hermes/hermes-agent/tools/`. Apos um `hermes update` (que faz `git pull` no repo), essas tools foram silenciosamente apagadas. A migracao para plugins corrigiu isto.

## A Regra

Codigo personalizado NUNCA deve ir para `~/.hermes/hermes-agent/` — e um repo Git que e apagado/actualizado por `hermes update`. Sempre para:
- Skills (texto): `~/.hermes/skills/`
- Tools Python: `~/.hermes/plugins/` (discoverable, persistente, dynamic load)

## Estado Actual (2026-05-18)

| Tool | Estado | Localizacao permanente |
|------|--------|------------------------|
| video_analyze_ollama (VAO) | Em plugins (criado 2026-05-18) | `~/.hermes/plugins/video_analyze_ollama/` |
| mixture_of_agents_ollama (MOAO) | Migrado hoje para plugins | `~/.hermes/plugins/mixture_of_agents_ollama/` |

## Estrutura de um Plugin de Tool

```
~/.hermes/plugins/<nome>/
├── plugin.yaml       # Nome, descricao, toolset, entry_point
└── __init__.py       # Codigo + funcao register(ctx)
```

### plugin.yaml (exemplo MOAO)

```yaml
name: mixture_of_agents_ollama
description: "MOAO: orquestra multiplos modelos Ollama..."
version: "1.0.0"
author: UmbralForge
enabled: true
toolsets:
  - moa
entry_point: __init__:register
```

### __init__.py — Funcoes principais (MOAO)

- `_resolve_mode()`: auto-detecta local vs cloud via curl /api/tags
- `_resolve_models()`: devolve (reference_models, aggregator_model)
- `_ollama_chat()`: helper POST /api/chat com retry
- `_run_reference()`: Layer 1 — uma referencia por modelo
- `_run_aggregator()`: Layer 2 — sintetiza referencias em resposta final
- `moao_handler()`: entrypoint principal — sequencial para VRAM safety
- `register(ctx)`: regista tool no Hermes via ctx.register_tool()

### __init__.py — Funcoes principais (VAO)

- `_resolve_model()`: detecta modelos de visao local ou cloud
- `_extract_frames()`: ffmpeg -ss timestamp -i video -frames:v 1 → base64
- `_call_ollama_chat()`: envia array `images[]` para Ollama /api/chat
- `video_analyze_ollama_handler()`: entrypoint
- `register(ctx)`: regista tool no Hermes via ctx.register_tool()

## Configuracao por Env Vars

| Tool | Variavel | Default |
|------|----------|---------|
| MOAO | `MOAO_MODE` | `auto` (local|cloud|auto) |
| MOAO | `MOAO_MODEL` | `""` (override aggregator) |
| VAO | `VAO_MODE` | `auto` |
| VAO | `VAO_MODEL` | `""` |
| VAO | `VAO_FPS` | `1.0` |
| VAO | `VAO_MAX_FRAMES` | `30` |
| Ambas | `OLLAMA_HOST` | `http://localhost:11434` |
| Cloud | `OLLAMA_API_KEY` | `""` |

## Modelos suportados (confirmados no Ollama local)

| Modelo | Uso | VRAM aprox |
|--------|-----|------------|
| qwen3:8b | MOAO ref + aggregator | ~5 GB |
| gemma4:e2b | MOAO ref | ~7 GB |
| llama3.1:8b | MOAO ref | ~5 GB |
| qwen3-vl:30b-a3b-instruct | VAO (vision local) | ~18 GB |
| qwen3-vl:235b-cloud | VAO (vision cloud) | Cloud |
| qwen3.5:35b-a3b | MOAO aggregator cloud | Cloud |
| kimi-k2.6:cloud | MOAO aggregator cloud | Cloud |

Nota: MOAO local requer execucao sequencial para caber em 16 GB VRAM. Layer 1 corre 3x em serie, depois Layer 2 corre 1x.

## Pitfall — `hermes update` apaga tudo em `hermes-agent/tools/`

O repo `~/.hermes/hermes-agent/` e um clone Git. `hermes update` = `git pull --ff-only` + reinicio. Qualquer ficheiro `.py` criado manualmente em `tools/` desaparece sem aviso.

Verificacao: `ls ~/.hermes/hermes-agent/tools/mixture_of_agents_ollama.py`
Resultado apos update: NOT FOUND.

Ja `ls ~/.hermes/plugins/mixture_of_agents_ollama/__init__.py` -> persistente para sempre.

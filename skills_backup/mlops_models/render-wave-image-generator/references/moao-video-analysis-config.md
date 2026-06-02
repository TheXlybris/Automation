# MOAO e Video Analysis — Configuração para THE RENDER WAVE

Data: 2026-05-12

---

## 1. Mixture of Agents Ollama (MOAO) — Agregador kimi-k2.6:cloud

### O que mudou
O agregador padrão em cloud mode foi alterado de `qwen3.5:35b-a3b` para `kimi-k2.6:cloud`.

**Ficheiro:** `~/.hermes/hermes-agent/tools/mixture_of_agents_ollama.py` (linha 63)

```python
# Antes:
AGGREGATOR_MODEL_CLOUD = "qwen3.5:35b-a3b"

# Depois:
AGGREGATOR_MODEL_CLOUD = "kimi-k2.6:cloud"
```

### Configuração atual
| Função | Modelo | Modo |
|---|---|---|
| Ref 1 | qwen3.5:35b-a3b | Cloud (Ollama Cloud Pro — 60 RPM) |
| Ref 2 | gemma4:26b | Cloud |
| Ref 3 | kimi-k2.6:cloud | Cloud |
| **Agregador** | **kimi-k2.6:cloud** | **Cloud** |

### Ativação
```bash
export MOAO_MODE=cloud
hermes tools enable moa
```

### Uso no Hermes
```
→ Invocar: /moa <pergunta complexa>
→ Ou: mixture_of_agents_ollama(user_prompt="...")
```

### Como o MOAO ajuda THE RENDER WAVE
- **Prompt engineering:** 3 modelos a refinar prompts de imagem/video = prompts mais precisos
- **Análise de vídeo:** Múltiplas perspetivas sobre o mesmo clip (fluidez, cor, composição)
- **Metadados YouTube:** Títulos/descrições/tags optimizados por consenso
- **Thumbnail concepts:** Ideias visuais validadas por múltiplos "críticos"
- **Debugging:** Quando um modelo dá uma resposta errada, os outros corrigem

---

## 2. Video Analysis — Limitações do Ollama

### O problema
A tool `video_analyze` do Hermes foi desenhada para **Gemini via OpenRouter**. Usa o formato OpenAI multimodal com campo `video_url` (tipo "video_url"):
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "prompt"},
    {"type": "video_url", "video_url": {"url": "data:video/mp4;base64,..."}}
  ]
}
```

**O Ollama API NÃO suporta `video_url`** — só suporta `image_url` (imagens estáticas).

### Modelos disponíveis e capabilities

| Modelo | Capacidade Ollama | Vision (imagens) | Video (ficheiros) | Tamanho |
|---|---|---|---|---|
| qwen3-vl:30b-a3b-instruct | `vision` | ✅ | ❌ (via Ollama API) | 19 GB |
| qwen3-vl:235b-cloud | `vision` | ✅ | ❓ (cloud, não testado) | Cloud |
| kimi-k2.6:cloud | `vision` | ✅ | ❓ | Cloud |
| qwen3.5:35b-a3b | `vision` | ✅ | ❌ | Cloud (23 GB) |
| gemma4:e2b | `vision` | ✅ | ❌ (só imagens) | 7.2 GB |
| gemma4:26b | `vision` | ✅ | ❌ (só imagens) | 17 GB |

**Nota:** A capability "vision" no Ollama refere-se a **análise de imagens**, não de vídeo.

### Opções para análise de vídeo com THE RENDER WAVE

| Opção | Descrição | Vantagens | Desvantagens |
|---|---|---|---|
| **A — Frames + vision_analyze** | Extrair frames com ffmpeg, usar `vision_analyze` em cada frame | Totalmente local, grátis, usa modelos que já tens | Perde coerência temporal entre frames |
| **B — OpenRouter Gemini** | `video_analyze` funciona nativamente | Suporta vídeo real, coerência temporal | Requer créditos OpenRouter (não é gratuito ilimitado) |
| **C — qwen3-vl via API directa** | Tentar chamada directa à API de chat do Ollama com vídeo base64 | Potencialmente grátis | Não confirmado que funcione; Ollama API docs não mencionam vídeo |

### Recomendação para produção
**Opção A (frames + vision_analyze)** é a mais viável para o pipeline local:

```bash
# Extrair 1 frame por segundo
ffmpeg -i input.mp4 -vf "fps=1,scale=768:-1" -q:v 2 /tmp/frames/frame_%03d.jpg

# Analisar key frames (início, meio, fim)
# Usar vision_analyze nos frames mais representativos
```

Para análise qualitativa profissional de clips (coerência temporal, fluidez de movimento), usar a **Opção B (OpenRouter Gemini)** como ferramenta complementar, não como pipeline principal.

---

## 3. Configuração do Auxiliary Vision para Ollama Cloud

Para usar `vision_analyze` com Ollama Cloud:

**`~/.hermes/.env`:**
```bash
OLLAMA_API_KEY=sk-...
OLLAMA_BASE_URL=https://ollama.com/v1
```

**`~/.hermes/config.yaml` (auxiliary.vision):**
```yaml
auxiliary:
  vision:
    provider: auto   # ou "custom" com base_url explícito
    model: ''        # deixar vazio para auto-detect
    base_url: ''
    api_key: ''
    timeout: 120
```

**Modelo vision recomendado para Ollama Cloud:**
- `qwen3-vl:30b-a3b-instruct` (mais capaz, 19GB)
- `gemma4:26b` (equilibrado, 17GB)
- `qwen3.5:35b-a3b` (já usado, vision ok)

---

## 4. Ativar toolsets no Hermes

```bash
# MOAO (já criado como tool custom)
hermes tools enable moa

# Video analysis (necessita de modelo multimodal)
hermes tools enable video

# Vision analysis (imagens)
hermes tools enable vision
```

**Nota:** Após qualquer `hermes tools enable/disable`, fazer `/reset` na sessão do Hermes para recarregar.

---

## 5. Verificar capabilities de modelos Ollama

```bash
ollama list | while read name id size rest; do
  [ -z "$name" ] || [ "$name" = "NAME" ] && continue
  echo "=== $name ==="
  ollama show "$name" 2>/dev/null | grep -i "capabilities\|vision" | head -5
done
```

Output esperado para modelos vision-capable:
```
  Capabilities
    vision
```

---

## 6. Pitfall — "Procede?" antes de avançar

Nunca tentar ativar/configurar video analysis sem confirmar com o utilizador primeiro, especialmente quando envolve:
- Download de modelos grandes (>5GB)
- Configuração de API keys pagas
- Alteração de ficheiros de configuração do Hermes

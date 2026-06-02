# FramePack First Run Diagnostics

## Resumo do primeiro vídeo gerado pelo utilizador (2026-05-09)

**Ficheiro:** `D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\output\FramePack_00001.mp4`

**Especificações:**
| Propriedade | Valor | Esperado | Estado |
|-------------|-------|----------|--------|
| Resolução | 480×512 | 1024×576 (16:9) | ❌ Errado — ImageResize+ força 512×512 |
| Frames | 145 | — | ✅ Ok |
| Duração | 4.83s | ~5s (total_second_length=5.0) | ✅ Correspondente |
| FPS | 30 | 30 | ✅ Fixo do FramePack |
| Codec | H.264 | — | ✅ MP4 standard |
| Tamanho | ~1.1MB | — | ✅ Ok para preview |

**Qualidade visual (análise de frames):**
- **Cena:** Paisagem com rio, prado, flores silvestres, colinas, céu com nuvens
- **Coerência temporal:** ✅ Sem temporal drift — a cena mantém-se estável ao longo dos frames
- **Movimento:** ✅ Movimento ambiente visível (ondulação na água, luz dourada)
- **Composição:** ✅ Consistente entre frames — nada desaparece ou muda de sítio

**Setup no workflow:**
- 1 imagem no Start (LoadImage)
- **Mesma imagem no End** (LoadImage) — isto reduz o movimento porque o modelo interpola entre duas imagens idênticas
- `total_second_length` = 5.0 segundos

## Diagnóstico do problema de resolução

O ffprobe reportou **480×512** em vez de 16:9. Isto indica que:
1. Os nodes `ImageResize+` (nodes 59 e 50) no workflow exemplo **forçaram a imagem para 512×512**
2. O `FramePackFindNearestBucket` (node 51) com valor **640** não conseguiu anular o resize — FramePack gerou na resolução que recebeu do VAEEncode, que já estava em 512×512 (ou próximo)
3. A proporção 480×512 sugere que FramePack aplicou bucket sizing sobre uma imagem já redimensionada

## Ajustes necessários para produção

| # | Problema | Fix | Ficheiro/Node |
|---|---------|-----|---------------|
| 1 | Resolução baixa (480×512) | Remover/bypass `ImageResize+` nodes 59/50 | Workflow ComfyUI |
| 2 | Resolução de referência errada | Mudar `FramePackFindNearestBucket` de 640 para 1024+ | Node 51 |
| 3 | Movimento reduzido | Usar **1 imagem só no Start**, deixar End desligado | Workflow ComfyUI |
| 4 | Duração curta (4.83s) | Aumentar `total_second_length` de 5.0 para 60.0 | Node 39 FramePackSampler |
| 5 | Prompt com headers markdown | Entregar como **parágrafo único contínuo** | Adapter system prompt |

## Verificação pós-ajuste

Após aplicar os fixes acima, gerar novo vídeo e verificar:

```bash
ffprobe -v error -show_entries stream=width,height -show_entries format=duration -of json output.mp4
```

Deve reportar:
- `width`: 1024 (ou 2048, ou 4096)
- `height`: ~576 (ou 1152, ou 2304) — proporcional 16:9
- `duration`: ~4.83 (para teste com 5.0) ou ~60.0 (para produção)

Se ainda reportar width < 500, os `ImageResize+` ainda estão ativos.

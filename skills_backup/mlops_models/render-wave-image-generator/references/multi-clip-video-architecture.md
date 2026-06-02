# Multi-Clip Video Architecture for RTX 4060 Ti 16GB

## Problema

Gerar vídeo narrativo de 60 segundos com múltiplas cenas (ex: cascata → campo de flores → mão → volta ao início) a partir de uma única imagem com movimento natural e controlo de transições.

## Investigacao: Opcoes Testadas e Descartadas

| Abordagem | Modelo/Nodes | VRAM | Resultado |
|---|---|---|---|
| **LTX 2B native multi-keyframe** | `LTXSequencer` + `MultiImageLoader` (workflow javano2604.2) | ~8-12GB | **IMPOSSIVEL** — LTX 2B v0.9.5 é single-image-only. Multi-keyframe nativo requer LTX 2.3/13B (>16GB). Nodes `LTXSequencer`/`MultiImageLoader` nao encontrados em repo free. |
| **Wan 2.1 I2V** | Wan 2.1 14B | >16GB | **OOM** — ja provado inviavel em sessao anterior |
| **FramePack** | HunyuanVideo 13B | >16GB | **OOM persistente** — ja provado inviavel |
| **AnimateDiff Evolved img2vid** | mm_sdxl_v10_beta + closed_loop | ~10GB | **Falha** — produz 0 frames ou output vazio. Motion module SDXL nao compativel com img2vid neste setup. |

## Arquitetura Viavel: Multi-Clip + Crossfade (v4)

Para hardware RTX 4060 Ti 16GB, a unica abordagem realista:

```
Imagem 1 (cascata)  →  LTX 2B img2vid  →  Clip A (~4-8s, zoom lento para cascata)
Imagem 2 (campo)    →  LTX 2B img2vid  →  Clip B (~4-8s, pan sobre flores)
Imagem 3 (mao)      →  LTX 2B img2vid  →  Clip C (~4-8s, close-up lento)
Imagem 4 (cascata)  →  LTX 2B img2vid  →  Clip D (~4-8s, zoom out suave)
                                    ↓
                           ffmpeg concat + crossfade
                                    ↓
                        Video final loopavel 60s
```

### Vantagens
- Cada clip usa LTX 2B (funciona, testado)
- Controlo total sobre duracao de cada cena
- Controlo total sobre tipo de movimento por cena
- Crossfade suave mascara transicao entre cenas
- Loop perfeito: Clip D termina onde Clip A comeca

### Desvantagens
- Nao é "geracao unica" — requer N chamadas ao sampler
- N frames de overlap/crossfade (2s) sao "perdidos" (nao sao conteudo novo)
- Prompt de movimento por cena tem de ser escrito manualmente

## Prompt de Movimento por Tipo de Cena

| Tipo de cena | Prompt de movimento (exemplo) |
|---|---|
| Paisagem ampla | `camera slowly pans to the right, gentle breeze moving tree branches, clouds drifting lazily across sky, subtle ambient motion only` |
| Agua/cascata | `gentle ripples on water surface, water cascading softly over rocks, concentric waves expanding, shimmering reflections dancing` |
| Close-up natureza | `slow dolly zoom towards flower, petals swaying in soft breeze, light filtering through leaves creating dancing shadows` |
| Interior/lareira | `flames flickering gently, warm light pulsing softly on walls, smoke rising slowly in thin wisps, subtle breath-like light variation` |
| Transicao/retorno | `camera slowly pulls back revealing wider scene, gentle zoom out, ambient motion maintaining continuity` |

## Ferramentas de Concatenacao

### Opcao 1: ffmpeg (recomendado, script Python)
```bash
# Crossfade de 2 segundos entre clips
ffmpeg -i clipA.mp4 -i clipB.mp4 -i clipC.mp4 -i clipD.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=fade:duration=2:offset=6[f1]; \
                   [f1][2:v]xfade=transition=fade:duration=2:offset=12[f2]; \
                   [f2][3:v]xfade=transition=fade:duration=2:offset=18[outv]" \
  -map "[outv]" -c:v libx264 -preset slow -crf 18 output.mp4
```

### Opcao 2: ComfyUI nodes (se quiser fazer tudo no UI)
- `Bjornulf_custom_nodes` (github.com/justUmen/Bjornulf_custom_nodes) — free, 163 nodes
  - `Bjornulf_ConcatVideos` — concatena multiplos MP4 com ffmpeg
  - `Bjornulf_ConcatVideosFromList` — concatena a partir de lista de paths
- `ComfyUI-Animation_Nodes_and_Workflows` (github.com/Isi-dev) — `JoinVideos` para juntar batches
- `ComfyUI-KJNodes` — `CrossFadeImagesMulti` (frames, nao videos)

## Parametros LTX 2B por Clip

| Parametro | Valor | Nota |
|---|---|---|
| `strength` | 0.10 | Menos drift geometrico que 0.15 |
| `steps` | 50 | Mais limpo que default 30 |
| `length` | 96-192 | 4-8s a 24fps |
| Resolucao | 1024×576 | Sweet spot (2048 produz grain) |
| FPS | 24 | Standard |
| CFG | 3.0 | Padrao LTX |

## Pipeline Completo (script Python)

1. Gera N imagens via API Text2Image (ou usar imagens existentes)
2. Para cada imagem:
   - Adaptar prompt: imagem → movimento especifico para aquela cena
   - Chamar API img2vid LTX 2B
   - Guardar clip em pasta temporaria
3. Juntar clips com ffmpeg crossfade
4. Opcional: upscal final para 2560×1440 via ffmpeg lanczos
5. Guardar video final + metadata.txt

## Estado Atual dos Nodes no ComfyUI

| Pack | Instalado? | Nodes relevantes |
|---|---|---|
| ComfyUI-VideoHelperSuite | Sim | `VHS_VideoCombine`, `VHS_LoadVideo` |
| ComfyUI-KJNodes | Sim | `CrossFadeImages`, `CrossFadeImagesMulti` (frames, nao video) |
| ComfyUI-essentials | Sim | `ImageListToBatch`, `ImageBatchToList` |
| Bjornulf_custom_nodes | **Nao** | `ConcatVideos`, `ConcatVideosFromList` (free, recomendado instalar) |
| ComfyUI-Animation_Nodes | **Nao** | `JoinVideos` (free) |

## Nota sobre Pesquisa

Pesquisa exaustiva realizada em 2026-05-12 confirmou:
- Nao existe pack free com multi-keyframe nativo para LTX 2B
- Workflow `LTX2.3(MF-javano2604.2).json` refere nodes inexistentes no sistema
- Unica alternativa com um unico modelo é LTX 2.3/13B (inviavel em 16GB)
- Solucao "multi-clip + concat" é o padrao da industria para long-form AI video em hardware consumer

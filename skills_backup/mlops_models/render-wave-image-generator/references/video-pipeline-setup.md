# Video Pipeline Setup — AnimateDiff Evolved

Sessão: 2026-05-08

## Contexto
Expansão do pipeline THE RENDER WAVE de Image Creation → Video Creation. Geração de vídeo-loops perfeitos (1 minuto, closed-loop) usando AnimateDiff Evolved no ComfyUI.

## Decisão de Arquitetura (análise das opções)

| Opção | Pros | Cons | Veredicto |
|-------|------|------|-----------|
| **A — AnimateDiff Evolved** | Loop perfeito nativo (closed_loop), SDXL motion module, RTX 4060 Ti 16GB aguenta | Modelo ~1GB VRAM extra | ✅ ESCOLHIDO |
| B — Wan T2V / HunyuanVideo | Melhor qualidade visual | Modelos enormes (~6-12GB), loop não nativo, precisa de truques FFmpeg | ❌ Demasiado pesado |
| C — FFmpeg puro (Ken Burns) | Instantâneo, zero VRAM | Sem AI motion, puramente mecânico | ❌ Sem "alma" de AI |

## Setup Automatizado (setup_video.py)

O script faz:
1. Verifica dependências (`git`)
2. Instala `ComfyUI-AnimateDiff-Evolved` via `git clone`
3. Instala `ComfyUI-VideoHelperSuite` via `git clone`
4. Cria `models/` e `motion_lora/` dentro do node
5. Descarrega 5 ficheiros do HuggingFace (~1.3 GB):
   - `mm_sdxl_v10_beta.ckpt` (motion module principal, ~950MB)
   - `v2_lora_ZoomIn.ckpt`
   - `v2_lora_ZoomOut.ckpt`
   - `v2_lora_PanLeft.ckpt`
   - `v2_lora_PanRight.ckpt`

**URLs dos modelos:**
- Motion module: `https://huggingface.co/guoyww/animatediff/resolve/main/mm_sdxl_v10_beta.ckpt`
- LoRAs: `https://huggingface.co/Kosinkadink/animatediff-motion-lora/resolve/main/v2_lora_*.ckpt`

## Estrutura de Pastas Após Setup

```
ComfyUI-AnimateDiff-Evolved/
├── models/
│   ├── mm_sdxl_v10_beta.ckpt
│   └── .gitkeep
└── motion_lora/
    ├── v2_lora_ZoomIn.ckpt
    ├── v2_lora_ZoomOut.ckpt
    ├── v2_lora_PanLeft.ckpt
    └── v2_lora_PanRight.ckpt
```

## Workflow de Vídeo (por montar no UI)

O workflow precisa de ser construído visualmente no ComfyUI e exportado como API JSON.

Nodes necessários:
1. `CheckpointLoaderSimple` — modelo SDXL base
2. `CLIPTextEncode` (positivo + negativo)
3. `EmptyLatentImage` — `batch_size` = número de frames (ex: 16)
4. `ADE_AnimateDiffLoaderWithContext` — node principal do AnimateDiff Evolved
   - `model_name`: `mm_sdxl_v10_beta.ckpt`
   - `closed_loop`: `true` ← **CRÍTICO para loop perfeito**
   - `context_length`: 16
   - `context_stride`: 1
   - `context_overlap`: 4
   - `motion_lora`: opcional, um dos v2_lora_*.ckpt
5. `KSampler` — geração propriamente dita
6. `VAEDecode` — descodificar latente
7. `VHS_VideoCombine` — VideoHelperSuite, converte frames em MP4/GIF
   - `frame_rate`: 16
   - `format`: `video/h264-mp4`
8. `SaveVideo` / `VHS_VideoSave` — guardar ficheiro

## Parâmetros Recomendados para Loop Perfeito de 1 Minuto

| Parâmetro | Valor | Nota |
|-----------|-------|------|
| Nº de frames | 960 | 60s × 16 fps |
| Context length | 16 | Janela de processamento do AnimateDiff |
| FPS | 16 | Output final |
| Closed loop | `true` | Último frame = primeiro frame |
| Resolução | 1024×576 | Igual às imagens (16:9) |
| Steps | 30-50 | Menos que imagem porque é mais pesado |
| CFG | 7.0 | Ligeiramente mais baixo que imagem |

## Pontos de Atenção

- **O ComfyUI DEVE ser reiniciado** após instalar custom_nodes ou descarregar modelos
- O node `ADE_AnimateDiffLoaderWithContext` só aparece depois do reinício
- `closed_loop=true` é a feature que garante loop perfeito sem artefactos na junção
- A VRAM da RTX 4060 Ti 16GB aguenta SDXL motion module em BF16 (~1.6GB extra)
- Se o workflow for re-exportado, os node IDs podem mudar — sempre validar

## Estado Atual (2026-05-08)
- ✅ `ComfyUI-AnimateDiff-Evolved` instalado
- ✅ `ComfyUI-VideoHelperSuite` instalado
- ✅ 5 modelos descarregados
- ⏳ ComfyUI precisa de reinício para carregar nodes
- ⏳ Workflow de vídeo por montar no UI e exportar como API JSON
- ⏳ Script `generate_video.py` por criar

## Próximo Passo (depende do utilizador)
O user prefere:
- **A) Guiar passo a passo** para criar o workflow no UI do ComfyUI (mais controlo)
- **B) Construir o JSON diretamente** por código (mais rápido, pode precisar de ajustes)

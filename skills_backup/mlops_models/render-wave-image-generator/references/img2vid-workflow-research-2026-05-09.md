# Pesquisa: Workflows Image-to-Video (img2vid) para THE RENDER WAVE
## Data: 2026-05-09
## Requisitos: Loop perfeito 60 segundos, 16:9 (1024/2048/4096 largura), RTX 4060 Ti 16GB, Local/Privado/Gratuito

---

## RESUMO EXECUTIVO

| Rank | Modelo | I2V Nativo | Anti-Drift | 60s Direto | VRAM 16GB | Recomendação |
|------|--------|-----------|------------|------------|-----------|-------------|
| 1 | **FramePack** | ✅ Sim | ✅ Sim (nativo) | ✅ Sim (1800 frames) | ✅ RTX 3060 6GB já funciona | **MELHOR ESCOLHA** |
| 2 | SVD (Stable Video Diffusion) | ✅ Sim | ❌ Não | ❌ Não (~4s) | ✅ Leve | Backup simples |
| 3 | Wan 2.1 | ✅ Sim | ❌ Não | ❌ Não (~5s) | ⚠️ 14B pesado | Se FramePack falhar |

**Decisão: FramePack é a única opção que gera 60 segundos diretamente com anti-drift nativo.**

---

## OPÇÃO 1: FRAMEPACK (RECOMENDADA)

**Criador:** lllyasviel (mesmo do ControlNet, Fooocus)  
**Base:** HunyuanVideo 13B com arquitetura next-frame-prediction  
**Anti-drift:** Nativo — previne deriva temporal

**Porquê é perfeito para o THE RENDER WAVE:**
- Gera **60 segundos diretamente** (1800 frames a 30fps)
- Funciona em **RTX 3060 6GB** — a tua 4060 Ti 16GB sobra
- **I2V nativo** — dá-lhe uma imagem, ele gera o vídeo
- **FP8 disponível** — modelo comprimido

**Modelos necessários (~12GB total):**

| Modelo | Tamanho ~ | Destino ComfyUI | URL |
|--------|-----------|-----------------|-----|
| `FramePackI2V_HY_fp8_e4m3fn.safetensors` | ~4GB | `models/diffusion_models/` | https://huggingface.co/Kijai/HunyuanVideo_comfy/blob/main/FramePackI2V_HY_fp8_e4m3fn.safetensors |
| `clip_l.safetensors` | ~400MB | `models/text_encoders/` | já tens ou HF |
| `llava_llama3_fp16.safetensors` | ~6GB | `models/text_encoders/` | https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged/tree/main/split_files |
| `sigclip_vision_patch14_384.safetensors` | ~800MB | `models/clip_vision/` | https://huggingface.co/Comfy-Org/sigclip_vision_384/tree/main |
| `hunyuan_video_vae_bf16.safetensors` | ~800MB | `models/vae/hunyuan/` | https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged/tree/main/split_files/vae |

**Custom node:** `ComfyUI-FramePackWrapper` → https://github.com/kijai/ComfyUI-FramePackWrapper  
**Workflow exemplo:** https://github.com/kijai/ComfyUI-FramePackWrapper/blob/main/example_workflows/framepack_hv_example.json  
**Artigo setup:** https://civitai.com/articles/13907/img2vid-with-framepack-on-comfyui-now-with-first-and-last-frame-support

**Nodes principais do workflow:**
```
[Load Image] ──→ [GetImageSizeAndCount] ──→ [FramePackFindNearestBucket]
                     ↓
[DualCLIPLoader] ──→ [CLIPTextEncode] ──→ [FramePackSampler]
                     ↓                              ↑
[CLIPVisionLoader] → [CLIPVisionEncode]            [LoadFramePackModel]
                     ↓                              ↑
[VAELoader] ───────→ [VAEEncode] ─────────────── [DownloadAndLoadFramePackModel]
                     ↓
              [VAEDecodeTiled] ──→ [VHS_VideoCombine]
```

---

## OPÇÃO 2: SVD (STABLE VIDEO DIFFUSION)

- Modelo da Stability AI, ComfyUI nativo
- **Limitação:** Gera apenas ~4 segundos (25 frames)
- Para 60 segundos = ~15 segmentos, deriva temporal visível
- **Workflow:** https://github.com/aimpowerment/comfyui-workflows/blob/main/SDV%20-%20img2vid.json
- **Modelo:** `svd_xt_1_1.safetensors` (~4GB)

---

## OPÇÃO 3: WAN 2.1

- Modelo open-source Alibaba
- **Limitação:** 14B pesado, ~5 segundos/iteração, wrapper complexo (1.2k issues)
- **Wrapper:** https://github.com/kijai/ComfyUI-WanVideoWrapper

---

## ESTRATÉGIA DE LOOP PERFEITO (60 SEGUNDOS)

Independente do modelo, para loop perfeito de 60s no YouTube:

**Método: Ping-Pong + Loop FFmpeg**

1. Gerar vídeo curto com movimento suave (5-10 segundos)
2. Inverter o vídeo (reverso)
3. Concatenar original + reverso = loop perfeito de 10-16s
4. Loop FFmpeg N vezes até 60s

```bash
# 1. Criar ping-pong
ffmpeg -i input.mp4 -filter_complex "
  [0]trim=0:5,setpts=PTS-STARTPTS[first];
  [0]trim=1:5,reverse,setpts=PTS-STARTPTS[rev];
  [first][rev]concat=n=2:v=1:a=0
" -c:v libx264 pingpong_10s.mp4

# 2. Loop 6x para 60 segundos
ffmpeg -stream_loop 5 -i pingpong_10s.mp4 -c copy output_60s.mp4
```

---

## COMPARAÇÃO

| | FramePack | SVD | Wan 2.1 |
|--|-----------|-----|---------|
| Custom node | `ComfyUI-FramePackWrapper` | Nativo | `ComfyUI-WanVideoWrapper` |
| Modelo principal | ~4GB (FP8) | ~4GB | ~14GB |
| **Total VRAM em uso** | ~8-12GB | ~4-6GB | ~10-14GB |
| **Tempo de geração 60s** | 1 pass | ~15 passes | ~12 passes |
| Anti-drift | ✅ Nativo | ❌ Não | ❌ Não |

## Parâmetros do `FramePackSampler` (do código-fonte)

| # | Parâmetro | Tipo | Default | Range | Descrição |
|---|-----------|------|---------|-------|-----------|
| 1 | `steps` | INT | 30 | ≥1 | Iterações de denoising |
| 2 | `use_teacache` | BOOLEAN | true | — | Acelera sampling (cache) |
| 3 | `teacache_rel_l1_thresh` | FLOAT | 0.15 | 0.0-1.0 | Tolerância do cache. Mais alto = mais rápido, menos qualidade |
| 4 | `cfg` | FLOAT | 1.0 | 0.0-30.0 | Classifier-free guidance. FramePack usa baixo CFG (1.0-1.5) |
| 5 | `guidance_scale` | FLOAT | 10.0 | 0.0-32.0 | Escala de guidance adicional. 5-15 aumenta coerência com prompt |
| 6 | `shift` | FLOAT | 0.0 | 0.0-1000.0 | Shift do scheduler. 0 para I2V, usado em T2V |
| 7 | `seed` | INT | 0 | ≥0 | Seed aleatória |
| 8 | `latent_window_size` | INT | 9 | 1-33 | Tamanho da janela latente. Maior = mais frames de uma vez |
| 9 | `total_second_length` | FLOAT | 5.0 | 1-120 | **DURAÇÃO EM SEGUNDOS**. 60.0 = 1800 frames a 30fps |
| 10 | `gpu_memory_preservation` | FLOAT | 6.0 | 0.0-128.0 | VRAM a preservar (GB). 6.0 para RTX 3060, 10-12 para RTX 4060 Ti |
| 11 | `sampler` | select | unipc_bh1 | unipc_bh1/bh2 | Algoritmo de sampling |
| — | `embed_interpolation` | select | disabled | disabled/weighted_average/linear | Interpolação entre embeddings de start/end image |
| — | `start_embed_strength` | FLOAT | 1.0 | 0.0-1.0 | Força do embed da imagem start quando há end image |
| — | `denoise_strength` | FLOAT | 1.0 | 0.0-1.0 | Força do denoising para video2video (não I2V) |

**Fórmula interna:** `total_latent_sections = (total_second_length * 30) / (latent_window_size * 4)`  
FramePack gera a **30 FPS fixos**. A duração controla-se apenas via `total_second_length`.

**Diferença Start-only vs Start+End:**
- **Só Start image** (I2V clássico): vídeo com movimento a partir de 1 imagem
- **Start + End image** (morphing): vídeo transforma imagem A em imagem B ao longo da duração
- End image é **opcional** — ligar `end_latent` e `end_image_embeds` só quando se quer morphing

### Recomendação de primeiro teste

| Parâmetro | Valor |
|-----------|-------|
| `total_second_length` | **5.0** (testar primeiro, não 60) |
| `steps` | 30 |
| `latent_window_size` | 9 |
| `guidance_scale` | 10 |
| `seed` | 12345 (fixo) |
| `gpu_memory_preservation` | 8.0 |

Usar **1 imagem só no Start**, sem End. Prompt descrevendo movimento suave. Validar coerência em 5s antes de passar para 60s.


1. Instalar `ComfyUI-FramePackWrapper`
2. Descarregar modelos FP8
3. Testar workflow exemplo com imagem do `Image_creation`
4. Criar loop perfeito via FFmpeg ping-pong
5. Exportar workflow limpo para API JSON

---

## LINKS
- FramePack oficial: https://lllyasviel.github.io/frame_pack_gitpage/
- FramePack GitHub: https://github.com/lllyasviel/FramePack
- ComfyUI wrapper: https://github.com/kijai/ComfyUI-FramePackWrapper
- Workflow exemplo: https://github.com/kijai/ComfyUI-FramePackWrapper/blob/main/example_workflows/framepack_hv_example.json
- Civitai artigo: https://civitai.com/articles/13907/img2vid-with-framepack-on-comfyui-now-with-first-and-last-frame-support
- Modelo FP8: https://huggingface.co/Kijai/HunyuanVideo_comfy/blob/main/FramePackI2V_HY_fp8_e4m3fn.safetensors

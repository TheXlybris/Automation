# LTX Video 2B — Grain Analysis and Resolution Sweet Spot

**Date:** 2026-05-11
**Context:** THE RENDER WAVE — testing LTX Video 2B img2vid at different resolutions

## Test Results (2026-05-11)

| Video | Output Resolution | Bitrate | Grain/Artifacts | Fidelity to Source | Verdict |
|-------|-------------------|---------|-----------------|-------------------|---------|
| ComfyUI_00001_.mp4 | 1024×576 | 1.1 Mbps | Moderate, acceptable | High | ✅ Good |
| ComfyUI_00002_.mp4 | 2048×1152 | 4.5 Mbps | **Very high** — pervasive multicolored speckles | Low | ❌ Poor |
| ComfyUI_00003_.mp4 | 2048×1152 | 5.6 Mbps | **Very high** — canvas-like texture, painting/watercolor effect | Low | ❌ Poor |
| ComfyUI_00004_.mp4 | 1024×576 | 3.5 Mbps | **Almost zero** | Very high | ✅ Excellent — clean, vibrant, no artifacts |

**Confirmed by frame extraction + visual analysis:**
- **Video 02 (2048×1152):** Ruído e grão abundantes em toda a superfície. Textura de "tela/canvas" sobreposta. Bordas moles, falta micro-contraste. Definição de detalhes comprometida.
- **Video 03 (2048×1152):** Desfoque generalizado + textura de canvas diagonal/cruzado. Banding nas transições de cor (céu, névoa). Efeito pictórico/aquarelado — aparenta filtro artístico indesejado.
- **Video 04 (1024×576):** Extremamente nítido. Zero ruído. Excelente definição de flores, musgo, relva, rochas, água. Frame praticamente impecável.

## Diagnosis

**1024 output = less grain + higher fidelity. 2048 = heavy grain + lower fidelity.**

Why:
- LTX Video 2B is a ~2B parameter model trained on modest resolutions (likely up to 768×512 native). When asked for 2048×1152, the model is doing aggressive upscaling — the neural network "invents" details at high res, and that invention manifests as statistical grain.
- `strength=0.15` injects temporal noise. At 2048, that noise is more visible because there are more pixels to distribute the same "coherence budget" of the model.
- **Visual analysis reveals this is not just "grain"** — it's canvas texture, painting-like artifacts, and banding, suggesting the VAE or decoder is struggling at 2K and falling back to painterly approximations.

## Recommendations

1. **Keep 1024 output** — sweet spot for this model on RTX 4060 Ti 16GB. High fidelity, minimal grain.
2. **Never generate at 2048 with LTX Video 2B** — quality degradation is severe and not fixable by post-processing.
3. **Post-process 2048 with ffmpeg denoise** — if stuck with 2048 source, filters like `nlmeans` or `hqdn3d`:
   ```bash
   ffmpeg -i input.mp4 -vf "hqdn3d=luma_spatial=4.0:chroma_spatial=3.0" output.mp4
   ```
   (Note: this will NOT recover lost detail, only smooth the grain.)
4. **Increase steps in LTXVScheduler** — from 30 to 40-50. More denoising steps = less grain, but slower generation.
5. **Test `strength=0.10`** — less injected noise = less grain, but more subtle motion.
6. **Use VAE in FP32** — if ComfyUI is using VAE in FP16, numeric artifacts may occur. Check if FP32 option exists in VAEDecode node.

## Production Recommendation

For THE RENDER WAVE pipeline: generate at **1024×576** (or 1024 width proportional) and only upscale at the end with ffmpeg `lanczos` or a super-resolution model (Real-ESRGAN) if needed. LTX Video 2B was not designed for native 2K — force it and grain is the price.

**Hardware-specific note:** This finding applies to RTX 4060 Ti 16GB with LTX Video 2B in FP16. Other GPUs or FP32 modes may behave differently.
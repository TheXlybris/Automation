# LTX Video 2B — img2vid Setup for THE RENDER WAVE

**Date:** 2026-05-11
**Context:** THE RENDER WAVE pipeline — local, private, free video generation for relaxing YouTube videos
**Hardware constraint:** RTX 4060 Ti 16GB VRAM

## Why LTX Video 2B was selected

After systematically testing/discarding alternatives on 16GB VRAM:

| Model | Status | Why discarded |
|-------|--------|---------------|
| **AnimateDiff Evolved img2vid** | ❌ DISCARDED | Produces only 1 frame (0.13s video). Root cause: denoise=1.0 makes KSampler ignore input latent; no multi-frame mechanism exists in standard workflows. |
| **FramePack (HunyuanVideo 13B)** | ❌ DISCARDED | Persistent OOM even with `gpu_memory_preservation=10`, `latent_window_size=5`, bucket=768. Tensor mismatches with wrapper forks. |
| **Wan 2.1 I2V** | ❌ DISCARDED | Minimum model is 14B (~14-16GB in FP8). No 1.3B I2V variant exists. Borderline/inviable on 16GB. |
| **LTX Video 2B** | ✅ SELECTED | ~2B params, ~8-12GB VRAM in fp16. Native ComfyUI nodes. img2vid functional with `strength=0.15`. |

## Required Models

| File | Size | HuggingFace URL | Destination |
|------|------|-----------------|-------------|
| `ltx-video-2b-v0.9.5.safetensors` | ~2.4GB | `https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.5.safetensors` | `ComfyUI/models/checkpoints/` |
| `t5xxl_fp16.safetensors` | ~5GB | `https://huggingface.co/comfyanonymous/LTX-Video/resolve/main/t5xxl_fp16.safetensors` | `ComfyUI/models/text_encoders/` |

## Node Verification

LTX Video nodes are **native** in ComfyUI ≥0.19.3. No custom node installation needed.

Verify presence:
```bash
grep -r "class LTXVImgToVideo\|class LTXVConditioning\|class LTXVScheduler" \
  /path/to/ComfyUI/comfy_extras/nodes_lt.py
```

Expected classes:
- `LTXVImgToVideo`
- `LTXVConditioning`
- `LTXVScheduler`
- `LTXVImgToVideoInplace`

## Working Workflow Parameters

From `Image to Video LTXV.json` (tested workflow):

| Parameter | Value | Note |
|-----------|-------|------|
| `width` | 768 | Input image is resized to this |
| `height` | 960 | Portrait-ish; adjust to 1024×576 for 16:9 |
| `length` | 97–257 | Frames; 97@25fps≈3.9s, 153≈6.1s, 257≈10.3s |
| `strength` | 0.15 | **Critical**: 0.15 = preserve 85% of image, add 15% motion noise |
| `frame_rate` | 25 | Output FPS |
| `steps` | 30–50 | LTXVScheduler steps; higher = cleaner but slower |
| `cfg` | 3 | Low CFG typical for video diffusion |
| `sampler` | euler | Via KSamplerSelect |
| `max_shift` | 2.05 | LTXVScheduler parameter |
| `base_shift` | 0.95 | LTXVScheduler parameter |

**Duration control (web UI):** A slider from 2–10 seconds maps to frames via `frames = round(seconds × 25)` at 25fps. The UI displays both seconds and the computed frame count.

**Strength guidance:**
- `0.05` = minimal motion, maximum structural fidelity (best for rigid objects: furniture, buildings)
- `0.10` = very subtle motion, reduced grain
- `0.15` = gentle ambient motion (recommended for relaxing videos, nature scenes)
- `0.25` = moderate motion
- `0.50` = heavy motion, may drift from original image
- `1.00` = ignore image completely (text2vid)

**⚠️ Structural Object Distortion (2026-05-12):** LTX Video reconstructs the input image frame-by-frame via diffusion. The more motion you request, the more the model "invents" over the original geometry. **Rigid structured objects** (sofas, fireplaces, buildings, furniture) are particularly prone to visible distortion — edges warp, proportions shift, and textures smear.

**Mitigations (ordered by effectiveness):**
1. **Reduce `strength` to 0.05–0.10** — less noise injection = less geometric drift (trade-off: subtler motion)
2. **Add to prompt:** `"preserve original composition, no structural changes, fixed architecture, subtle ambient motion only"`
3. **Use input images at resolutions that are multiples of 32**
4. **Avoid scenes with rigid man-made objects** — nature, water, clouds, and organic materials handle img2vid much better

**When to accept the limitation:** If structural fidelity is critical and motion must be visible, consider:
- Generating at very low strength (0.05) → mostly static with tiny flicker
- Using the image as a static background and adding particle/fire effects in post (ffmpeg overlay)
- Switching to a different img2vid model (FramePack, Wan 2.1, or SVD)

## Workflow Structure (API JSON)

Key nodes:
- `38` = CLIPLoader (t5xxl_fp16, type=ltxv)
- `44` = CheckpointLoaderSimple (ltx-video-2b-v0.9.5)
- `6` = CLIPTextEncode (positive prompt)
- `7` = CLIPTextEncode (negative prompt)
- `77` = LTXVImgToVideo (injects image + conditions, outputs latent)
- `69` = LTXVConditioning (frame_rate + positive/negative conditioning)
- `71` = LTXVScheduler (steps, shifts, sigmas)
- `72` = SamplerCustom (add_noise=true, latent_image from LTXVImgToVideo)
- `8` = VAEDecode (samples → pixels)
- `80` = CreateVideo (images → video)
- `81` = SaveVideo (fps=24, format=mp4)

## From 4-second clips to 1-minute loop to 4-8 hours

LTX Video 2B generates ~4s clips. To reach longer durations:

1. **Generate multiple clips** from the same base image with slightly different seeds/strengths
2. **Crossfade in FFmpeg** between clips to create seamless transitions
3. **Loop the 1-minute composite** with `ffmpeg -stream_loop -1` for 4-8 hour ambient videos

This avoids the need for a single 60s AI generation (which would require 900+ frames and likely OOM).

## VRAM Budget Estimate

| Component | VRAM |
|-----------|------|
| LTX Video 2B model (fp16) | ~4-5GB |
| T5-XXL text encoder | ~5GB |
| VAE + latent buffers | ~2-3GB |
| **Total** | **~11-13GB** |
| Headroom on 16GB | ~3-5GB ✅ |

## Next Steps (post-setup)

1. Download both models to correct folders
2. Load `Image to Video LTXV.json` in ComfyUI UI
3. Test with a generated landscape image (strength=0.15)
4. Verify output MP4 has ~4s duration and visible motion
5. Adapt workflow for 16:9 (1024×576 or 2048×1152)
6. Create automation script (adapt `run_img2vid.py` for LTX nodes)

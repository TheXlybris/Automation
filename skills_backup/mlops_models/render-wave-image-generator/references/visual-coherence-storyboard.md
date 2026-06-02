# Visual Coherence for Storyboard Multi-Clip Videos

Problem: When generating multiple images for a video storyboard (e.g., waterfall → close-up waterfall → hand with butterfly → back to waterfall), each independent SDXL generation produces a completely different waterfall, even with similar prompts. The scene looks like it jumped to a different location, not a camera moving within the same scene.

This breaks the illusion of "camera moving through a single coherent space" when clips are stitched.

## Methods Evaluated

### A — Same Seed + Incremental Prompt
Keep seed fixed, alter only camera/distance terms in prompt.

| Pros | Cons |
|------|------|
| Zero setup | Only works for tiny variations; close-up produces an unrecognizable different scene |
| Fast to test | SDXL treats "close-up" as a completely different latent space composition |

Verdict: Insufficient for storyboard-level changes (wide → close-up → detail → wide).

### B — Img2img with Low Denoise (0.30–0.50)
Generate scene master (wide shot), then use it as `latent_image` in KSampler with reduced denoise.

| Denoise | Effect |
|---------|--------|
| 0.25–0.35 | Small camera shift (slight zoom, minor pan) |
| 0.40–0.50 | Larger change (close-up, angle shift) |
| 0.55–0.65 | Dramatic reframing (still recognizable) |

| Pros | Cons |
|------|------|
| Uses existing workflow, zero new models | Still limited — large reframes degrade quality |
| Perfect scene coherence (same rocks, same flowers) | Very low denoise = very subtle changes only |
| Works today with existing setup | High denoise = loses coherence advantage |

Verdict: Good for minor camera movements, insufficient for storyboard narrative jumps.

### C — IP-Adapter (User Selected)
IP-Adapter transfers "visual identity" of a reference image to new generations. Think of it as a 1-image LoRA.

| Pros | Cons |
|------|------|
| Best coherence across large camera changes | Requires ~2GB of model downloads |
| Allows completely different prompts while keeping scene identity | Requires custom node pack installation |
| Industry-standard technique for image-conditioned generation | Slightly slower inference |

Verdict: **Selected by user** as the preferred approach for THE RENDER WAVE storyboard pipeline.

## IP-Adapter Installation (THE RENDER WAVE context)

### Custom Node
```bash
cd /mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/custom_nodes
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
```

### Model Downloads (~2GB total)
| File | Size | Destination | Filename on disk |
|------|------|-------------|-----------------|
| Plus SDXL | ~780MB | `models/ipadapter/` | `ip-adapter-plus_sdxl_vit-h.safetensors` |
| Standard SDXL | ~722MB | `models/ipadapter/` | `ip-adapter_sdxl_vit-h.safetensors` |
| ViT-H Image Encoder | ~1.2GB | `models/clip_vision/` | `ViT-H-14_s32B_b79K.safetensors` |

**Note:** Existing `sigclip_vision_patch14_384.safetensors` in `clip_vision/` is a SigLIP model, not the ViT-H required by IP-Adapter. Must download the specific `image_encoder` model and rename it to match the regex pattern: `ViT-H-14_s32B_b79K.safetensors`. The `IPAdapterUnifiedLoader` node searches with regex `r'(ViT.H.14.*s32B.b79K|...)'` — a file named `model.safetensors` alone will NOT be found.

### Workflow (Exact Node Chain)
Confirmed working chain from `03_Workflows/ComfyUI_Text2Image_IPAdapter_Coherent.json`:
```
LoadImage (scene_master.png) → PrepImageForClipVision
                                     ↓
CheckpointLoaderSimple → IPAdapterUnifiedLoader (preset: "PLUS (high strength)")
                                     ↓
IPAdapterAdvanced (weight=0.8, weight_type="linear", combine_embeds="concat")
                                     ↓
KSampler + CLIPTextEncode (Positivo) + CLIPTextEncode (Negativo)
                                     ↓
VAEDecode → SaveImage
```

**Resolution:** 2400×1350 (16:9 widescreen, user preference).

### Key Parameters
| Parameter | Value | Effect |
|-----------|-------|--------|
| `weight` | 0.8 | Balanced — strong scene identity, still follows prompt |
| `weight_type` | `linear` | Standard weight curve |
| `combine_embeds` | `concat` | Concatenate text + image embeddings |
| `start_at` / `end_at` | 0.0 / 1.0 | Full generation influenced by reference |
| `embeds_scaling` | `V only` | Scale image embedding in V projection only |
| `denoise` in KSampler | 1.0 | Correct for IP-Adapter; image influence comes from IP-Adapter, not low denoise |
| `steps` | 70 | Same as standard Text2Image |
| `cfg` | 8 | Same as standard Text2Image |

### Workflow Files
- API format: `D:/AI_Ecosystem/03_Workflows/API/Text2Image_IPAdapter_Coherent_API.json`
- UI format (with links): `D:/AI_Ecosystem/03_Workflows/ComfyUI_Text2Image_IPAdapter_Coherent.json`
- Node structure reference: `references/ip-adapter-workflow-nodes.md`

## Decision: Image Coherence Method for Storyboard

For THE RENDER WAVE:
1. **Generate scene master image** via standard `Text2Image_API.json`
2. **Generate all storyboard frames** via IP-Adapter (method C), using scene master as reference
3. **Generate clips** via `Image2Video_LTXV_API.json` for each coherent image
4. **Stitch clips** via Python pipeline (`storyboard_pipeline.py`) with ffmpeg xfade

This method (C) was explicitly chosen by the user over B because it offers the best visual consistency across camera distance changes in a narrative storyboard.

## Files
- Scene master images: `04_Data/Hermes/images/output/`
- Storyboard config: `08_Config/storyboard.json`
- IP-Adapter custom node: `02_Engines/ComfyUI/ComfyUI/custom_nodes/ComfyUI_IPAdapter_plus/`
- Pipeline script: `05_Code/storyboard_pipeline.py`

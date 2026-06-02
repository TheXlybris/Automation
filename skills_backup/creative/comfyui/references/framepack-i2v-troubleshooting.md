# FramePack I2V Troubleshooting Reference

## Session context
Date: 2026-05-09
Hardware: RTX 4060 Ti 16GB
Project: THE RENDER WAVE (img2vid pipeline)

---

## Workflow nodes (official kijai wrapper)

| Node ID | Type | Purpose |
|---------|------|---------|
| 52 | LoadFramePackModel | Load transformer + quantization |
| 54 | DownloadAndLoadFramePackModel | Auto-download from HuggingFace (bypassed, mode=4) |
| 13 | DualCLIPLoader | CLIP + LLaMA3 text encoders |
| 12 | VAELoader | HunyuanVideo VAE |
| 51 | FramePackFindNearestBucket | Resolution bucket selector |
| 39 | FramePackSampler | Core sampler |
| 27 | FramePackTorchCompileSettings | torch.compile config |
| 47 | CLIPTextEncode | Positive prompt |
| 15 | ConditioningZeroOut | Negative prompt handling |
| 20 | CLIPVisionEncode | Vision encoding of start image |
| 17 | CLIPVisionEncode | Vision encoding of end image |
| 58 | LoadImage | Start image |
| 19 | LoadImage | End image |
| 57 | VAEEncode | Encode start image to latent |
| 62 | VAEEncode | Encode end image to latent |
| 50 | ImageResize+ | Resize end image |
| 59 | ImageResize+ | Resize start image |
| 49 | EmptyHunyuanVideoLatent | Empty latent for generation |
| 48 | VAEDecodeTiled | Decode final latents |
| 23 | VHS_VideoCombine | Export MP4/WEBP |

---

## Error catalogue

### Error: OOM (Out of Memory)
```
Allocation on device 0 would exceed allowed memory.
Currently allocated: 22.43 GiB
Requested: 4.07 GiB
Device limit: 16.00 GiB
```

**Cause:** `end_latent` pin disconnected on FramePackSampler. Without an end
anchor, the model needs 26+ GB for free-form generation.

**Fix:** Re-connect `end_latent` to a VAEEncode of the same image (or a
slightly altered variant). Do NOT disconnect this pin on 16GB cards.

---

### Error: Tensor size mismatch in rotary embeddings
```
RuntimeError: The size of tensor a (15890) must match the size of tensor b (15859)
  at non-singleton dimension 1
```
Location: `apply_rotary_emb_transposed` in `hunyuan_video_packed.py`

**Cause:** Image dimensions do not match the expected patch grid for the
selected bucket. The RoPE embeddings are precomputed for a specific
resolution and do not align with the actual latent size.

**Fix:** Ensure the input image resolution matches one of the supported
bucket sizes. Safe values: 512×512, 640×360, 768×432, 960×540, 1024×576.
Avoid arbitrary dimensions. Check that `FramePackFindNearestBucket` and
any `ImageResize+` nodes agree on the same resolution.

---

### Error: Tensor cat dimension mismatch
```
RuntimeError: Sizes of tensors must match except in dimension 2.
Expected size 69 but got size 72 for tensor number 1 in the list.
```
Location: `torch.cat([clean_latents_pre, clean_latents_post], dim=2)`

**Cause:** Latent dimensions from start and end images differ. This happens
when start and end images have different resolutions or when the bucket
size does not match the actual encoded latent.

**Fix:** Ensure start and end images have identical dimensions. Verify that
`ImageResize+` nodes (if present) are connected and set to the same size.
Or bypass them and feed images that already match the bucket resolution.

---

### Error: Tensor mismatch (47 vs 46)
```
RuntimeError: The size of tensor a (47) must match the size of tensor b (46)
  at non-singleton dimension 3
```

**Cause:** Similar to above — latent padding / section dimensions do not
align. Occurs when `FramePackFindNearestBucket` selects a resolution that
does not cleanly divide by the model's patch size (typically 2×2 or 4×4).

**Fix:** Use the bucket sizes listed above. Do not use custom resolutions.

---

## Working configuration for RTX 4060 Ti 16GB

| Parameter | Value | Notes |
|-----------|-------|-------|
| `total_second_length` | 5.0 (test) / 60.0 (prod) | 60s = 1800 frames |
| `guidance_scale` | 12.0–15.0 | Higher forces more motion |
| `steps` | 30 | Can reduce to 20 for speed |
| `latent_window_size` | 9 | Default; reduce to 5 if OOM |
| `gpu_memory_preservation` | 10.0 | Aggressive CPU offload |
| `end_latent` | **Connected** (same image or variant) | Required for 16GB |
| `bucket` (FindNearestBucket) | 768 | 768×432 = safe 16:9 |
| `dtype` (LoadFramePackModel) | bf16 or fp16 | fp8 if available |
| `quantization` | fp8_e4m3fn or disabled | fp8 saves VRAM |
| `attention_mode` | sdpa | Flash attention if installed |

---

## Prompt format for FramePack

**Input (image prompt):**
```
masterpiece, photorealistic, 8k, a breathtaking landscape...
```

**Output (video prompt — single flowing paragraph):**
```
a breathtaking landscape of a crystal-clear river winding through a vast lush
green meadow dotted with colorful wildflowers, distant rolling hills on the
horizon, warm golden hour sunlight casting long soft shadows, bright blue sky
with soft white clouds, gentle ripples spreading smoothly across the water
surface with soft concentric waves shimmering and reflecting the sky, grass
blades and wildflowers swaying rhythmically in a gentle breeze, leaves and
petals nodding softly, clouds drifting lazily overhead with warm golden
sunlight flickering subtly through the moving air creating soft dancing
highlights and slowly shifting shadows, consistent scene, stable composition,
camera remains still, subtle ambient motion only, fixed viewpoint, seamless
cyclic motion, smooth continuous movement, infinite loop feel, ambient
perpetual motion, natural repeating rhythm, hypnotic gentle flow, meditative
calm motion
```

**Negative:**
```
static image, frozen frame, no movement, camera pan, camera zoom,
camera movement, shaky footage, abrupt changes, jitter, flickering,
morphing, warping, object disappearance, scene change
```

**Rules:**
- No markdown headers ("Scene anchor:", "Motion layer:")
- No bullet points
- One continuous paragraph
- No repetition of the same motion verb for different objects
- Group objects that share motion: "grass blades and wildflowers swaying"

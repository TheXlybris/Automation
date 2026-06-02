# LTX Video 2B — Workflow Operation Guide

Reference for operating the `Image2Video_LTXV` workflow in ComfyUI and exporting it for API automation.

---

## Files

| File | Purpose | Path |
|------|---------|------|
| **Template** | Load into ComfyUI UI, adjust visually | `D:/AI_Ecosystem/03_Workflows/API/Image2Video_LTXV_TEMPLATE.json` |
| **Instructions** | Human-readable guide to all nodes | `D:/AI_Ecosystem/03_Workflows/API/Image2Video_LTXV_INSTRUCOES.md` |
| **API export** | Created by user after UI tuning; used by scripts | `D:/AI_Ecosystem/03_Workflows/API/Image2Video_LTXV.json` (or `Image2Video_LTXV_Meu.json`) |

**Rule:** Never overwrite the TEMPLATE. Always create a new file when exporting from the UI.

---

## Node Reference (API format)

| Node ID | `class_type` | Key Inputs | Default | Notes |
|---------|-------------|------------|---------|-------|
| `6` | `CLIPTextEncode` | `text` | Long waterfall prompt | Positive prompt — describe motion |
| `7` | `CLIPTextEncode` | `text` | Negative prompt | Negative prompt |
| `38` | `CLIPLoader` | `clip_name`, `type` | `t5xxl_fp16.safetensors`, `ltxv` | T5 text encoder for LTX |
| `44` | `CheckpointLoaderSimple` | `ckpt_name` | `ltx-video-2b-v0.9.5.safetensors` | LTX 2B model |
| `69` | `LTXVConditioning` | `frame_rate`, `positive`, `negative` | 25 fps | Conditioning node |
| `71` | `LTXVScheduler` | `steps`, `max_shift`, `base_shift`, `stretch`, `terminal` | 50 steps | Scheduler config |
| `72` | `SamplerCustom` | `noise_seed`, `cfg`, `model`, `positive`, `negative`, `sampler`, `sigmas`, `latent_image` | seed=866826632611090, cfg=3 | Main sampler |
| `73` | `KSamplerSelect` | `sampler_name` | `euler` | Sampler selection |
| `77` | `LTXVImgToVideo` | `width`, `height`, `length`, `batch_size`, `strength`, `positive`, `negative`, `vae`, `image` | 1024×576, 153 frames, strength=0.1 | **Critical node** — controls resolution, duration, motion fidelity |
| `78` | `LoadImage` | `image` | `ComfyUI_00005_ (1).png` | Input image filename |
| `80` | `CreateVideo` | `fps`, `images` | 24 fps | Composes frames to video |
| `81` | `SaveVideo` | `filename_prefix`, `format`, `codec`, `video` | `video/ComfyUI`, `mp4`, `auto` | Saves MP4 to disk |

---

## Parameter Sweet Spots

| Parameter | Node | Range | Production Value | Effect |
|-----------|------|-------|------------------|--------|
| `strength` | 77 | 0.05 – 0.30 | **0.10** (clean), 0.15 (more motion) | Lower = more faithful to input image; higher = more invented motion |
| `length` | 77 | 49 – 153 | **153** (~6.4s @ 24fps) | Frame count; 153 is max before degradation |
| `steps` | 71 | 30 – 50 | **50** | More steps = cleaner, slower |
| `cfg` | 72 | 2 – 4 | **3** | Lower = more creative; higher = more prompt-faithful |
| `width/height` | 77 | 512 – 1024 | **1024×576** (16:9) | Higher = more VRAM; 2048×1152 causes grain |
| `fps` | 80 | 12 – 30 | **24** | Playback framerate |

---

## Operational Steps

### 1. Load Template in ComfyUI
- Open ComfyUI in browser
- Click **Load** or drag `Image2Video_LTXV_TEMPLATE.json` onto canvas

### 2. Adjust Key Nodes
- **Node 78 (Load Image):** Select input PNG/JPG from `ComfyUI/input/`
- **Node 6 (Positive Prompt):** Edit motion description. Keep keywords: `stable composition`, `fixed viewpoint`, `seamless cyclic motion` for loopable output
- **Node 77 (LTXVImgToVideo):** Set width, height, length, strength
- **Node 71 (LTXVScheduler):** Adjust steps if needed
- **Node 72 (SamplerCustom):** Set seed (-1 for random) or fixed for reproducibility

### 3. Execute
- Click **Queue Prompt** (Ctrl+Enter)
- Wait ~2–5 minutes (RTX 4060 Ti 16GB)
- Video appears in Preview node and is auto-saved to `ComfyUI/output/video/`

### 4. Export to API Format
- When satisfied with parameters:
  - **Workflow → Export (API)**
  - Save as: `D:/AI_Ecosystem/03_Workflows/API/Image2Video_LTXV_Meu.json`
  - **Do not overwrite TEMPLATE**

---

## API Automation (Python)

```python
import json
import requests

with open("D:/AI_Ecosystem/03_Workflows/API/Image2Video_LTXV_Meu.json") as f:
    workflow = json.load(f)

# Modify inputs by node ID
workflow["78"]["inputs"]["image"] = "minha_imagem.png"
workflow["6"]["inputs"]["text"] = "nova descricao do movimento"
workflow["77"]["inputs"]["strength"] = 0.15
workflow["72"]["inputs"]["noise_seed"] = 12345

response = requests.post(
    "http://127.0.0.1:8188/prompt",
    json={"prompt": workflow}
)
print(response.json())  # job ID
```

---

## Limitations of LTX 2B v0.9.5

- **Max clip:** ~6 seconds (153 frames @ 24fps). Beyond this, quality degrades.
- **Single image only:** No native multi-keyframe support.
- **VRAM usage:** ~6–8GB at 1024×576; ~10–12GB at 768×960.
- **Motion type:** Best for subtle ambient motion (water, leaves, light). Poor for fast action or rigid structured objects (buildings, furniture).

---

## Related References

- `references/ltx-video-img2vid-setup.md` — Model download links, node verification
- `references/ltx-video-grain-resolution.md` — Resolution sweet spot analysis
- `references/multi-clip-video-architecture.md` — Multi-clip pipeline with ffmpeg crossfade
- `references/storyboard-pipeline-script.md` — Python script for batch clip generation and stitching

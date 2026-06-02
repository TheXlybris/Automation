# IP-Adapter Workflow — Node Structure and API Format

For coherent storyboard image generation using IP-Adapter+ with SDXL.

## Nodes Used (API Format)

| Node ID | Class_type | Purpose | Key Inputs | Key Outputs |
|---------|-----------|---------|-----------|-------------|
| 1 | EmptyLatentImage | Latent canvas | width, height, batch_size | LATENT |
| 4 | CheckpointLoaderSimple | Load SDXL model | ckpt_name | MODEL, CLIP, VAE |
| 6 | CLIPTextEncode | Positive prompt | text, clip | CONDITIONING |
| 7 | CLIPTextEncode | Negative prompt | text, clip | CONDITIONING |
| 8 | VAEDecode | Decode latent→pixels | samples, vae | IMAGE |
| 9 | SaveImage | Save output | images, filename_prefix | – |
| 10 | LoadImage | Load reference image | image (filename) | IMAGE |
| 11 | PrepImageForClipVision | Preprocess for CLIP | image | IMAGE |
| 12 | IPAdapterUnifiedLoader | Load IP-Adapter + CLIP Vision | model, preset | model, ipadapter |
| 13 | IPAdapterAdvanced | Apply image conditioning | model, ipadapter, image, weight, weight_type, combine_embeds, start_at, end_at, embeds_scaling | MODEL |
| 14 | KSampler | Generate with IP-Adapter | model, positive, negative, latent_image, seed | LATENT |

## Node Connections (API Format)

```
4[0] MODEL    → 12[model]
4[1] CLIP     → 6[clip], 7[clip]
4[2] VAE      → 8[vae]

1[0] LATENT   → 14[latent_image]
6[0] CONDITIONING → 14[positive]
7[0] CONDITIONING → 14[negative]

10[0] IMAGE   → 11[image]
11[0] IMAGE   → 13[image]
12[0] model   → 13[model]
12[1] ipadapter → 13[ipadapter]
13[0] MODEL   → 14[model]

14[0] LATENT  → 8[samples]
8[0] IMAGE    → 9[images]
```

## Critical Fields for Automation

Node 10 (LoadImage):
```json
{"inputs": {"image": "cena_master_cascata.png"}}
```
→ Change this to point at the scene master image.

Node 6 (CLIPTextEncode, positive):
```json
{"inputs": {"text": "prompt describing the NEW camera angle/distance"}}
```
→ Describe the NEW view (close-up, macro, pan) while keeping location keywords.

Node 12 (IPAdapterUnifiedLoader):
```json
{"inputs": {"preset": "PLUS (high strength)"}}
```
→ Options: `STANDARD (medium strength)`, `PLUS (high strength)`, `VIT-G (medium strength)`.

Node 13 (IPAdapterAdvanced):
```json
{"inputs": {
  "weight": 0.8,
  "weight_type": "linear",
  "combine_embeds": "concat",
  "start_at": 0.0,
  "end_at": 1.0,
  "embeds_scaling": "V only"
}}
```
→ `weight` controls adherence: 0.3–0.5 = subtle influence, 0.6–0.8 = balanced, 0.9–1.0 = very strong.
→ `weight_type`: see skill main doc for full list.

Node 14 (KSampler):
```json
{"inputs": {
  "seed": 453733129827348,
  "steps": 70,
  "cfg": 8,
  "denoise": 1
}}
```
→ For IP-Adapter, `denoise=1.0` is correct. The image influence comes from the IP-Adapter injection, not from low denoise.

## Preset → Model File Mapping

| Preset Selection | SDXL Model File | CLIP Vision Required |
|-----------------|-----------------|---------------------|
| `STANDARD (medium strength)` | `ip-adapter_sdxl_vit-h.safetensors` | ViT-H/14 |
| `PLUS (high strength)` | `ip-adapter-plus_sdxl_vit-h.safetensors` | ViT-H/14 |
| `VIT-G (medium strength)` | `ip-adapter_sdxl.safetensors` | ViT-bigG/14 |

**For THE RENDER WAVE:** Always use `PLUS (high strength)` for best scene coherence.

## Resolution

User preference: **2400×1350** (widescreen, 16:9 aspect ratio, higher quality than 1024).

Set in Node 1:
```json
{"inputs": {"width": 2400, "height": 1350, "batch_size": 1}}
```

## File Paths

| File | Path |
|------|------|
| API workflow (flat dict) | `D:/AI_Ecosystem/03_Workflows/API/Text2Image_IPAdapter_Coherent_API.json` |
| UI workflow (nodes+links) | `D:/AI_Ecosystem/03_Workflows/ComfyUI_Text2Image_IPAdapter_Coherent.json` |
| IP-Adapter model (PLUS) | `D:/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors` |
| IP-Adapter model (STANDARD) | `D:/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/models/ipadapter/ip-adapter_sdxl_vit-h.safetensors` |
| CLIP Vision encoder | `D:/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/models/clip_vision/ViT-H-14_s32B_b79K.safetensors` |
| Custom node source | `https://github.com/cubiq/ComfyUI_IPAdapter_plus.git` |

## Automation Script Pattern (Conceptual)

To generate N coherent storyboard frames from 1 master image:

```python
import json, requests, time

MASTER_IMAGE = "cena_master_cascata.png"
SCENES = [
    {"camera": "wide shot, full waterfall scene", "filename": "scene_01_wide"},
    {"camera": "medium shot, waterfall cascading over mossy rocks", "filename": "scene_02_medium"},
    {"camera": "close-up, crystal clear water droplets sparkling", "filename": "scene_03_close"},
    {"camera": "macro, wildflowers swaying near the pool", "filename": "scene_04_macro"},
]

with open("03_Workflows/API/Text2Image_IPAdapter_Coherent_API.json") as f:
    workflow = json.load(f)

for scene in SCENES:
    wf = json.loads(json.dumps(workflow))  # deep copy
    wf["10"]["inputs"]["image"] = MASTER_IMAGE
    wf["6"]["inputs"]["text"] = f"masterpiece, best quality, photorealistic, {scene['camera']}"
    wf["9"]["inputs"]["filename_prefix"] = scene["filename"]
    
    # Optional: vary seed for variety while keeping coherence via IP-Adapter
    # wf["14"]["inputs"]["seed"] = generate_new_seed()
    
    resp = requests.post("http://192.168.144.1:8188/prompt", json={"prompt": wf})
    print(f"Queued: {scene['filename']} — {resp.json()}")
    time.sleep(2)  # small delay between submissions
```

Key insight: IP-Adapter provides coherence; varying the prompt provides camera angles; varying seed provides variety within coherence bounds.

## Model Installation Checklist

- [ ] `git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git` into `custom_nodes/`
- [ ] Download `ip-adapter-plus_sdxl_vit-h.safetensors` to `models/ipadapter/`
- [ ] Download `ip-adapter_sdxl_vit-h.safetensors` to `models/ipadapter/` (fallback)
- [ ] Download `model.safetensors` from HF `h94/IP-Adapter` image_encoder to `models/clip_vision/`
- [ ] Rename CLIP vision model to include `ViT-H-14` or `ViT-H` pattern
- [ ] Restart ComfyUI server
- [ ] Verify nodes appear in ComfyUI: search "ipadapter" in node menu

## Pitfall — `get_clipvision_file()` regex

The `IPAdapterUnifiedLoader` node searches `models/clip_vision/` with a regex pattern:
```python
pattern = r'(ViT.H.14.*s32B.b79K|ipadapter.*sd15|sd1.?5.*model)\.(bin|safetensors)'
```

**The CLIP vision model filename MUST match this pattern.** A file named `model.safetensors` alone will NOT be found. It must contain `ViT-H-14` (or `ViT-H` with some variant).

Recommended names:
- `ViT-H-14_s32B_b79K.safetensors` ✅ (matches pattern)
- `ViT-H-14.safetensors` ✅
- `model.safetensors` ❌ (does NOT match)
- `sigclip_vision_patch14_384.safetensors` ❌ (different model entirely)

## Pitfall — IP-Adapter weight too high

If `weight > 1.0` (max is 5.0 but rarely useful), the generated image can become a near-clone of the reference. For storyboard coherence, 0.6–0.8 is the sweet spot. Below 0.5, coherence weakens; above 1.0, the model loses prompt adherence.

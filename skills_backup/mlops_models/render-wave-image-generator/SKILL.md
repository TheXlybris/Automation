---
name: render-wave-image-generator
category: mlops_models
trigger: "THE RENDER WAVE project — image generation via ComfyUI API, video loop generation via LTX Video 2B, and related pipeline automation. Also covers post-session file corruption recovery, script audit, and git rollback procedures."
author: Luís Batista
version: 6.4
created: 2026-05-07
updated: 2026-05-22
updated: 2026-05-14
updated: 2026-05-11
description: "Pipeline completo THE RENDER WAVE: geração de imagens (ComfyUI API), vídeo-loops (LTX Video 2B), e setup de modelos. Inclui decisão arquitetural de symlink, reescrita-de-raiz em vez de patches, WSL↔Windows networking, e protocolo de recuperação após corrupção por outro modelo."
---

# 📝 DESCRIÇÃO

[... conteúdo existente mantido ...]

## LTX Video 2B — Grain and Resolution Sweet Spot

**Finding (2026-05-11):** LTX Video 2B generates best quality at **1024×576** output. 2048×1152 produces heavy grain, canvas texture, banding, and painterly artifacts. Visual frame analysis confirmed: Video 02/03 at 2048×1152 show pervasive multicolored speckles, canvas-like texture overlay, soft edges, and watercolor-like degradation. Video 04 at 1024×576 is exceptionally sharp with zero noise and excellent detail definition.

**Confirmed parameters for production:**
- Resolution: **1024×576** (never 2048×1152)
- `strength=0.10` (less noise injection than 0.15)
- `steps=50` (higher than default 30 for cleaner output)
- `length=153` frames (~6.4s at 24fps)
- Post-generation upscale: ffmpeg lanczos to 2560×1440:

**Video quality analysis method:** Extract frames with ffmpeg (`ffmpeg -ss 00:00:03 -vframes 1`) then analyze visually for grain, artifacts, sharpness. Frame extraction at 1s, 3s, 5s gives representative sample of temporal consistency.

## Metadata Extraction from MP4 (2026-05-22)

[... existing content unchanged ...]

## MusicGen Audio Integration (2026-05-25)

MusicGen via `ComfyUI-MusicGen-HF` custom node generates ambient background music loops. These feed audio-reactive visuals in TouchDesigner.

**Pipeline:**
1. Generate 10-second loops with MusicGen Small (max ~30s per run)
2. Save as WAV via `SaveAudioStandalone`
3. Concatenate N loops with ffmpeg crossfade into 8-hour tracks
4. Normalize + convert to MP3 320k

**Custom node install:**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ebrinz/ComfyUI-MusicGen-HF.git
cd ComfyUI-MusicGen-HF && pip install -r requirements.txt
```

**Key parameters:**
- `model_size`: "small" (3GB, ~10s gen) / "medium" / "large"
- `duration`: 10.0 (seconds, max ~30 for small)
- `guidance_scale`: 3.0 (2.5–3.5 for ambient)
- `max_new_tokens`: 256 (512+ for longer)
- `temperature`: 1.0 (0.8–1.2 for ambient)

**Workflow JSON structure (no SD nodes):**
```json
{
  "1": {
    "inputs": {
      "model_size": "small", "duration": 10.0,
      "guidance_scale": 3.0, "do_sample": true,
      "max_new_tokens": 256, "seed": 42,
      "prompt": "ambient thunderstorm, rain, seamless loop",
      "temperature": 1.0, "duration_override": 0.0
    },
    "class_type": "HuggingFaceMusicGen"
  },
  "2": {
    "inputs": {
      "audio": ["1", 0],
      "filename_prefix": "track",
      "format": "wav", "quality": "320k"
    },
    "class_type": "SaveAudioStandalone"
  }
}
```

For full parameter reference, prompts by scene, and 8h concatenation strategy, see `references/musicgen-integration.md` and `references/comfyui-audio-workflows.md` (under the `comfyui` skill).

**Extraction method:**
```bash
# Metadata is in stderr, not stdout
ffmpeg -i video.mp4 -f ffmetadata - 2>&1 | grep -o 'prompt={.*}'
```

**Python recovery:**
```python
import subprocess, json

def extract_params(mp4_path):
    stderr = subprocess.run(["ffmpeg","-i",mp4_path], capture_output=True, text=True).stderr
    idx = stderr.find('prompt={')
    json_str = stderr[idx+7:]
    braces, end, in_str, esc = 0, 0, False, False
    for i,c in enumerate(json_str):
        if esc: esc=False; continue
        if c=='\\': esc=True; continue
        if c=='"' and not esc: in_str=not in_str; continue
        if not in_str:
            if c=='{': braces+=1
            if c=='}': braces-=1
            if braces==0: end=i+1; break
    workflow = json.loads(json_str[:end])
    return {
        "strength": workflow["77"]["inputs"]["strength"],
        "seed": workflow["72"]["inputs"]["noise_seed"],
        "cfg": workflow["72"]["inputs"]["cfg"],
        "steps": workflow["71"]["inputs"]["steps"],
        "fps": workflow["80"]["inputs"]["fps"],
        "positive": workflow["6"]["inputs"]["text"],
        "negative": workflow["7"]["inputs"]["text"],
        "input_image": workflow["78"]["inputs"]["image"],
    }
```

**Limitations:** Not all MP4s embed metadata; UI-format workflows may not include it. This is a fallback, not primary record-keeping.

## Hallucinated Text / Fake Watermarks (2026-05-22)

LTX Video 2B at strength >= 0.10 often generates fake artist signatures or text-like artifacts in corners (e.g., "AEDRIN RONPEROSKO" in ComfyUI_00015_.mp4). These are training-data artifacts, not real watermarks.

**Negative prompt defense:**
```
watermark, signature, text, letters, inscription, logo, words, artist name,
signed, copyright, trademark, caption, subtitle, distorted text, illegible writing
```

**Additional strategies:**
- Lower strength (0.05-0.08) reduces text probability
- Add to positive: `clean image, no text, no writing, no signature`
- Avoid style triggers: `artstation`, `deviantart`, `concept art by`
- Post-detection: extract middle frame with ffmpeg, zoom corners 200%

Details in `references/ltx-video-grain-resolution.md`.

## Saving Prompts Alongside Videos
[... resto do conteúdo mantido ...]

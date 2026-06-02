---
topic: "Basic ComfyUI API Image Generation — Session-Specific Reference"
description: "Minimal valid ComfyUI API workflow JSON for text-to-image via WSL, with common validation pitfalls. Condensed from the comfyui-generate-image session."
scope: comfyui, api, text2image, wsl, troubleshooting
---

# Basic ComfyUI API Image Generation (Session Reference)

This reference condenses the validated `comfyui-generate-image` session into a
minimal, reusable recipe. It is intentionally narrower than the full Render Wave
pipeline documented in the main SKILL.md.

## Auto-Detect Windows Host IP from WSL

```python
import subprocess, os

def get_host_ip() -> str:
    try:
        result = subprocess.run(
            ["ip", "route"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if line.startswith("default"):
                parts = line.split()
                if "via" in parts:
                    return parts[parts.index("via") + 1]
    except Exception:
        pass
    return os.environ.get("COMFYUI_HOST_IP", "127.0.0.1")

COMFYUI_URL = f"http://{get_host_ip()}:8188"
```

## Minimal Valid Workflow JSON (API Format)

```python
workflow = {
    "prompt": {
        "3": {
            "inputs": {"text": "<positive prompt>", "clip": ["5", 1]},
            "class_type": "CLIPTextEncode",
        },
        "4": {
            "inputs": {"text": "low quality, blurry, ugly", "clip": ["5", 1]},
            "class_type": "CLIPTextEncode",
        },
        "5": {
            "inputs": {"ckpt_name": "model.safetensors"},
            "class_type": "CheckpointLoaderSimple",
        },
        "6": {
            "inputs": {"width": 1024, "height": 576, "batch_size": 1},
            "class_type": "EmptyLatentImage",
        },
        "7": {
            "inputs": {"samples": ["9", 0], "vae": ["5", 2]},
            "class_type": "VAEDecode",
        },
        "8": {
            "inputs": {"images": ["7", 0], "filename_prefix": "output_prefix"},
            "class_type": "SaveImage",
        },
        "9": {
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 8.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["5", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["6", 0]
            },
            "class_type": "KSampler",
        }
    }
}
```

## Common Validation Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| `filename_prefix missing` | `SaveImage` node lacks `filename_prefix` | Inject `"filename_prefix": "prefix"` into node `"8"` |
| `Required input is missing: ckpt_name` | Used `model_name` instead of `ckpt_name` | Use `ckpt_name` in `CheckpointLoaderSimple` |
| `Return type mismatch (LATENT vs CLIP)` | Connected `clip` output to wrong input | Connect `clip` only from `CheckpointLoaderSimple` output index 1 |
| `Connection refused` | ComfyUI not listening on `0.0.0.0` or wrong IP | Use detected host IP, ensure `--listen` is set |
| `Exception when validating node: 7` | Workflow JSON has structural issues | Re-export from ComfyUI UI to guarantee validity |

## Script Stub

A runnable Python stub (with hardcoded Portuguese comments from the original
session artifact) is preserved below for reference. In production, prefer the
modular `generate_image.py` from the Render Wave pipeline.

```python
import requests, json, os

COMFYUI_URL = "http://192.168.144.1:8188"
PROMPT = "Uma paisagem tranquila ao pôr do sol, estilo anime"
MODEL = "leosamsHelloworldXL_helloworldXL70.safetensors"
WIDTH, HEIGHT = 1024, 768
OUTPUT_PATH = "/mnt/d/AI_Ecosystem/04_Data/images/"

WORKFLOW = {  # minimal workflow as shown above
    "prompt": { ... }
}

resp = requests.post(f"{COMFYUI_URL}/prompt", json=WORKFLOW)
if resp.status_code == 200:
    print("Workflow submitted.")
else:
    print(f"Error {resp.status_code}: {resp.text}")
```

## When to Use This Reference

- Quick one-off image generation without the full Render Wave pipeline.
- Copy-paste starting point when the full pipeline scripts haven't been set up yet.
- Debugging a "Connection refused" or validation error in a minimal setup.

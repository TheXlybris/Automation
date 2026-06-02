# LTX Video — Metadata Extraction from MP4

**Date:** 2026-05-22
**Context:** THE RENDER WAVE — recovering generation parameters from ComfyUI output MP4s when no separate .txt metadata was saved.

## Problem

The user generates videos via ComfyUI but does not always save a separate `.txt` metadata file alongside the MP4. Days later, they want to reproduce or debug a video but have lost the exact parameters (strength, seed, prompt, etc.).

**Solution:** ComfyUI embeds the **entire workflow JSON** into the MP4's metadata stream when using `SaveVideo` node.

## Extraction Method

### Using ffmpeg (stderr capture)

```bash
ffmpeg -i video.mp4 -f ffmetadata - 2>&1 | grep -o 'prompt={.*}'
```

**Important:** The metadata is embedded in the **stderr** output of ffmpeg, not stdout. The `ffmetadata` format flag causes ffmpeg to dump the embedded metadata to stderr alongside the video info.

### Python extraction (WSL-safe)

```python
import subprocess, json

def extract_comfyui_params(mp4_path: str) -> dict:
    """Extract ComfyUI workflow parameters from MP4 metadata."""
    result = subprocess.run(
        ["ffmpeg", "-i", mp4_path],
        capture_output=True, text=True
    )
    stderr = result.stderr
    
    # Find prompt= JSON block
    idx = stderr.find('prompt={')
    if idx == -1:
        return {"error": "No prompt metadata found in MP4"}
    
    # Extract balanced JSON
    json_str = stderr[idx + 7:]  # after 'prompt='
    braces = 0
    end = 0
    in_str = False
    escape = False
    
    for i, c in enumerate(json_str):
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_str = not in_str
            continue
        if not in_str:
            if c == '{': braces += 1
            if c == '}': braces -= 1
            if braces == 0:
                end = i + 1
                break
    
    json_str = json_str[:end]
    try:
        workflow = json.loads(json_str)
        
        # Extract key parameters from known node IDs (LTX Video workflow)
        params = {}
        n77 = workflow.get('77', {}).get('inputs', {})
        n6 = workflow.get('6', {}).get('inputs', {})
        n7 = workflow.get('7', {}).get('inputs', {})
        
        params['strength'] = n77.get('strength')
        params['width'] = n77.get('width')
        params['height'] = n77.get('height')
        params['length'] = n77.get('length')
        params['cfg'] = workflow.get('72', {}).get('inputs', {}).get('cfg')
        params['steps'] = workflow.get('71', {}).get('inputs', {}).get('steps')
        params['fps'] = workflow.get('80', {}).get('inputs', {}).get('fps')
        params['seed'] = workflow.get('72', {}).get('inputs', {}).get('noise_seed')
        params['sampler'] = workflow.get('73', {}).get('inputs', {}).get('sampler_name')
        params['positive_prompt'] = n6.get('text', '')
        params['negative_prompt'] = n7.get('text', '')
        params['input_image'] = workflow.get('78', {}).get('inputs', {}).get('image', '')
        params['model'] = workflow.get('44', {}).get('inputs', {}).get('ckpt_name', '')
        
        return params
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse metadata JSON: {e}"}
```

### Key parameters from LTX Video workflow nodes

| Node ID | Class | Extracted params |
|---------|-------|------------------|
| `"6"` | CLIPTextEncode | `positive_prompt` (text field) |
| `"7"` | CLIPTextEncode | `negative_prompt` (text field) |
| `"44"` | CheckpointLoaderSimple | `model` (ckpt_name) |
| `"72"` | SamplerCustom | `seed`, `cfg` |
| `"71"` | LTXVScheduler | `steps` |
| `"73"` | KSamplerSelect | `sampler_name` |
| `"77"` | LTXVImgToVideo | `width`, `height`, `length`, `strength`, `batch_size` |
| `"78"` | LoadImage | `input_image` filename |
| `"80"` | CreateVideo | `fps` |

## Limitations

1. **Not all MP4s have metadata** — if the `SaveVideo` node didn't include the workflow, extraction fails
2. **UI-format workflows may not embed** — only API-format exports include the full prompt dict
3. **Workflow version drift** — if the user re-exported the workflow after generation, node IDs may differ from the embedded version
4. **Large metadata** — the full workflow JSON can be 50KB+ embedded in the MP4; this increases file size slightly

## Prevention: Save metadata alongside video

See `references/saving-prompts-from-comfyui.md` for the recommended `.txt` sidecar pattern. The embedded metadata is a **fallback**, not the primary record.

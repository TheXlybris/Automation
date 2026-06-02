# run_img2vid.py — Lightweight AnimateDiff img2vid Script

Single-purpose script: loads a ComfyUI API workflow JSON, injects parameters, submits, polls, and returns the output video path.

## Architecture

```
load_workflow()     → deep copy → inject_parameters() → submit_prompt() → poll_for_results() → extract_output_path()
```

## Key Functions

### `load_workflow()`
- Validates file exists and is valid JSON
- Prints node count for debugging
- Returns dict (not string)

### `inject_parameters(workflow, args)`
- **Node 2** (`CLIPTextEncode` positive): Injects adapted prompt (removes photo terms, adds motion vocabulary)
- **Node 8** (`CLIPTextEncode` negative): Injects negative prompt
- **Node 4** (`KSampler`): Injects seed (auto-random if -1), steps, cfg, denoise
- **Node 12** (`LoadImage`): Injects image filename (must exist in ComfyUI/input/)
- **Returns modified workflow dict**

### `copy_input_image(source, target_filename)`
- Copies source image into `ComfyUI/input/` if not already there
- Handles full paths or relative filenames
- Returns target filename

### `submit_prompt(workflow)`
- POST to `http://192.168.144.1:8188/prompt`
- Validates `prompt_id` exists in response
- Handles HTTP errors

### `poll_for_results(prompt_id)`
- Polls `/history/{prompt_id}` every 2s for up to 15 min
- **Error detection**: Checks `status_str == "error"`, prints detailed messages
- **Success detection**: Looks for `"7"` node with `gifs` or `images` keys
- **Progress indicator**: Prints `.` every 10s + elapsed time on completion
- Returns list of output items

### `extract_output_path(video_items)`
- Constructs absolute path from `subfolder` + `filename`
- Verifies file exists and reports size
- Returns full path

## CLI Arguments

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `--input-image` | str | required | Image filename (copied to input/ if not there) |
| `--prompt` | str | required | Positive prompt (adapted for video) |
| `--negative` | str | `""` | Negative prompt |
| `--seed` | int | -1 | Random if -1 |
| `--steps` | int | 25 | Sampling steps |
| `--cfg` | float | 8.0 | CFG scale |
| `--denoise` | float | 1.0 | 1.0=full motion, 0.65=subtle |

## Testing

```bash
python3 run_img2vid.py \
  --input-image base_landscape.png \
  --prompt "river flowing through meadow" \
  --denoise 1.0 \
  --steps 25
```

## Known Issue (2026-05-11)

With `VideoLoop_I2V.json` + denoise=1.0, the script completes successfully but produces a 0-second, 0.56 MB MP4 with no visible video. The ComfyUI UI shows the workflow running and the VHS_VideoCombine node appears to complete, but the output is effectively empty.

**Root cause diagnosed:** The workflow is actually **txt2vid disguised as img2vid**. The VAEEncode produces only **1 latent** (batch=1), and denoise=1.0 tells the KSampler to ignore the input latent entirely and generate from pure noise. With only 1 latent going in and no multi-frame generation mechanism, the output is 1 frame.

**AnalyseDiff img2vid requires:** A multi-frame latent generation mechanism (typically via `ADE_StandardStaticContextOptions` or similar nodes that inject multiple frames into the latent space). The current workflow simply encodes a single image and passes it to KSampler — this is mechanically identical to txt2vid with an initial latent, not true img2vid.

**Why denoise=1.0 is correct for AnimateDiff img2vid conceptually but fails here:**
Conceptually, AnimateDiff img2vid uses the motion module to generate multiple frames from an encoded image. However, this requires the pipeline to generate a **sequence of latents** (typically via `context_length` frames produced by the motion module), not a single latent. The current workflow produces only 1 latent → 1 frame regardless of denoise value.

**Correct img2vid architecture with AnimateDiff:**
```
LoadImage -> VAEEncode -> produces MULTIPLE latents (via motion module context)
                          |
                          v
                    KSampler + AnimateDiff -> generates N frames
                          |
                          v
                    VADecode (batch of N frames)
                          |
                          v
                    VHS_VideoCombine -> MP4
```

The current workflow produces only 1 latent because it lacks the node that expands the single image into multiple frame latents for the motion module to process.

**Next steps:** Abandon AnimateDiff img2vid approach and evaluate alternatives (FramePack I2V, LTX Video, Wan 2.1 img2vid, or FFmpeg Ken Burns as fallback).

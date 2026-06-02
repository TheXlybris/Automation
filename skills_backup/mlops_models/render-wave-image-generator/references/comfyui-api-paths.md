# ComfyUI Path Resolution for WSL + Windows Host

## Problem
ComfyUI runs on Windows host but automation scripts run in WSL Linux. Paths must resolve correctly in both environments.

## Architecture
- **WSL** sees Windows paths via `/mnt/c/`, `/mnt/d/`, etc.
- **Windows** ComfyUI runs with `--listen 0.0.0.0 --port 8188`
- **WSL** accesses ComfyUI API via host IP (e.g., `192.168.144.1`)

## Key Paths

| Environment | Path | Purpose |
|-------------|------|---------|
| Windows | `D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\output\` | Actual output directory |
| WSL | `/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output/` | Symlink target (read-only access) |
| WSL | `/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/input/` | Where images must be placed before LoadImage |

## Rule: Never Move ComfyUI Outputs
Moving or copying files from `output/` breaks internal references (hash-based filenames, subfolder associations). Always use symlinks.

## API Endpoints
- `POST http://192.168.144.1:8188/prompt` — Submit workflow
- `GET http://192.168.144.1:8188/history/{prompt_id}` — Poll for results
- `GET http://192.168.144.1:8188/system_stats` — Health check

## Workflow Node IDs for img2vid (VideoLoop_I2V.json)
| Node | Class | Field to Inject |
|------|-------|-----------------|
| 2 | CLIPTextEncode | `inputs.text` (positive prompt, adapted for video) |
| 4 | KSampler | `inputs.seed`, `inputs.steps`, `inputs.cfg`, `inputs.denoise` |
| 7 | VHS_VideoCombine | Output node (produces MP4 in `outputs.7.gifs`) |
| 8 | CLIPTextEncode | `inputs.text` (negative prompt) |
| 12 | LoadImage | `inputs.image` (filename in input/) |
| 13 | VAEEncode | No injection needed (auto-wired from 12) |
| 11 | ADE_LoopedUniformContextOptions | No injection needed (fixed: context_length=16, closed_loop=true) |

## Known Issues
1. **0-second MP4 outputs**: The VideoLoop_I2V.json workflow completes but produces empty videos. Likely causes:
   - Incompatible motion module (mm_sdxl_v10_beta.ckpt) with img2vid mode
   - VHS_VideoCombine misconfiguration (frame_rate=8 may be too low for MP4 encoding)
   - Missing frame count specification in context options
2. **Image resolution**: Must be 512×512 for AnimateDiff img2vid (the VAEEncode node hardcodes this)
3. **LoadImage requires image in input/**: The image must be copied to `ComfyUI/input/` before the workflow runs

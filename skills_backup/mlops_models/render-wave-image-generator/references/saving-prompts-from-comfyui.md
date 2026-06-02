# Saving Prompts from ComfyUI Video Generation

**Date:** 2026-05-11
**Context:** THE RENDER WAVE — need to save positive/negative prompts alongside each generated video

## Problem

When generating videos via ComfyUI (UI or API), the prompts used are embedded in the workflow JSON but not saved as a separate human-readable file. For THE RENDER WAVE pipeline, we need a `.txt` file with the same base name as the video (e.g., `ComfyUI_00005_.mp4` + `ComfyUI_00005_.txt`).

## Options

### Option A: Custom Node in ComfyUI UI

**Node:** `SaveTextFile` from `Yahweasel/ComfyUI-Save-Text`
- GitHub: https://github.com/Yahweasel/ComfyUI-Save-Text
- Install:
  ```bash
  cd ComfyUI/custom_nodes
  git clone https://github.com/Yahweasel/ComfyUI-Save-Text.git
  ```
- Node inputs: `text` (STRING) + `filename` (STRING)
- Output: writes `output/{filename}.txt` in ComfyUI's output directory
- **Limitation:** Hardcoded `output/` path. Video goes to `output/video/`, txt goes to `output/` — different subdirectories.

**Verdict:** Not ideal for THE RENDER WAVE. Better to handle saving in the API script.

### Option B: SaveTextFile node from ComfyUI-KJNodes or ComfyUI_Swwan

Checked installed custom nodes:
- ComfyUI-essentials — no save text node
- ComfyUI-KJNodes — no save text node (checked `nodes/nodes.py`)
- ComfyUI_Swwan — `io_nodes.py` only handles image saving, no text output
- ComfyUI-VideoHelperSuite — no save text node

**Verdict:** None of the currently installed nodes support saving arbitrary text to a file with custom path.

### Option C: API Script Side (RECOMMENDED)

The Python script that submits the workflow via API knows exactly:
- The positive prompt injected into the workflow
- The negative prompt injected into the workflow
- All generation parameters (strength, steps, seed, resolution, etc.)
- The output video filename (from ComfyUI history API)

**Implementation:**
```python
def save_prompts(video_path, positive, negative, params):
    """Save prompts to a .txt with same base name as the video."""
    txt_path = video_path.replace(".mp4", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"=== Prompts ===\n")
        f.write(f"Positive: {positive}\n")
        f.write(f"Negative: {negative}\n\n")
        f.write(f"=== Parameters ===\n")
        for k, v in params.items():
            f.write(f"{k}: {v}\n")
        f.write(f"\n=== Workflow ===\n")
        f.write(f"{params.get('workflow', 'unknown')}\n")
    print(f"[SAVE] Prompts saved to: {txt_path}")
```

**Advantages:**
- Same directory as the video
- Same base filename (just .txt instead of .mp4)
- Includes ALL parameters, not just prompts
- No ComfyUI custom node needed
- Works with both manual runs and automation

**Location:** The .txt should be saved in the same folder as the MP4 (`ComfyUI/output/video/` or `ComfyUI/output/`).

## Decision

For THE RENDER WAVE: **Use Option C (API script side)**. Integrate `save_prompts()` into `run_ltx_video.py`. This avoids installing yet another custom node and ensures the .txt is always co-located with the .mp4.
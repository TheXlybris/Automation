# Narrative Multi-Keyframe Video Generation for THE RENDER WAVE

**Context:** THE RENDER WAVE currently generates relaxing ambient loops (single image → subtle motion). The user wants to evolve to **cinematic storytelling**: multiple keyframe images stitched into a narrative sequence with natural camera movement (approach waterfall, pan to flowers, hand with butterfly, return to start).

**Current hardware constraint:** RTX 4060 Ti 16GB. Current model: LTX Video 2B v0.9.5.

---

## Technical Reality Check: What LTX 2B v0.9.5 Actually Supports

**It does NOT support multi-image input natively.** The native ComfyUI nodes (`LTXVImgToVideo`, `LTXVConditioning`, `LTXVScheduler`) accept exactly **one image** as conditioning. The `strength` parameter (0.05–0.15) controls how much the original image is preserved vs. how much temporal noise is injected.

**What this means:** You cannot feed 5 images to LTX 2B and say "morph from image 1 to image 2 at frame 30, then to image 3 at frame 60..." The model was trained for single-image conditioning.

**The `LTX2.3(MF-javano2604.2).json` workflow trap:** This workflow references `MultiImageLoader` and `LTXSequencer` nodes. These nodes do **NOT exist** in the currently installed custom_nodes. They belong to a newer LTX 2.3 custom node pack (ComfyUI-LTXVideo or similar) that is not installed. The workflow is a dead reference.

---

## Four Technical Approaches (Ranked by Viability)

### Approach A: Segmented Generation + FFmpeg Concat (RECOMMENDED — Works Now)

**Idea:** Break the 60-second narrative into N segments (e.g., 5 segments × 12 seconds each). Each segment uses 1 keyframe image as input to LTX 2B img2vid. Concatenate segments with FFmpeg crossfade.

**Pipeline:**
1. Generate 5 keyframe images (cascade, flowers, butterfly-on-finger, flower field, wide shot)
2. For each image: run LTX 2B img2vid → 12s clip with ambient motion
3. Concatenate: `ffmpeg concat demuxer` with 1-second crossfade between clips
4. Result: 60s seamless(ish) narrative video

**Pros:**
- ✅ Uses existing LTX 2B model (no new downloads)
- ✅ No new custom nodes needed
- ✅ VRAM footprint identical to current img2vid
- ✅ Each segment can have custom prompt adapted to that image

**Cons:**
- ❌ No true camera movement between segments (jump cut, not smooth pan)
- ❌ Crossfade is a transition, not a natural camera path
- ❌ Temporal continuity between segments is manual (no AI coherence)

**Mitigation for smoother transitions:**
- Use `ffmpeg xfade` with `fade` or `wipe` transition
- Generate intermediate "bridge" images between keyframes (img2img with 0.3 denoise)
- Keep prompts consistent across segments (same lighting, atmosphere)

---

### Approach B: Native Multi-Keyframe with LTX 2.3 (Future — Requires Upgrade)

**Idea:** LTX Video 2.3/2.4 (and the 13B models) support multi-keyframe conditioning natively. Install the `ComfyUI-LTXVideo` custom node pack and use the `LTXVImgToVideoInplace` or `LTXSequencer` nodes.

**What changes:**
1. Download newer LTX model: `ltxv-2b-0.9.8-distilled.safetensors` (or 13B if VRAM allows)
2. Install custom node pack: `ComfyUI-LTXVideo` from GitHub
3. Use workflow with `MultiImageLoader` + `LTXSequencer` nodes (they will actually exist)
4. Define keyframe schedule: image A at frame 0, image B at frame 180, image C at frame 360...
5. Model interpolates motion between keyframes automatically

**Pros:**
- ✅ True cinematic interpolation between keyframes
- ✅ Natural camera movement implied by the model
- ✅ Single inference pass (no stitching)

**Cons:**
- ❌ Requires new model download (~4-8GB depending on version)
- ❌ Requires new custom node pack (installation risk)
- ❌ LTX 13B requires >16GB VRAM (distilled 2B might work)
- ❌ Learning curve: new nodes, new parameters

**VRAM reality:** The 2B distilled model at 0.9.8 might fit in 16GB. The 13B models will not. Test with 2B first.

**Research findings from web search (2026-05-12):**
- Reddit r/comfyui: "ComfyUI Nodes for Filmmaking (LTX 2.3 Shot Sequencing)" — mentions FFLF (First Frame Last Frame) and multi-keyframe support
- YouTube: "LTX 2.3 Multi Keyframe Guide Image + Text to Video" and "Create Better AI Videos With LTX 2.3 Using Multi Keyframe Technique"
- GitHub: `Lightricks/ComfyUI-LTXVideo` has example workflows for `LTX-2.3_I2V_Multi_Key_Frame.json`
- HuggingFace: LTX-Video model card lists `ltxv-2b-0.9.8-distilled.yaml` as "Ideal for light VRAM usage"

---

### Approach C: Image-to-Video Loop with Motion LoRA (Limited)

**Idea:** Use the existing AnimateDiff Evolved setup with motion LoRAs (ZoomIn, ZoomOut, PanLeft, PanRight) to add directed camera movement to a single image.

**Limitation:** This gives only ONE type of motion per clip (e.g., zoom in OR pan left). You cannot sequence "approach waterfall → pan right → show hand → return". It is a single continuous motion over one image.

**Use case:** Good for ambient loops, not for narrative storytelling.

---

### Approach D: Post-Production FFmpeg Ken Burns (No AI Motion)

**Idea:** Use ffmpeg's zoompan filter to create Ken Burns-style slow zoom/pan over a static image. No AI motion generation at all.

**Command example:**
```bash
ffmpeg -loop 1 -i image.png -vf "zoompan=z='min(zoom+0.0015,1.5)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080" -t 60 -pix_fmt yuv420p output.mp4
```

**Limitation:** No real motion (ripples, wind, butterfly flapping). Just a camera moving over a photo. Not suitable for THE RENDER WAVE's "living scene" aesthetic.

---

## Recommended Path Forward

**Phase 1 (Now):** Implement Approach A — segmented generation + ffmpeg concat.
- Create `generate_narrative_video.py` script
- Input: list of `(image_path, duration_seconds, prompt_segment)` tuples
- Output: stitched MP4 with crossfades
- Use existing LTX 2B, existing workflows, no new installations

**Phase 2 (Later):** Evaluate Approach B — LTX 2.3 multi-keyframe.
- Only if Phase 1 proves insufficient for storytelling quality
- Requires explicit user approval for model download + custom node install
- Test 2B distilled first; 13B is likely impossible on 16GB

**Phase 3 (Never):** Approaches C and D are too limited for the storytelling goal.

---

## Key Technical Insight: The Prompt Problem

The user's example describes a complex narrative with multiple scenes:
1. Waterfall (wide shot)
2. Pan to flower field
3. Butterfly lands on finger
4. Walk through flower field
5. Return to waterfall (loop)

**This is fundamentally different from a single-scene ambient loop.** The prompt must evolve across the video. Current LTX 2B img2vid uses ONE prompt for the entire clip. A segmented approach allows different prompts per segment, but the model has no "memory" of previous segments.

**Solution for segmented approach:**
- Use consistent base atmosphere across all segment prompts (lighting, color palette, mood)
- Only change the focal subject (waterfall → flowers → butterfly → flowers → waterfall)
- The crossfade transition hides the prompt discontinuity

**Example segment prompts (all sharing the same golden-hour, warm, soft atmosphere):**
- Segment 1 (0–12s): "gentle waterfall cascading over mossy rocks, warm golden light, water droplets sparkling"
- Segment 2 (12–24s): "pan across lush meadow with wildflowers, butterflies fluttering, soft breeze"
- Segment 3 (24–36s): "close-up of a finger extended, butterfly landing gently, delicate wing patterns"
- Segment 4 (36–48s): "walking through flower field at eye level, petals swaying, sunlit path"
- Segment 5 (48–60s): "returning to waterfall view, wide establishing shot, seamless loop"

---

## Workflow Nodes for Segmented Approach

Each segment uses the same LTX 2B img2vid workflow, but with different:
- `LoadImage` node: points to the keyframe image for that segment
- `CLIPTextEncode` (positive): segment-specific prompt
- `LTXVImgToVideo` node: `strength`, `length` tuned per segment

**No new nodes needed.** The existing `Image2Video_LTXV.json` workflow handles each segment individually.

**Concatenation script (Python + ffmpeg):**
```python
import subprocess, tempfile, os

def concat_segments(segment_files, output_path, transition_duration=1.0):
    # Create concat list with crossfade filters
    # ... ffmpeg xfade implementation
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy", output_path
    ])
```

Full implementation pending user decision on Approach A vs B.

---

## Decision Checkpoint (User Must Choose)

| Question | Approach A | Approach B |
|----------|-----------|-----------|
| Works today? | ✅ Yes | ❌ Needs install |
| New model download? | ❌ No | ✅ Yes (~4GB) |
| New custom nodes? | ❌ No | ✅ Yes |
| True camera movement? | ❌ No (crossfade) | ✅ Yes |
| VRAM risk? | ❌ None | ⚠️ Test 2B first |
| Narrative quality? | 🟡 Good | 🟢 Excellent |

**My recommendation:** Start with Approach A. It gives immediate results with zero risk. If the crossfade quality is insufficient, THEN invest in Approach B.

**Never proceed with Approach B without explicit user confirmation:** "Queres que eu descarregue o modelo LTX 2.3 (~4GB) e instale os custom nodes para testar multi-keyframe nativo?"

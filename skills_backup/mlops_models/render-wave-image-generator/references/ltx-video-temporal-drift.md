# LTX Video 2B — Temporal Drift Diagnosis (2026-05-22)

**Date:** 2026-05-22
**Context:** THE RENDER WAVE — user reported video inconsistency; agent diagnosed via frame extraction + vision analysis
**Video analyzed:** `ComfyUI_00013_.mp4` (1024×576, 24fps, 6.4s, ~153 frames)
**Hardware:** RTX 4060 Ti 16GB VRAM

---

## What "Temporal Drift" Looks Like in Practice

Temporal drift in LTX Video 2B is **not subtle flicker or grain** — it is **complete scene metamorphosis**.

### Frame-by-frame degradation observed

| Frame (s) | Scene description |
|-----------|-------------------|
| 0 (start) | Ancient temple ruins in storm, blue lightning, cyan water, stone columns, torch on right |
| 3 (middle)| **Completely different scene** — submerged aqueduct/bridge, central lightning strike, red vegetation left |
| 6 (end) | **Completely different scene** — blue energy vortex with red core, nearly total darkness, architecture reduced to silhouettes |

**Verdict:** The video contains **three entirely different scenes** that morph into each other over 6 seconds. This is not motion within a fixed scene — it is scene-to-scene interpolation masquerading as video.

---

## Root Causes (ranked by impact)

### 1. Strength too high (>0.15)
- LTX Video 2B reconstructs the input image frame-by-frame via diffusion
- `strength` controls noise injection per frame — higher = more "creative freedom"
- At `strength=0.15+`, the model invents new geometry over the original scene
- Each frame is a **re-diffusion** from noise conditioned on the original image, not a **warp** of the original

### 2. Resolution at model limit (1024×576)
- LTX 2B trained on modest resolutions (likely ≤768 native)
- At 1024, the model is already upscaling aggressively; any noise injection amplifies hallucination
- 2048×1152 is even worse (see `ltx-video-grain-resolution.md`)

### 3. Prompt lacks stability anchors
- Without explicit "preserve original composition", "fixed architecture", "subtle ambient motion only", the model interprets the prompt as a **description of a sequence** rather than a **description of motion within a fixed scene**
- The model generates a "story" rather than a "loop"

---

## Diagnosis Method (reproducible)

Use ffmpeg to extract frames at 1-second intervals, then analyze with a vision model:

```bash
# Extract representative frames
mkdir -p /tmp/video_diag && ffmpeg -y -i input.mp4 \
  -vf "select='not(mod(n,24))',scale=iw:ih" \
  -vsync vfr -q:v 1 /tmp/video_diag/frame_%03d.png

# Count frames extracted
ls /tmp/video_diag/frame_*.png | wc -l
```

For a 6s @ 24fps video, this yields ~7 frames (one per second).

**Analysis protocol:**
1. Examine frame 1 (start) — record architecture, light sources, color palette, key objects
2. Examine middle frame(s) — check for morphing, disappearing elements, color shifts
3. Examine final frame — compare to start for structural integrity
4. If ANY major architectural element changes position, disappears, or is replaced, classify as **temporal drift**

---

## Mitigation Strategies (3 tiers)

### Tier 1 — Quick fix (minimal effort, subtle motion)
| Parameter | Change | Effect |
|-----------|--------|--------|
| `strength` | 0.05–0.08 | Dramatically less noise = less drift; motion becomes very subtle (water shimmer, light flicker) |
| Prompt suffix | Add: `preserve original composition, fixed architecture, no structural changes, subtle ambient motion only` | Anchors the model to the original geometry |
| Negative prompt | Add: `scene change, morphing, structural distortion, object disappearance, geometry warp` | Represses drift directly |

**Trade-off:** Motion is barely visible. Best for rigid scenes (interiors, architecture, furniture).

### Tier 2 — Balanced (recommended for nature/organic scenes)
| Parameter | Change | Effect |
|-----------|--------|--------|
| `strength` | 0.10 | Moderate noise; visible ambient motion (leaves, water, clouds) |
| Prompt | Strip photography terms (35mm, 8k, National Geographic); add motion vocabulary per element type | Keeps scene fixed while animating only organic elements |
| IP-Adapter | Load original image via `IPAdapterAdvanced` with weight 0.6–0.8, linear, concat | Forces visual coherence across frames |
| `steps` | 40–50 | More denoising steps = cleaner reconstruction per frame |

**Trade-off:** Good balance. Requires IP-Adapter node installation. See `references/ip-adapter-workflow-nodes.md`.

### Tier 3 — Maximum consistency (slower, best result)
| Approach | Description | Effort |
|----------|-------------|--------|
| **FramePack img2vid** | Single Start image, no End image, `total_second_length=5.0`, `guidance_scale=12.0` | High — requires FramePack wrapper + HunyuanVideo 13B (OOM risk on 16GB) |
| **Multi-clip + crossfade** | Generate 4–6 clips at `strength=0.05` from same image, crossfade in ffmpeg | Medium — no single clip has drift, transitions are artificial but seamless |
| **IP-Adapter + low strength + ping-pong** | IP-Adapter weight 0.9, strength 0.05, then ffmpeg reverse+concat for loop | Medium — static scene with tiny motion, looped perfectly |

---

## When to Accept the Limitation

LTX Video 2B is a **2B parameter model** designed for short (~4s) clips with moderate motion. It is **not** a high-fidelity video consistency engine.

**Accept drift when:**
- The video is abstract/atmospheric and scene metamorphosis is artistically acceptable
- The target is a 4-second social media clip where viewers won't notice mid-clip changes

**Do NOT accept drift when:**
- The goal is a 1-hour ambient loop (drift accumulates and becomes obvious on repeat)
- The scene has narrative or structural identity (a specific temple, room, landscape)
- Brand/project consistency matters (THE RENDER WAVE requires recognizable scenes)

---

## Key Insight: Diffusion-Based Video vs Warp-Based Video

| Property | Diffusion-based (LTX, AnimateDiff, FramePack) | Warp-based (SVD, FFmpeg Ken Burns) |
|----------|----------------------------------------------|-------------------------------------|
| Mechanism | Re-diffuses each latent frame from noise | Warps/wiggles existing pixels |
| Motion richness | High — can generate new motion patterns | Low — limited to geometric transforms |
| Temporal consistency | Poor — each frame is independent generation | Excellent — same pixels, just moved |
| Structural fidelity | Degrades with strength/resolution | Perfect — never changes geometry |
| Best use | Short clips, organic motion | Loops, rigid scenes, long durations |

**For THE RENDER WAVE's 1-hour ambient loops:** Consider combining diffusion clips at very low strength with warp-based transitions, or use multi-clip crossfade to hide the drift boundaries.

---

## Reference

- `references/ltx-video-grain-resolution.md` — companion analysis of resolution/noise trade-offs
- `references/ltx-video-img2vid-setup.md` — full LTX setup and parameters
- `references/ip-adapter-workflow-nodes.md` — IP-Adapter for visual coherence
- `references/multi-clip-video-architecture.md` — multi-clip + crossfade pipeline for 60s loops

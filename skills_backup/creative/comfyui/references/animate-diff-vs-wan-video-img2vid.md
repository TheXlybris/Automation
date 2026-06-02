# AnimateDiff vs Wan 2.1 vs FramePack — Img2Vid on 16 GB VRAM

Session: 2026-05-11  
User: THE RENDER WAVE project  
GPU: NVIDIA RTX 4060 Ti 16 GB

---

## What Failed (AnimateDiff I2V)

### Symptom
Workflow `VideoLoop_I2V.json` executed without error but produced a video
with **Duration: 00:00:00.13** — effectively 1 frame. The VHS_VideoCombine
generated an MP4, but there was no actual motion.

### Root cause
AnimateDiff Evolved requires a **multi-frame latent pipeline** for img2vid.
The workflow received only a single VAE-encoded latent (from one image) and
denoise=1.0 caused the KSampler to ignore even that latent and generate from
noise. Without a proper "sliding window" or "loopback" mechanism to produce
multiple frames from a single image, AnimateDiff falls back to near-static
output.

### Key log line
```
[AnimateDiffEvo] - INFO - Regular sampling activated - latents passed
in (1) less or equal to context_length 16.
```
"Passed in (1)" = 1 latent frame only.

### Verification
```bash
ffprobe -show_streams VideoLoop_00001.mp4
# Duration: 00:00:00.13, bitrate: 37913 kb/s, 8 fps
# → 1 frame total
```

### Conclusion
AnimateDiff Evolved I2V workflows in ComfyUI are **not a simple img→KSampler
→Video path**. They require custom nodes (loopback, sliding window,
context concatenation) that were not present in the tested workflow.
The old workflow `Videoloop_img2vid_landscape.json` used `denoise=0.65`
at frame_rate=16 but was deprecated for the same reason.

---

## Alternatives Explored

| Model | Size | VRAM (est.) | Viable for 16 GB? | Notes |
|-------|------|-------------|-------------------|-------|
| **AnimateDiff Evolved I2V** | motion module + SDXL | ~12–16 GB | ❌ No | Requires multi-frame latent loop. Produces 1 frame without it. |
| **LTX Video** | ~3B params | ~6–10 GB | ✅ Yes (not tested) | Most promising fallback. Has native ComfyUI node. Designed for efficiency. |
| **CogVideoX-5B** | 5B params | ~10–14 GB | ⚠️ Maybe with FP8 | THUDM model. 5B is borderline on 16 GB. |
| **Wan 2.1 I2V** | 14B params | ~16–24 GB | ❌ No | Best quality but 14B minimum, even with FP8 quantisation. Block swap required, extremely slow. |
| **Wan 2.1 T2V** | 1.3B params | ~5–8 GB | ✅ Yes (text2vid) | 1.3B model fits comodamente. Only T2V — no img2vid support in 1.3B variant. |
| **FramePack (HunyuanVideo)** | 13B params | ~12–16 GB | ⚠️ Maybe with `gpu_memory_preservation` | Already tested earlier. OOM when `end_latent` disconnected. With same-image end_latent, requires 768 px bucket to avoid tensor mismatches. |

---

## Recommended Next Steps

1. **First attempt: LTX Video**
   - Install node: `ComfyUI-LTXVideo` (or `ComfyUI-LTXVideoWrapper`)
   - Model: `LTX-Video-2B` or `LTX-Video-0.9B`
   - Has native img2vid support, designed for consumer GPUs
   - Workflow structure should be: LoadImage → Encode → LTX Sampler → Decode → VideoCombine

2. **If LTX fails or quality is too low:**
   - Retry FramePack with `end_latent` connected to the SAME image,
     `gpu_memory_preservation` = 10, `latent_window_size` = 5, bucket
     size = 768×432, and fixed seed.

3. **Avoid for now:**
   - AnimateDiff I2V — requires complex multi-frame workflow not available
   - Wan 2.1 I2V 14B — VRAM requirements exceed 16 GB comfortably

---

## References

LTX Video node (ComfyUI):  
`https://github.com/Lightricks/ComfyUI-LTXVideo`

WanVideo wrapper (Kijai) — T2V only for 16 GB:  
`https://github.com/Kijai/ComfyUI-WanVideoWrapper`

FramePack wrapper (Kijai):  
`https://github.com/Kijai/ComfyUI-FramePackWrapper`
